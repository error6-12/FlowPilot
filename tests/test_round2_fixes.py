import pytest
from api.chat_handler import workflow_query_reply
from api import knowledge
from agents.workflow import WorkflowDraft, WorkflowType

class Records:
    def get(self, identifier):
        if identifier == 'WF-ABC123':
            return {'workflow_id':identifier,'conversation_id':'own','status':'submitted'}
    def list_by_conversation(self, conversation_id, limit=1):
        return [self.get('WF-ABC123')] if conversation_id == 'own' else []

def test_query_known_missing_and_cross_session():
    engine=Records()
    assert '已提交' in workflow_query_reply('查询流程 WF-ABC123 状态','own',engine)
    assert '未找到' in workflow_query_reply('查询 WF-ABC123 状态','other',engine)
    assert '未找到' in workflow_query_reply('查询 WF-UNKNOWN 状态','own',engine)
    assert '已提交' in workflow_query_reply('它现在什么状态','own',engine)
    assert workflow_query_reply('我要请假','own',engine) is None

def test_zero_amount_remains_present():
    draft=WorkflowDraft.build(WorkflowType.REIMBURSEMENT, {'amount':0,'expense_type':'交通','description':'测试'})
    assert 'amount' not in draft.missing_fields
    assert draft.fields['amount'] == 0

@pytest.mark.asyncio
async def test_search_contract_and_filters(monkeypatch):
    class Service:
        async def search(self, query, top_k, category):
            assert (query,top_k,category) == ('年假',5,'人事')
            return [{'id':1,'content':'年假制度'}]
    async def get_service():return Service()
    monkeypatch.setattr(knowledge,'get_knowledge_service',get_service)
    result=await knowledge.search_knowledge(knowledge.SearchRequest(query='年假',top_k=5,category='人事'))
    assert result['results'] == result['data']
    assert result['total_found'] == 1
    assert result['query'] == '年假'
