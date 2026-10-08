"""Enterprise workflow tools exposed through the governed Tool Registry."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agents.workflow import WorkflowDraft, WorkflowType
from services.tool_registry import ToolDefinition, ToolRegistry
from services.tool_observability import tool_audit_store
from services.workflow_engine import WorkflowEngine


class WorkflowToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: str
    conversation_id: str


class LeaveToolInput(WorkflowToolInput):
    start_date: str
    end_date: str
    reason: str


class ReimbursementToolInput(WorkflowToolInput):
    amount: float = Field(gt=0)
    expense_type: str
    description: str


class ITSupportToolInput(WorkflowToolInput):
    issue_description: str
    urgency: str


class ResourceBookingToolInput(WorkflowToolInput):
    resource: str
    start_time: str
    end_time: str


class WorkflowToolOutput(BaseModel):
    workflow_id: str
    workflow_type: str
    status: str


TOOL_BY_WORKFLOW_TYPE = {
    WorkflowType.LEAVE: "submit_leave_request",
    WorkflowType.REIMBURSEMENT: "submit_reimbursement",
    WorkflowType.IT_SUPPORT: "create_it_ticket",
    WorkflowType.RESOURCE_BOOKING: "book_enterprise_resource",
}

INPUT_MODEL_BY_WORKFLOW_TYPE = {
    WorkflowType.LEAVE: LeaveToolInput,
    WorkflowType.REIMBURSEMENT: ReimbursementToolInput,
    WorkflowType.IT_SUPPORT: ITSupportToolInput,
    WorkflowType.RESOURCE_BOOKING: ResourceBookingToolInput,
}


def _handler(engine: WorkflowEngine, workflow_type: WorkflowType):
    def execute(item: WorkflowToolInput) -> dict[str, Any]:
        excluded = {"workflow_id", "conversation_id"}
        fields = {
            key: value
            for key, value in item.model_dump().items()
            if key not in excluded
        }
        draft = WorkflowDraft.build(workflow_type, fields)
        draft.workflow_id = item.workflow_id
        submitted = engine.submit(draft, item.conversation_id)
        return {
            "workflow_id": submitted.workflow_id,
            "workflow_type": submitted.workflow_type.value,
            "status": submitted.status.value,
        }

    return execute


def create_workflow_tool_registry(engine: WorkflowEngine) -> ToolRegistry:
    registry = ToolRegistry(audit_sink=tool_audit_store.record)
    definitions = (
        ("submit_leave_request", "提交员工请假申请", LeaveToolInput, WorkflowType.LEAVE),
        ("submit_reimbursement", "提交员工费用报销", ReimbursementToolInput, WorkflowType.REIMBURSEMENT),
        ("create_it_ticket", "创建企业 IT 支持工单", ITSupportToolInput, WorkflowType.IT_SUPPORT),
        ("book_enterprise_resource", "预订会议室或企业资源", ResourceBookingToolInput, WorkflowType.RESOURCE_BOOKING),
    )
    for name, description, input_model, workflow_type in definitions:
        registry.register(
            ToolDefinition(
                name=name,
                description=description,
                input_model=input_model,
                output_model=WorkflowToolOutput,
                handler=_handler(engine, workflow_type),
                timeout_seconds=5,
                max_retries=1,
                required_permissions=frozenset({"workflow:submit"}),
            )
        )
    return registry
