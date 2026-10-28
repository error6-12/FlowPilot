import pytest
from api.chat_handler import repeat_confirmation_reply
from api.workflow_query_context import workflow_query_focus
from agents.workflow import WorkflowDraft, WorkflowType, WorkflowStatus
from agents.workflow_agent import WorkflowAgent

class Records:
    def get(self,identifier):
        return dict(workflow_id=identifier,conversation_id='qa-r8',status='submitted')

def test_repeat_confirmation_only_for_owned_submitted_focus_without_active_draft():
    try:
        workflow_query_focus.set('qa-r8','WF-TEST8')
        reply=repeat_confirmation_reply('确认提交','qa-r8',Records())
        assert '已提交' in reply and '未再次提交' in reply and 'WF-TEST8' in reply
        draft=WorkflowDraft.build(WorkflowType.LEAVE,{'reason':'新申请'})
        assert repeat_confirmation_reply('确认提交','qa-r8',Records(),draft) is None
        assert repeat_confirmation_reply('我想提交一份新请假','qa-r8',Records()) is None
        workflow_query_focus.set('other','WF-TEST8')
        assert repeat_confirmation_reply('确认','other',Records()) is None
        workflow_query_focus.clear('qa-r8')
        assert repeat_confirmation_reply('确认','qa-r8',Records()) is None
    finally:
        workflow_query_focus.clear('qa-r8');workflow_query_focus.clear('other')

@pytest.mark.asyncio
async def test_booking_assumptions_use_user_labels_including_adjacent_chinese():
    draft=WorkflowDraft.build(WorkflowType.RESOURCE_BOOKING,dict(resource='A303',start_date='2026-12-21',end_date='2026-12-21',start_time='10:30',end_time='11:30'),assumptions=['start_date与end_date相同，description未提供'])
    agent=object.__new__(WorkflowAgent)
    async def create(text):return draft
    agent.create_draft=create
    result=''.join([chunk async for chunk in agent.run_stream('测试摘要')])
    assert '开始日期与结束日期相同' in result
    assert '预订主题未提供' in result
    assert 'start_date' not in result and 'end_date' not in result and 'description' not in result
