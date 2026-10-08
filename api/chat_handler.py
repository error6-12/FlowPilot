from api.agent_observability import agent_trace_store
from api.conversation_runtime import conversation_runtime_store
from services.prompt_registry import prompt_registry

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
