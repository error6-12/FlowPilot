"""Governed tool execution for Agent and MCP adapters."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, ValidationError


ToolHandler = Callable[[BaseModel], Any | Awaitable[Any]]


class ToolExecutionResult(BaseModel):
    tool_name: str
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    attempts: int = 0
    duration_ms: float = 0
    idempotency_hit: bool = False


class ToolPermissionError(PermissionError):
    pass


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: ToolHandler
    timeout_seconds: float = 10.0
    max_retries: int = 1
    required_permissions: frozenset[str] = field(default_factory=frozenset)


class ToolRegistry:
    """Execute registered tools through one auditable safety boundary."""

    def __init__(
        self,
        audit_capacity: int = 1000,
        audit_sink: Callable[[dict[str, Any]], None] | None = None,
    ):
        self._tools: dict[str, ToolDefinition] = {}
        self._idempotency_cache: dict[tuple[str, str], ToolExecutionResult] = {}
        self._audit_log: deque[dict[str, Any]] = deque(maxlen=audit_capacity)
        self._audit_sink = audit_sink

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool already registered: {definition.name}")
        if definition.timeout_seconds <= 0 or definition.max_retries < 0:
            raise ValueError("timeout_seconds must be positive and max_retries non-negative")
        self._tools[definition.name] = definition

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": item.name,
                "description": item.description,
                "input_schema": item.input_model.model_json_schema(),
                "output_schema": item.output_model.model_json_schema(),
                "required_permissions": sorted(item.required_permissions),
            }
            for item in self._tools.values()
        ]

    async def execute(
        self,
        name: str,
        payload: dict[str, Any],
        *,
        permissions: set[str] | None = None,
        idempotency_key: str | None = None,
        trace_id: str | None = None,
    ) -> ToolExecutionResult:
        definition = self._tools.get(name)
        if definition is None:
            return self._record(
                ToolExecutionResult(tool_name=name, success=False, error="tool_not_found"),
                trace_id,
            )

        missing_permissions = definition.required_permissions - (permissions or set())
        if missing_permissions:
            return self._record(
                ToolExecutionResult(
                    tool_name=name,
                    success=False,
                    error=f"permission_denied:{','.join(sorted(missing_permissions))}",
                ),
                trace_id,
            )

        cache_key = (name, idempotency_key) if idempotency_key else None
        if cache_key and cache_key in self._idempotency_cache:
            cached = self._idempotency_cache[cache_key].model_copy(deep=True)
            cached.idempotency_hit = True
            return self._record(cached, trace_id)

        try:
            validated_input = definition.input_model.model_validate(payload)
        except ValidationError as exc:
            return self._record(
                ToolExecutionResult(
                    tool_name=name,
                    success=False,
                    error=f"input_validation_error:{exc.error_count()}",
                ),
                trace_id,
            )

        started = time.perf_counter()
        last_error = "unknown_error"
        attempts = 0
        for attempts in range(1, definition.max_retries + 2):
            try:
                value = definition.handler(validated_input)
                if inspect.isawaitable(value):
                    value = await asyncio.wait_for(value, definition.timeout_seconds)
                validated_output = definition.output_model.model_validate(value)
                result = ToolExecutionResult(
                    tool_name=name,
                    success=True,
                    data=validated_output.model_dump(mode="json"),
                    attempts=attempts,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                )
                if cache_key:
                    self._idempotency_cache[cache_key] = result.model_copy(deep=True)
                return self._record(result, trace_id)
            except asyncio.TimeoutError:
                last_error = "timeout"
            except ValidationError as exc:
                last_error = f"output_validation_error:{exc.error_count()}"
                break
            except Exception as exc:
                last_error = f"handler_error:{type(exc).__name__}"

        return self._record(
            ToolExecutionResult(
                tool_name=name,
                success=False,
                error=last_error,
                attempts=attempts,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            ),
            trace_id,
        )

    def audit_records(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(self._audit_log)[-limit:]

    def _record(self, result: ToolExecutionResult, trace_id: str | None) -> ToolExecutionResult:
        record = {
            "trace_id": trace_id,
            **result.model_dump(mode="json"),
            "recorded_at": time.time(),
        }
        self._audit_log.append(record)
        if self._audit_sink:
            self._audit_sink(dict(record))
        return result
