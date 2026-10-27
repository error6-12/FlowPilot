import pytest
from agents.workflow import WorkflowDraft, WorkflowType, WorkflowStatus, WorkflowExtraction, WorkflowAction
from agents.workflow_agent import WorkflowAgent
from services.workflow_engine import WorkflowEngine
from services.enterprise_tools import create_workflow_tool_registry, TOOL_BY_WORKFLOW_TYPE

@pytest.mark.asyncio
@pytest.mark.parametrize('kind,fields',[
    (WorkflowType.RESOURCE_BOOKING,dict(resource='A303',start_date='2026-11-12',end_date='2026-11-12',start_time='15:00',end_time='16:00',description='QA-R3主题')),
    (WorkflowType.RESOURCE_BOOKING,dict(resource='A303',start_date='2026-11-12',end_date='2026-11-13',start_time='23:00',end_time='01:00',description='跨日')),
    (WorkflowType.IT_SUPPORT,dict(issue_description='鼠标无法使用',urgency='低',device_id='QA-R3-004',location='测试工位',description='工单测试')),
    (WorkflowType.LEAVE,dict(start_date='2026-11-09',end_date='2026-11-10',reason='QA')),
    (WorkflowType.REIMBURSEMENT,dict(amount=120,expense_type='交通',description='QA')),
])
async def test_agent_tool_database_audit_fields_match(tmp_path,kind,fields):
    engine=WorkflowEngine(f'sqlite:///{(tmp_path/"fields.db").as_posix()}')
    class Chain:
        async def ainvoke(self,payload):
            return WorkflowExtraction(workflow_type=kind,user_action=WorkflowAction.CONFIRM)
    try:
        agent=WorkflowAgent(session_id='round3',extraction_chain=Chain(),workflow_engine=engine)
        agent.current_draft=WorkflowDraft.build(kind,fields)
        engine.save_draft(agent.current_draft,'round3')
        result=await agent.create_draft('确认')
        assert result.status is WorkflowStatus.SUBMITTED
        record=engine.get(result.workflow_id)
        assert record['fields']==fields
        assert record['audit_logs'][-1]['details']['fields']==fields
        # Duplicate confirmation neither re-extracts nor adds submitted events.
        await agent.create_draft('确认')
        assert len([x for x in engine.get(result.workflow_id)['audit_logs'] if x['action']=='submitted'])==1
    finally: engine.close()

def test_booking_normalizes_full_datetimes_and_requires_date():
    draft=WorkflowDraft.build(WorkflowType.RESOURCE_BOOKING,dict(resource='A303',start_time='2026-11-12 15:00',end_time='2026-11-12 16:00',description='主题'))
    assert draft.fields['start_date']=='2026-11-12'
    assert draft.fields['end_time']=='16:00'
    missing=WorkflowDraft.build(WorkflowType.RESOURCE_BOOKING,dict(resource='A303',start_time='15:00',end_time='16:00'))
    assert missing.status is WorkflowStatus.NEEDS_INFORMATION
    assert set(missing.missing_fields)=={'start_date','end_date'}

def test_it_legacy_resource_becomes_device_id():
    draft=WorkflowDraft.build(WorkflowType.IT_SUPPORT,dict(resource='QA-R3-004',description='位置：测试工位',issue_description='鼠标坏了',urgency='低'))
    assert draft.fields['device_id']=='QA-R3-004'
    assert 'resource' not in draft.fields
    assert draft.fields['description']=='位置：测试工位'

def test_booking_reason_alias_becomes_topic_without_losing_text():
    draft=WorkflowDraft.build(WorkflowType.RESOURCE_BOOKING,dict(resource='A303',reason='QA主题',start_time='2026-11-12 15:00',end_time='2026-11-12 16:00'))
    assert draft.fields['description']=='QA主题'
    assert 'reason' not in draft.fields

@pytest.mark.asyncio
async def test_booking_date_and_time_correction_persists_final_values(tmp_path):
    engine=WorkflowEngine(f'sqlite:///{(tmp_path/"correction.db").as_posix()}')
    class Chain:
        results=[
            WorkflowExtraction(workflow_type=WorkflowType.RESOURCE_BOOKING,resource='A303',start_date='2026-11-12',end_date='2026-11-12',start_time='15:00',end_time='14:00',description='保留主题'),
            WorkflowExtraction(workflow_type=WorkflowType.RESOURCE_BOOKING,start_date='2026-11-13',end_date='2026-11-13',end_time='16:00',user_action=WorkflowAction.MODIFY),
            WorkflowExtraction(workflow_type=WorkflowType.RESOURCE_BOOKING,user_action=WorkflowAction.CONFIRM),
        ]
        async def ainvoke(self,payload):return self.results.pop(0)
    try:
        agent=WorkflowAgent(session_id='correction',extraction_chain=Chain(),workflow_engine=engine)
        await agent.create_draft('倒置时间草稿')
        await agent.create_draft('改到13日，结束时间改16点')
        result=await agent.create_draft('确认')
        record=engine.get(result.workflow_id)
        assert record['status']=='submitted'
        assert record['fields']['start_date']==record['fields']['end_date']=='2026-11-13'
        assert record['fields']['end_time']=='16:00'
        assert record['fields']['description']=='保留主题'
        assert record['audit_logs'][-1]['details']['fields']==record['fields']
    finally:engine.close()

@pytest.mark.asyncio
async def test_tool_preserves_stored_optional_fields_omitted_from_payload(tmp_path):
    engine=WorkflowEngine(f'sqlite:///{(tmp_path/"projection.db").as_posix()}')
    try:
        fields=dict(issue_description='鼠标故障',urgency='低',device_id='QA-DEVICE',location='测试工位',description='不可丢失')
        draft=WorkflowDraft.build(WorkflowType.IT_SUPPORT,fields)
        engine.save_draft(draft,'projection')
        registry=create_workflow_tool_registry(engine)
        result=await registry.execute('create_it_ticket',dict(workflow_id=draft.workflow_id,conversation_id='projection',issue_description='鼠标故障',urgency='低'),permissions={'workflow:submit'})
        assert result.success
        assert engine.get(draft.workflow_id)['fields']==fields
    finally:engine.close()
