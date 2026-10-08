import pytest

from agents.workflow import WorkflowDraft, WorkflowStatus, WorkflowType
from services.workflow_engine import InvalidWorkflowTransition, WorkflowEngine


def test_workflow_engine_persists_submit_and_audit(tmp_path):
    database_file = tmp_path / "workflow.db"
    engine = WorkflowEngine(f"sqlite:///{database_file.as_posix()}")
    draft = WorkflowDraft.build(
        WorkflowType.RESOURCE_BOOKING,
        {"resource": "A301会议室", "start_time": "14:00", "end_time": "16:00"},
    )

    try:
        engine.save_draft(draft, "conversation-test")
        engine.submit(draft, "conversation-test")
        stored = engine.get(draft.workflow_id)

        assert stored["status"] == WorkflowStatus.SUBMITTED.value
        assert stored["fields"]["resource"] == "A301会议室"
        assert [log["action"] for log in stored["audit_logs"]] == [
            "draft_created",
            "submitted",
        ]
    finally:
        engine.close()


def test_workflow_engine_rejects_incomplete_submission(tmp_path):
    database_file = tmp_path / "workflow.db"
    engine = WorkflowEngine(f"sqlite:///{database_file.as_posix()}")
    draft = WorkflowDraft.build(WorkflowType.LEAVE, {"reason": "休息"})

    try:
        engine.save_draft(draft, "conversation-test")
        with pytest.raises(InvalidWorkflowTransition):
            engine.submit(draft, "conversation-test")
    finally:
        engine.close()
