import asyncio

import pytest
from pydantic import BaseModel

from services.tool_registry import ToolDefinition, ToolRegistry


class Input(BaseModel):
    value: int


class Output(BaseModel):
    doubled: int


def definition(handler, **kwargs):
    return ToolDefinition(
        name="double",
        description="Double a number",
        input_model=Input,
        output_model=Output,
        handler=handler,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_registry_validates_and_executes_tool():
    registry = ToolRegistry()
    registry.register(definition(lambda item: {"doubled": item.value * 2}))

    result = await registry.execute("double", {"value": 4})

    assert result.success is True
    assert result.data == {"doubled": 8}
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_registry_rejects_invalid_input_and_missing_permission():
    registry = ToolRegistry()
    registry.register(definition(lambda item: {"doubled": 2}, required_permissions=frozenset({"write"})))

    denied = await registry.execute("double", {"value": 1})
    invalid = await registry.execute("double", {"value": "bad"}, permissions={"write"})

    assert denied.error == "permission_denied:write"
    assert invalid.error.startswith("input_validation_error")


@pytest.mark.asyncio
async def test_registry_retries_transient_handler_error():
    calls = 0

    def flaky(item):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")
        return {"doubled": item.value * 2}

    registry = ToolRegistry()
    registry.register(definition(flaky, max_retries=1))

    result = await registry.execute("double", {"value": 3})

    assert result.success is True
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_registry_enforces_timeout():
    async def slow(item):
        await asyncio.sleep(0.05)
        return {"doubled": item.value * 2}

    registry = ToolRegistry()
    registry.register(definition(slow, timeout_seconds=0.001, max_retries=0))

    result = await registry.execute("double", {"value": 3})

    assert result.success is False
    assert result.error == "timeout"


@pytest.mark.asyncio
async def test_registry_idempotency_and_audit():
    calls = 0

    def handler(item):
        nonlocal calls
        calls += 1
        return {"doubled": item.value * 2}

    registry = ToolRegistry()
    registry.register(definition(handler))
    first = await registry.execute("double", {"value": 5}, idempotency_key="same", trace_id="t1")
    second = await registry.execute("double", {"value": 999}, idempotency_key="same", trace_id="t2")

    assert first.data == second.data == {"doubled": 10}
    assert second.idempotency_hit is True
    assert calls == 1
    assert len(registry.audit_records()) == 2
