import pytest
from api.chat_handler import workflow_query_reply, ProcessUserInput_stream
import api.chat_handler as handler

POLICY_CASES = [
    '查询公司的请假审批流程',
    '请查询请假审批顺序。正文保留[QA-R5]，用text代码块展示审批顺序。只咨询，不发起流程。',
    '公司的请假审批制度是什么？请依据知识库回答。这是制度咨询，不是查某个申请的状态。',
    '流程状态是什么意思？',
    '请假申请需要哪些审批，查询一下规则',
    '我不是查申请的状态，只想了解怎么报销',
]

class Records:
    def __init__(self): self.calls=[]
    def get(self, identifier):
        self.calls.append(('get',identifier))
        return {'workflow_id':identifier,'conversation_id':'own','workflow_type':'it_support','status':'submitted'} if identifier=='WF-IT001' else None
    def list_by_conversation(self, conversation_id, limit=1):
        self.calls.append(('list',conversation_id))
        if conversation_id!='own':return []
        return [
            dict(workflow_id='WF-EXP001',conversation_id='own',workflow_type='reimbursement',status='cancelled'),
            dict(workflow_id='WF-LEAVE001',conversation_id='own',workflow_type='leave',status='submitted'),
        ]
    def close(self):pass

@pytest.mark.parametrize('text',POLICY_CASES)
def test_policy_and_negation_never_read_recent_record(text):
    engine=Records()
    assert workflow_query_reply(text,'own',engine) is None
    assert engine.calls==[]
    assert workflow_query_reply(text,'empty',engine) is None
    assert engine.calls==[]

def test_explicit_recent_ambiguous_and_cross_type_queries():
    engine=Records()
    assert 'WF-IT001' in workflow_query_reply('查询 WF-IT001 的状态','own',engine)
    assert '未找到' in workflow_query_reply('查询 WF-IT001 的状态','other',engine)
    assert '未找到' in workflow_query_reply('查询 WF-UNKNOWN 状态','own',engine)
    assert 'WF-EXP001' in workflow_query_reply('它现在什么状态','own',engine)
    assert 'WF-LEAVE001' in workflow_query_reply('我刚才的请假申请进度如何','own',engine)
    assert 'WF-EXP001' not in workflow_query_reply('查询我的请假状态','own',engine)
    engine.calls.clear()
    assert '哪一条' in workflow_query_reply('查询申请状态','own',engine)
    assert engine.calls==[]

@pytest.mark.asyncio
@pytest.mark.parametrize('text',POLICY_CASES[:3])
async def test_policy_reaches_existing_agent_stream(monkeypatch,text):
    calls=[]
    class Agent:
        async def classify_task_stream(self, value):
            calls.append(value)
            yield '[REPLY][咨询机器人]公司制度答案'
    import asyncio
    from types import SimpleNamespace
    runtime=SimpleNamespace(agent=Agent(),execution_lock=asyncio.Lock())
    monkeypatch.setattr(handler,'WorkflowEngine',Records)
    monkeypatch.setattr(handler.conversation_runtime_store,'get_or_create',lambda cid:runtime)
    output=''.join([chunk async for chunk in ProcessUserInput_stream(text,'own')])
    assert calls==[text]
    assert '公司制度答案' in output and 'WF-EXP001' not in output
