from api.agent_observability import agent_trace_store
from api.conversation_runtime import conversation_runtime_store
from services.prompt_registry import prompt_registry
import re
from services.workflow_engine import WorkflowEngine


def workflow_query_reply(text, conversation_id, engine):
    """Read actual records only, scoped to the requesting conversation."""
    identifier = re.search(r'\bWF-[A-Za-z0-9]+\b', text, re.I)
    query = any(word in text for word in ('查询', '状态', '进度', '查一下', '查下'))
    if not query or not (identifier or any(word in text for word in ('流程', '申请', '工单', '它', '刚才'))):
        return None
    if identifier:
        record = engine.get(identifier.group().upper())
        if not record or record.get('conversation_id') != conversation_id:
            return '未找到当前会话可查询的该流程，请核对编号，并在创建流程的会话中查询。'
    else:
        records = engine.list_by_conversation(conversation_id, limit=1)
        if not records:
            return '当前会话暂无流程记录，请提供流程编号，或先创建流程。'
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
