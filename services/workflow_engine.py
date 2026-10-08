"""Deterministic workflow state transitions separated from LLM reasoning."""

from __future__ import annotations

from uuid import uuid4

from agents.workflow import WorkflowDraft, WorkflowStatus
from db.base.session_manager import SessionManager
from db.repositories.workflow_repository import WorkflowRepository


class InvalidWorkflowTransition(ValueError):
    pass


class WorkflowEngine:
    def __init__(self, db_path: str = "sqlite:///data/smart_appointment.db"):
        self.session_manager = SessionManager(db_path)
        self.repository = WorkflowRepository(self.session_manager)

    def save_draft(self, draft: WorkflowDraft, conversation_id: str) -> WorkflowDraft:
        is_new = draft.workflow_id is None
        if is_new:
            draft.workflow_id = f"WF-{uuid4().hex[:10].upper()}"
        self.repository.upsert(
            workflow_id=draft.workflow_id,
            conversation_id=conversation_id,
            workflow_type=draft.workflow_type.value,
            status=draft.status.value,
            fields=draft.fields,
            missing_fields=draft.missing_fields,
            assumptions=draft.assumptions,
            action="draft_created" if is_new else "draft_updated",
        )
        return draft

    def submit(self, draft: WorkflowDraft, conversation_id: str) -> WorkflowDraft:
        if draft.status is not WorkflowStatus.READY_FOR_CONFIRMATION:
            raise InvalidWorkflowTransition("Only a complete draft can be submitted")
        if draft.workflow_id is None:
            self.save_draft(draft, conversation_id)
        draft.status = WorkflowStatus.SUBMITTED
        self.repository.upsert(
            workflow_id=draft.workflow_id,
            conversation_id=conversation_id,
            workflow_type=draft.workflow_type.value,
            status=draft.status.value,
            fields=draft.fields,
            missing_fields=draft.missing_fields,
            assumptions=draft.assumptions,
            action="submitted",
        )
        return draft

    def cancel(self, draft: WorkflowDraft, conversation_id: str) -> WorkflowDraft:
        if draft.status in {WorkflowStatus.SUBMITTED, WorkflowStatus.CANCELLED}:
            raise InvalidWorkflowTransition(f"Cannot cancel workflow in {draft.status.value}")
        draft.status = WorkflowStatus.CANCELLED
        self.repository.upsert(
            workflow_id=draft.workflow_id,
            conversation_id=conversation_id,
            workflow_type=draft.workflow_type.value,
            status=draft.status.value,
            fields=draft.fields,
            missing_fields=draft.missing_fields,
            assumptions=draft.assumptions,
            action="cancelled",
        )
        return draft

    def get(self, workflow_id: str) -> dict | None:
        return self.repository.get(workflow_id)

    def list_by_conversation(self, conversation_id: str, limit: int = 20) -> list[dict]:
        return self.repository.list_by_conversation(conversation_id, limit)

    def close(self) -> None:
        self.session_manager.close()
