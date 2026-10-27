"""Domain contracts for enterprise workflow requests."""

from enum import Enum
from datetime import datetime

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
    WorkflowType.RESOURCE_BOOKING: ("resource", "start_date", "end_date", "start_time", "end_time"),
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
        fields = dict(fields)
        if workflow_type in (WorkflowType.IT_SUPPORT, WorkflowType.RESOURCE_BOOKING) and fields.get('reason'):
            reason = fields.pop('reason')
            if fields.get('description'):
                if str(reason) not in str(fields['description']):
                    fields['description'] = f"{fields['description']}；{reason}"
            else:
                fields['description'] = reason
        if workflow_type is WorkflowType.IT_SUPPORT and fields.get('resource'):
            fields.setdefault('device_id', fields.pop('resource'))
        if workflow_type is WorkflowType.RESOURCE_BOOKING:
            for edge in ('start', 'end'):
                value = str(fields.get(f'{edge}_time', ''))
                if 'T' in value or ' ' in value:
                    try:
                        stamp = datetime.fromisoformat(value)
                    except ValueError:
                        continue
                    fields[f'{edge}_date'] = stamp.date().isoformat()
                    fields[f'{edge}_time'] = stamp.time().isoformat(timespec='minutes')
            if fields.get('start_date') and not fields.get('end_date'):
                fields['end_date'] = fields['start_date']
        missing = [field for field in REQUIRED_FIELDS[workflow_type] if fields.get(field) in (None, "")]
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
    reason: str | None = Field(default=None, description='仅请假原因；预订主题和工单说明填写description')
    amount: float | None = None
    expense_type: str | None = None
    description: str | None = Field(default=None, description='报销说明、资源预订主题或IT工单补充说明；保留用户原意')
    issue_description: str | None = None
    device_id: str | None = Field(default=None, description='IT设备编号，不要填入resource')
    location: str | None = Field(default=None, description='IT设备或故障发生位置')
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
