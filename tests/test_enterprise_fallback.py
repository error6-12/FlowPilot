import pytest

from agents.task_classification.agent_router import AgentRouter
from agents.task_classification.state_manager import StateManager


async def collect(generator) -> str:
    chunks = []
    async for chunk in generator:
        chunks.append(chunk)
    return "".join(chunks)


@pytest.mark.asyncio
async def test_greeting_returns_enterprise_capabilities():
    router = AgentRouter(None, None, StateManager())

    response = await collect(router.handle_unsupported_task("other", "你好"))

    assert "企业智能协作助手" in response
    assert "请假" in response
    assert "报销" in response
    assert "按摩" not in response


@pytest.mark.asyncio
async def test_unsupported_task_no_longer_mentions_legacy_massage_scope():
    router = AgentRouter(None, None, StateManager())

    response = await collect(router.handle_unsupported_task("other", "帮我写一首诗"))

    assert "企业知识查询" in response
    assert "IT 工单" in response
    assert "按摩" not in response
