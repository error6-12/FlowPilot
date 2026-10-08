"""Lightweight, privacy-aware execution traces for Agent requests.

The in-memory store is intentionally dependency-free. It provides a stable
contract for the future operations dashboard and can later be replaced by
SQLite, OpenTelemetry, Langfuse, or another persistent backend.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import RLock
from time import perf_counter
from uuid import uuid4


@dataclass
class AgentExecutionTrace:
    trace_id: str
    conversation_id: str
    status: str
    started_at: str
    duration_ms: float | None
    input_chars: int
    output_chars: int
    output_chunks: int
    error_type: str | None = None
    prompt_versions: dict[str, str] = field(default_factory=dict)


class AgentTraceStore:
    """Keep bounded execution metadata without retaining message content."""

    def __init__(self, max_traces: int = 500):
        if max_traces < 1:
            raise ValueError("max_traces must be positive")
        self._traces: deque[AgentExecutionTrace] = deque(maxlen=max_traces)
        self._started: dict[str, float] = {}
        self._lock = RLock()

    def start(
        self,
        conversation_id: str,
        input_chars: int,
        prompt_versions: dict[str, str] | None = None,
    ) -> str:
        trace_id = str(uuid4())
        trace = AgentExecutionTrace(
            trace_id=trace_id,
            conversation_id=conversation_id,
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=None,
            input_chars=input_chars,
            output_chars=0,
            output_chunks=0,
            prompt_versions=dict(prompt_versions or {}),
        )
        with self._lock:
            self._traces.append(trace)
            self._started[trace_id] = perf_counter()
        return trace_id

    def finish(
        self,
        trace_id: str,
        *,
        output_chars: int,
        output_chunks: int,
        error: BaseException | None = None,
    ) -> None:
        with self._lock:
            trace = self._find(trace_id)
            if trace is None:
                return
            started = self._started.pop(trace_id, perf_counter())
            trace.duration_ms = round((perf_counter() - started) * 1000, 2)
            trace.output_chars = output_chars
            trace.output_chunks = output_chunks
            trace.status = "error" if error else "success"
            trace.error_type = type(error).__name__ if error else None

    def recent(self, limit: int = 50) -> list[dict]:
        safe_limit = max(1, min(limit, 200))
        with self._lock:
            return [asdict(trace) for trace in list(self._traces)[-safe_limit:]][::-1]

    def get(self, trace_id: str) -> dict | None:
        with self._lock:
            trace = self._find(trace_id)
            return asdict(trace) if trace else None

    def analytics(self, limit: int = 100) -> dict:
        safe_limit = max(1, min(limit, 500))
        with self._lock:
            traces = list(self._traces)[-safe_limit:]
        completed = [trace for trace in traces if trace.status != "running"]
        status_distribution: dict[str, int] = {}
        error_distribution: dict[str, int] = {}
        latency_buckets = {"0-500ms": 0, "500-1000ms": 0, "1000-2000ms": 0, ">2000ms": 0}
        trend = []
        for trace in completed:
            status_distribution[trace.status] = status_distribution.get(trace.status, 0) + 1
            if trace.error_type:
                error_distribution[trace.error_type] = error_distribution.get(trace.error_type, 0) + 1
            latency = trace.duration_ms or 0
            bucket = "0-500ms" if latency < 500 else "500-1000ms" if latency < 1000 else "1000-2000ms" if latency < 2000 else ">2000ms"
            latency_buckets[bucket] += 1
            trend.append({
                "started_at": trace.started_at,
                "success": trace.status == "success",
                "duration_ms": trace.duration_ms,
            })
        return {
            "sample_size": len(completed),
            "status_distribution": status_distribution,
            "error_distribution": error_distribution,
            "latency_buckets": latency_buckets,
            "trend": trend,
        }

    def summary(self) -> dict:
        with self._lock:
            completed = [trace for trace in self._traces if trace.status != "running"]
            successful = [trace for trace in completed if trace.status == "success"]
            durations = [trace.duration_ms for trace in completed if trace.duration_ms is not None]
            return {
                "total_requests": len(completed),
                "successful_requests": len(successful),
                "failed_requests": len(completed) - len(successful),
                "success_rate": round(len(successful) / len(completed), 4) if completed else None,
                "average_latency_ms": round(sum(durations) / len(durations), 2) if durations else None,
                "total_input_chars": sum(trace.input_chars for trace in completed),
                "total_output_chars": sum(trace.output_chars for trace in completed),
            }

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()
            self._started.clear()

    def _find(self, trace_id: str) -> AgentExecutionTrace | None:
        return next((trace for trace in reversed(self._traces) if trace.trace_id == trace_id), None)


agent_trace_store = AgentTraceStore()
