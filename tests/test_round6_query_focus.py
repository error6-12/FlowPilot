from api.chat_handler import workflow_query_reply, remember_submitted_workflow
from api.workflow_query_context import WorkflowQueryFocus, workflow_query_focus
from api.conversation_runtime import ConversationRuntimeStore

class Records:
    rows={
        'WF-LEAVE':dict(workflow_id='WF-LEAVE',conversation_id='a',workflow_type='leave',status='submitted'),
        'WF-ROOM':dict(workflow_id='WF-ROOM',conversation_id='a',workflow_type='resource_booking',status='submitted'),
        'WF-IT':dict(workflow_id='WF-IT',conversation_id='b',workflow_type='it_support',status='submitted'),
    }
    def get(self,identifier):return self.rows.get(identifier)
    def list_by_conversation(self,cid,limit=100):
        return [self.rows[k] for k in ('WF-ROOM','WF-LEAVE','WF-IT') if self.rows[k]['conversation_id']==cid]

def test_old_explicit_record_then_pronoun_does_not_switch_to_newest():
    focus=WorkflowQueryFocus(); engine=Records()
    assert 'WF-LEAVE' in workflow_query_reply('查询 WF-LEAVE 状态','a',engine,focus)
    assert 'WF-LEAVE' in workflow_query_reply('它现在什么状态','a',engine,focus)
    assert 'WF-LEAVE' in workflow_query_reply('刚才查的那条申请状态','a',engine,focus)
    assert 'WF-ROOM' in workflow_query_reply('最新申请的状态','a',engine,focus)
    assert 'WF-ROOM' in workflow_query_reply('它现在什么状态','a',engine,focus)

def test_failed_lookup_clears_focus_instead_of_falling_back():
    focus=WorkflowQueryFocus(); engine=Records()
    workflow_query_reply('查询 WF-LEAVE 状态','a',engine,focus)
    assert '未找到' in workflow_query_reply('查询 WF-UNKNOWN 状态','a',engine,focus)
    assert '查询对象' in workflow_query_reply('它现在什么状态','a',engine,focus)
    assert '查询对象' in workflow_query_reply('它现在什么状态','empty',engine,focus)

def test_typed_switch_and_conversation_isolation():
    focus=WorkflowQueryFocus(); engine=Records()
    workflow_query_reply('查询 WF-LEAVE 状态','a',engine,focus)
    workflow_query_reply('查询 WF-IT 状态','b',engine,focus)
    assert 'WF-LEAVE' in workflow_query_reply('它现在什么状态','a',engine,focus)
    assert 'WF-IT' in workflow_query_reply('它现在什么状态','b',engine,focus)
    assert 'WF-ROOM' in workflow_query_reply('我的预订状态','a',engine,focus)
    assert 'WF-ROOM' in workflow_query_reply('它现在什么状态','a',engine,focus)
    assert '未找到' in workflow_query_reply('查询 WF-IT 状态','a',engine,focus)
    assert '查询对象' in workflow_query_reply('它现在什么状态','a',engine,focus)
    assert 'WF-IT' in workflow_query_reply('它现在什么状态','b',engine,focus)

def test_expiry_and_capacity():
    now=[0]; focus=WorkflowQueryFocus(ttl_seconds=10,max_sessions=2,clock=lambda:now[0])
    focus.set('a','WF-LEAVE'); focus.set('b','WF-IT'); focus.set('c','WF-ROOM')
    assert focus.get('a') is None
    now[0]=11
    assert focus.get('b') is None

def test_just_submitted_ignores_newer_cancelled_draft():
    class WithCancellation(Records):
        def list_by_conversation(self,cid,limit=100):
            return [dict(workflow_id='WF-CANCEL',conversation_id=cid,workflow_type='leave',status='cancelled')]+super().list_by_conversation(cid,limit)
    assert 'WF-ROOM' in workflow_query_reply('我刚提交的申请状态','a',WithCancellation(),WorkflowQueryFocus())

def test_submission_receipt_sets_focus_only_for_owned_persisted_record():
    engine=Records()
    try:
        remember_submitted_workflow('[REPLY]已提交成功，流程编号：WF-LEAVE。','a',engine)
        assert workflow_query_focus.get('a')=='WF-LEAVE'
        remember_submitted_workflow('[REPLY]已提交成功，流程编号：WF-IT。','a',engine)
        assert workflow_query_focus.get('a')=='WF-LEAVE'
        # Clearing a chat with no loaded Agent runtime must still clear focus.
        store=ConversationRuntimeStore(agent_factory=lambda cid:None)
        assert store.reset('a') is False
        assert workflow_query_focus.get('a') is None
    finally:workflow_query_focus.clear('a')
