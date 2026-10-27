from api.agent_observability import agent_trace_store
from api.conversation_runtime import conversation_runtime_store
from services.prompt_registry import prompt_registry
import re
from services.workflow_engine import WorkflowEngine


def workflow_query_reply(text, conversation_id, engine):
    """Conservative record lookup; policy questions stay with semantic routing.

    A query verb plus a business noun is not evidence of an instance lookup.
    Without an ID, require explicit reference to an existing personal/recent
    instance. Ambiguous status requests clarify instead of selecting a record.
    """
    identifier = re.search(r'\bWF-[A-Za-z0-9]+\b', text, re.I)
    query = any(word in text for word in ('查询', '状态', '进度', '查一下', '查下', '查查', '批了吗', '处理到哪'))
    negated_lookup = re.search(r'(?:不是|并非|不要|不需要|无需|不用|不想).{0,12}(?:查|申请.*状态|流程.*状态)', text)
    if negated_lookup:
        return None
    if not query:
        return None
    if identifier:
        record = engine.get(identifier.group().upper())
        if not record or record.get('conversation_id') != conversation_id:
            return '未找到当前会话可查询的该流程，请核对编号，并在创建流程的会话中查询。'
    else:
        # These phrases describe general knowledge, not persisted instances.
        if any(word in text for word in ('制度', '规则', '审批流程', '审批顺序', '知识库', '只咨询', '制度咨询', '是什么意思', '含义')):
            return None
        status_query = any(word in text for word in ('状态', '进度', '批了吗', '处理到哪'))
        reference = re.search(r'它|这(?:个|条|笔|次)|该(?:流程|申请|工单)|刚才|刚刚|上一条|最近|我的|我提交的|本人', text)
        business = any(word in text for word in ('流程', '申请', '工单', '请假', '报销', '预订', '预约'))
        if not reference:
            if status_query and business:
                return '你想查询哪一条申请的状态？请提供 WF 流程编号，或说明“我刚才提交的请假/报销/工单/预订”。'
            return None
        if not status_query and not business:
            return None
        types = {
            'leave': ('请假',), 'reimbursement': ('报销',),
            'it_support': ('工单', '报修'), 'resource_booking': ('预订', '预约'),
        }
        requested_types = [kind for kind, words in types.items() if any(word in text for word in words)]
        if len(requested_types) > 1:
            return '请说明要查询哪一类申请，或提供对应的 WF 流程编号。'
        records = engine.list_by_conversation(conversation_id, limit=100)
        if requested_types:
            records = [record for record in records if record.get('workflow_type') == requested_types[0]]
        if not records:
            return '未找到当前会话中符合条件的流程记录，请提供流程编号，并在创建该流程的会话中查询。'
        record = records[0]
    statuses = {'submitted':'已提交','cancelled':'已取消','ready_for_confirmation':'等待确认','needs_information':'待补充信息'}
    return f"流程编号：{record['workflow_id']}；状态：{statuses.get(record['status'], record['status'])}。此状态表示本平台记录，不代表外部 OA 已审批。"

async def ProcessUserInput_stream(
    user_input,
    conversation_id: str = "default",
    state=None,
    context=None,
):
    """
    user_input: 用户输入
    state: 当前对话状态（如 None, 'classify', 'appointment', 'query', ...）
    context: 可选，保存多轮对话上下文（如 dict，可存储 agent 的 history 等）
    返回: (reply, next_state, next_context)
    """
    # 初始化 context
    if context is None:
        context = {}

    trace_id = agent_trace_store.start(
        conversation_id,
        len(user_input or ""),
        prompt_versions=prompt_registry.active_versions(),
    )
    output_chars = 0
    output_chunks = 0
    failure = None

    try:
        engine = WorkflowEngine()
        try:
            reply = workflow_query_reply(user_input, conversation_id, engine)
        finally:
            engine.close()
        if reply:
            token = '[REPLY][任务协调Agent]' + reply
            output_chunks += 1
            output_chars += len(token)
            yield token
            return
        if any(phrase in user_input for phrase in ('你能做什么', '提供哪些帮助', '有哪些功能', '介绍一下功能')) or user_input.strip() in ('你好', '您好', 'hello'):
            token = '[REPLY][任务协调Agent]你好！我可以查询企业制度、办理请假和报销、创建 IT 工单、预订资源，并查询当前会话的流程状态。你可以说“我要请假”或“查询刚才申请的状态”。'
            output_chunks += 1
            output_chars += len(token)
            yield token
            return
        runtime = conversation_runtime_store.get_or_create(conversation_id)
        async with runtime.execution_lock:
            async for token in runtime.agent.classify_task_stream(user_input):
                output_chunks += 1
                output_chars += len(token)
                yield token
    except BaseException as exc:
        failure = exc
        raise
    finally:
        agent_trace_store.finish(
            trace_id,
            output_chars=output_chars,
            output_chunks=output_chunks,
            error=failure,
        )
