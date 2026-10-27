import pytest

from agents.workflow import WorkflowDraft, WorkflowStatus, WorkflowType
from services.enterprise_tools import create_workflow_tool_registry
from services.workflow_engine import WorkflowEngine


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "workflow_type", "fields"),
    [
        ("submit_leave_request", WorkflowType.LEAVE, {"start_date": "2026-10-01", "end_date": "2026-10-01", "reason": "家中有事"}),
        ("submit_reimbursement", WorkflowType.REIMBURSEMENT, {"amount": 500, "expense_type": "交通费", "description": "机场打车"}),
        ("create_it_ticket", WorkflowType.IT_SUPPORT, {"issue_description": "无法联网", "urgency": "紧急"}),
        ("book_enterprise_resource", WorkflowType.RESOURCE_BOOKING, {"resource": "A301", "start_date": "2026-11-12", "end_date": "2026-11-12", "start_time": "14:00", "end_time": "16:00"}),
    ],
)
async def test_enterprise_workflow_tools_submit_and_persist(tmp_path, tool_name, workflow_type, fields):
    engine = WorkflowEngine(f"sqlite:///{(tmp_path / f'{tool_name}.db').as_posix()}")
    registry = create_workflow_tool_registry(engine)
    draft = WorkflowDraft.build(workflow_type, fields)
    engine.save_draft(draft, "conversation-tools")

    try:
        result = await registry.execute(
            tool_name,
            {"workflow_id": draft.workflow_id, "conversation_id": "conversation-tools", **fields},
            permissions={"workflow:submit"},
            idempotency_key=draft.workflow_id,
            trace_id="trace-tools",
        )
        stored = engine.get(draft.workflow_id)

        assert result.success is True
        assert stored["status"] == WorkflowStatus.SUBMITTED.value
        assert registry.audit_records()[-1]["trace_id"] == "trace-tools"
    finally:
        engine.close()


@pytest.mark.asyncio
async def test_enterprise_tool_requires_submit_permission(tmp_path):
    engine = WorkflowEngine(f"sqlite:///{(tmp_path / 'permission.db').as_posix()}")
    registry = create_workflow_tool_registry(engine)
    try:
        result = await registry.execute(
            "create_it_ticket",
            {
                "workflow_id": "WF-PERMISSION",
                "conversation_id": "conversation-tools",
                "issue_description": "无法联网",
                "urgency": "紧急",
            },
        )
        assert result.success is False
        assert result.error == "permission_denied:workflow:submit"
    finally:
        engine.close()
