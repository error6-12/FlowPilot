"""Read-only API endpoints for Agent execution metrics and traces."""

from fastapi import APIRouter, HTTPException, Query

from api.agent_observability import agent_trace_store
from services.tool_observability import tool_audit_store


router = APIRouter(prefix="/api/observability", tags=["Agent 可观测性"])


@router.get("/summary")
async def get_agent_summary():
    return agent_trace_store.summary()


@router.get("/traces")
async def get_recent_agent_traces(limit: int = Query(default=50, ge=1, le=200)):
    return {"traces": agent_trace_store.recent(limit), "limit": limit}


@router.get("/traces/{trace_id}")
async def get_agent_trace_detail(trace_id: str):
    trace = agent_trace_store.get(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return {"trace": trace, "tool_calls": tool_audit_store.for_trace(trace_id)}


@router.get("/analytics")
async def get_observability_analytics(limit: int = Query(default=100, ge=1, le=500)):
    return {
        "agent": agent_trace_store.analytics(limit),
        "tools": {
            "summary": tool_audit_store.summary(),
            "trend": tool_audit_store.trend(limit),
        },
    }


@router.get("/tools/summary")
async def get_tool_summary():
    return tool_audit_store.summary()


@router.get("/tools/calls")
async def get_recent_tool_calls(
    limit: int = Query(default=50, ge=1, le=200),
    tool_name: str | None = Query(default=None),
):
    return {
        "calls": tool_audit_store.recent(limit=limit, tool_name=tool_name),
        "limit": limit,
        "tool_name": tool_name,
    }
