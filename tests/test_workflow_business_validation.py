import pytest
from agents.workflow import WorkflowDraft, WorkflowStatus, WorkflowType
from services.workflow_engine import WorkflowEngine
from services.workflow_validation import validate_workflow

@pytest.mark.parametrize('kind,fields', [
    ('leave', {'start_date':'2026-11-05','end_date':'2026-11-03'}),
    ('leave', {'start_date':'2026-02-30','end_date':'2026-03-01'}),
    ('reimbursement', {'amount':-100}),
    ('reimbursement', {'amount':'NaN'}),
    ('resource_booking', {'start_time':'16:00','end_time':'14:00'}),
    ('resource_booking', {'start_time':'14:00','end_time':'14:00'}),
])
def test_invalid_fields_are_rejected(kind, fields):
    with pytest.raises(ValueError): validate_workflow(kind, fields)

def test_invalid_leave_never_persists_submitted(tmp_path):
    engine=WorkflowEngine(f'sqlite:///{(tmp_path / "validation.db").as_posix()}')
    draft=WorkflowDraft.build(WorkflowType.LEAVE, {'start_date':'2026-11-05','end_date':'2026-11-03','reason':'QA'})
    try:
        engine.save_draft(draft,'test')
        with pytest.raises(ValueError): engine.submit(draft,'test')
        assert draft.status is WorkflowStatus.READY_FOR_CONFIRMATION
        record=engine.get(draft.workflow_id)
        assert record['status'] != 'submitted'
        assert all(item['action'] != 'submitted' for item in record['audit_logs'])
    finally: engine.close()
