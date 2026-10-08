"""Domain contracts for enterprise workflow requests."""

from enum import Enum

from pydantic import BaseModel, Field


class WorkflowType(str, Enum):
    LEAVE = "leave"
    REIMBURSEMENT = "reimbursement"
    IT_SUPPORT = "it_support"
    RESOURCE_BOOKING = "resource_booking"
    UNKNOWN = "unknown"


class WorkflowStatus(str, Enum):
    NEEDS_INFORMATION = "needs_information"
    READY_FOR_CONFIRMATION = "ready_for_confirmation"
    SUBMITTED = "submitted"
    CANCELLED = "cancelled"


class WorkflowAction(str, Enum):
    NONE = "none"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    MODIFY = "modify"


REQUIRED_FIELDS: dict[WorkflowType, tuple[str, ...]] = {
    WorkflowType.LEAVE: ("start_date", "end_date", "reason"),
    WorkflowType.REIMBURSEMENT: ("amount", "expense_type", "description"),
    WorkflowType.IT_SUPPORT: ("issue_description", "urgency"),
    WorkflowType.RESOURCE_BOOKING: ("resource", "start_time", "end_time"),
    WorkflowType.UNKNOWN: (),
}


class WorkflowDraft(BaseModel):
    workflow_type: WorkflowType
    fields: dict[str, str | float] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.NEEDS_INFORMATION
    assumptions: list[str] = Field(default_factory=list)
    workflow_id: str | None = None

    @classmethod
    def build(
        cls,
        workflow_type: WorkflowType,
        fields: dict[str, str | float],
        assumptions: list[str] | None = None,
    ):
        missing = [field for field in REQUIRED_FIELDS[workflow_type] if not fields.get(field)]
        status = (
            WorkflowStatus.READY_FOR_CONFIRMATION
            if workflow_type is not WorkflowType.UNKNOWN and not missing
            else WorkflowStatus.NEEDS_INFORMATION
        )
        return cls(
            workflow_type=workflow_type,
            fields=fields,
            missing_fields=missing,
            status=status,
            assumptions=assumptions or [],
        )


class WorkflowExtraction(BaseModel):
    """Semantic fields extracted by the LLM from the latest conversation turn."""

    workflow_type: WorkflowType
    start_date: str | None = None
    end_date: str | None = None
    reason: str | None = None
    amount: float | None = None
    expense_type: str | None = None
    description: str | None = None
    issue_description: str | None = None
    urgency: str | None = None
    resource: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    user_action: WorkflowAction = WorkflowAction.NONE

    def extracted_fields(self) -> dict[str, str | float]:
        excluded = {"workflow_type", "assumptions", "confidence", "user_action"}
        return {
            key: value
            for key, value in self.model_dump().items()
            if key not in excluded and value not in (None, "")
        }
