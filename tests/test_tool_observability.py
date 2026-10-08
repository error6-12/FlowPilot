import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.observability import router
from api.agent_observability import agent_trace_store
from services.tool_observability import tool_audit_store


@pytest.fixture(autouse=True)
def clear_store():
    tool_audit_store.clear()
    agent_trace_store.clear()
    yield
    tool_audit_store.clear()
    agent_trace_store.clear()


@pytest.mark.asyncio
async def test_tool_observability_summary_and_calls_api():
    tool_audit_store.record({
        "trace_id": "t1", "tool_name": "create_it_ticket", "success": True,
        "data": {"status": "submitted"}, "error": None, "attempts": 1,
        "duration_ms": 12.5, "idempotency_hit": False, "recorded_at": 1.0,
    })
    tool_audit_store.record({
        "trace_id": "t2", "tool_name": "create_it_ticket", "success": False,
        "data": None, "error": "timeout", "attempts": 2,
        "duration_ms": 20.0, "idempotency_hit": False, "recorded_at": 2.0,
    })
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        summary = (await client.get("/api/observability/tools/summary")).json()
        calls = (await client.get("/api/observability/tools/calls?tool_name=create_it_ticket")).json()

    assert summary["total_calls"] == 2
    assert summary["success_rate"] == 0.5
    assert summary["errors"] == {"timeout": 1}
    assert len(calls["calls"]) == 2
    assert tool_audit_store.for_trace("t2")[0]["error"] == "timeout"
    assert len(tool_audit_store.trend()) == 2


@pytest.mark.asyncio
async def test_mcp_server_registers_four_enterprise_tools():
    from mcp_server import mcp

    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert names == {
        "submit_leave_request",
        "submit_reimbursement",
        "create_it_ticket",
        "book_enterprise_resource",
    }


@pytest.mark.asyncio
async def test_trace_detail_and_combined_analytics_api():
    trace_id = agent_trace_store.start("conversation-api", input_chars=4)
    agent_trace_store.finish(trace_id, output_chars=8, output_chunks=2)
    tool_audit_store.record({
        "trace_id": trace_id, "tool_name": "create_it_ticket", "success": True,
        "data": None, "error": None, "attempts": 1, "duration_ms": 3.0,
        "idempotency_hit": False, "recorded_at": 3.0,
    })
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        detail = (await client.get(f"/api/observability/traces/{trace_id}")).json()
        analytics = (await client.get("/api/observability/analytics")).json()

    assert detail["trace"]["trace_id"] == trace_id
    assert detail["tool_calls"][0]["tool_name"] == "create_it_ticket"
    assert analytics["agent"]["sample_size"] == 1
    assert len(analytics["tools"]["trend"]) == 1
