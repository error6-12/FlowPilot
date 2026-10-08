"""MCP server exposing governed enterprise workflow tools.

Run with: python mcp_server.py
The default transport is stdio for local MCP clients.
"""

from __future__ import annotations

from uuid import uuid4

from mcp.server.mcpserver import MCPServer

from services.enterprise_tools import create_workflow_tool_registry
from services.workflow_engine import WorkflowEngine


mcp = MCPServer(
    "enterprise-workflow-tools",
    description="请假、报销、IT 工单和企业资源预订工具",
    version="1.0.0",
)
workflow_engine = WorkflowEngine()
tool_registry = create_workflow_tool_registry(workflow_engine)


async def _execute(name: str, payload: dict) -> dict:
    workflow_id = payload.get("workflow_id") or f"WF-{uuid4().hex[:10].upper()}"
    payload["workflow_id"] = workflow_id
    result = await tool_registry.execute(
        name,
        payload,
        permissions={"workflow:submit"},
        idempotency_key=workflow_id,
        trace_id=f"mcp:{payload['conversation_id']}",
    )
    return result.model_dump(mode="json")


@mcp.tool(description="提交员工请假申请")
async def submit_leave_request(
    conversation_id: str,
    start_date: str,
    end_date: str,
    reason: str,
    workflow_id: str | None = None,
) -> dict:
    return await _execute("submit_leave_request", locals())


@mcp.tool(description="提交员工费用报销")
async def submit_reimbursement(
    conversation_id: str,
    amount: float,
    expense_type: str,
    description: str,
    workflow_id: str | None = None,
) -> dict:
    return await _execute("submit_reimbursement", locals())


@mcp.tool(description="创建企业 IT 支持工单")
async def create_it_ticket(
    conversation_id: str,
    issue_description: str,
    urgency: str,
    workflow_id: str | None = None,
) -> dict:
    return await _execute("create_it_ticket", locals())


@mcp.tool(description="预订会议室或企业资源")
async def book_enterprise_resource(
    conversation_id: str,
    resource: str,
    start_time: str,
    end_time: str,
    workflow_id: str | None = None,
) -> dict:
    return await _execute("book_enterprise_resource", locals())


if __name__ == "__main__":
    mcp.run()
