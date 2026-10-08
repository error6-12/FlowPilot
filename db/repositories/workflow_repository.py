"""Persistence and audit repository for enterprise workflows."""

from __future__ import annotations

from datetime import UTC, datetime

from db.base.session_manager import SessionManager
from db.models import WorkflowAuditLog, WorkflowInstance


class WorkflowRepository:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    def upsert(
        self,
        *,
        workflow_id: str,
        conversation_id: str,
        workflow_type: str,
        status: str,
        fields: dict,
        missing_fields: list[str],
        assumptions: list[str],
        action: str,
    ) -> dict:
        with self.session_manager.session_scope() as session:
            instance = session.get(WorkflowInstance, workflow_id)
            previous_status = instance.status if instance else None
            if instance is None:
                instance = WorkflowInstance(
                    workflow_id=workflow_id,
                    conversation_id=conversation_id,
                    workflow_type=workflow_type,
                    status=status,
                    fields=fields,
                    missing_fields=missing_fields,
                    assumptions=assumptions,
                )
                session.add(instance)
            else:
                instance.workflow_type = workflow_type
                instance.status = status
                instance.fields = fields
                instance.missing_fields = missing_fields
                instance.assumptions = assumptions
                instance.updated_at = datetime.now(UTC)

            session.add(
                WorkflowAuditLog(
                    workflow_id=workflow_id,
                    action=action,
                    from_status=previous_status,
                    to_status=status,
                    details={"fields": fields, "missing_fields": missing_fields},
                )
            )
            session.flush()
            return self._to_dict(instance)

    def get(self, workflow_id: str) -> dict | None:
        with self.session_manager.session_scope() as session:
            instance = session.get(WorkflowInstance, workflow_id)
            return self._to_dict(instance, include_audit=True) if instance else None

    def list_by_conversation(self, conversation_id: str, limit: int = 20) -> list[dict]:
        with self.session_manager.session_scope() as session:
            instances = (
                session.query(WorkflowInstance)
                .filter(WorkflowInstance.conversation_id == conversation_id)
                .order_by(WorkflowInstance.updated_at.desc())
                .limit(limit)
                .all()
            )
            return [self._to_dict(instance) for instance in instances]

    @staticmethod
    def _to_dict(instance: WorkflowInstance, include_audit: bool = False) -> dict:
        result = {
            "workflow_id": instance.workflow_id,
            "conversation_id": instance.conversation_id,
            "workflow_type": instance.workflow_type,
            "status": instance.status,
            "fields": instance.fields or {},
            "missing_fields": instance.missing_fields or [],
            "assumptions": instance.assumptions or [],
            "created_at": instance.created_at.isoformat() if instance.created_at else None,
            "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
        }
        if include_audit:
            result["audit_logs"] = [
                {
                    "action": log.action,
                    "from_status": log.from_status,
                    "to_status": log.to_status,
                    "details": log.details,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in instance.audit_logs
            ]
        return result
