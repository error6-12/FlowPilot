"""Structured routing contracts shared by the classifier and API layer."""

from enum import Enum

from pydantic import BaseModel, Field


class TaskIntent(str, Enum):
    WORKFLOW = "workflow"
    APPOINTMENT = "appointment"
    QUERY = "query"
    PAY = "pay"
    STATISTICS = "statistics"
    OTHER = "other"


class AgentTarget(str, Enum):
    WORKFLOW = "workflow_agent"
    APPOINTMENT = "appointment_agent"
    CONSULTANT = "consultant_agent"
    UNSUPPORTED = "unsupported"


INTENT_TARGETS = {
    TaskIntent.WORKFLOW: AgentTarget.WORKFLOW,
    TaskIntent.APPOINTMENT: AgentTarget.APPOINTMENT,
    TaskIntent.QUERY: AgentTarget.CONSULTANT,
    TaskIntent.PAY: AgentTarget.UNSUPPORTED,
    TaskIntent.STATISTICS: AgentTarget.UNSUPPORTED,
    TaskIntent.OTHER: AgentTarget.UNSUPPORTED,
}


class RouteDecision(BaseModel):
    """Validated output produced for every routing decision."""

    intent: TaskIntent
    target_agent: AgentTarget
    confidence: float = Field(ge=0.0, le=1.0)
    needs_clarification: bool = False
    reasoning: str = Field(default="", max_length=300)

    @classmethod
    def fallback(cls, intent: TaskIntent = TaskIntent.OTHER) -> "RouteDecision":
        return cls(
            intent=intent,
            target_agent=INTENT_TARGETS[intent],
            confidence=0.0,
            needs_clarification=intent is TaskIntent.OTHER,
            reasoning="分类器未返回有效的结构化结果，已使用安全回退。",
        )
