from api.conversation_runtime import ConversationRuntimeStore


class FakeAgent:
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.reset_calls = 0

    def reset_conversation(self):
        self.reset_calls += 1


def test_same_conversation_reuses_runtime():
    store = ConversationRuntimeStore(agent_factory=FakeAgent)

    first = store.get_or_create("conversation-a")
    second = store.get_or_create("conversation-a")

    assert first is second
    assert store.count() == 1


def test_different_conversations_do_not_share_agents():
    store = ConversationRuntimeStore(agent_factory=FakeAgent)

    first = store.get_or_create("conversation-a")
    second = store.get_or_create("conversation-b")

    assert first.agent is not second.agent
    assert first.agent.conversation_id == "conversation-a"
    assert second.agent.conversation_id == "conversation-b"
    assert first.execution_lock is not second.execution_lock


def test_reset_removes_only_target_conversation():
    store = ConversationRuntimeStore(agent_factory=FakeAgent)
    first = store.get_or_create("conversation-a")
    store.get_or_create("conversation-b")

    assert store.reset("conversation-a") is True
    assert first.agent.reset_calls == 1
    assert store.count() == 1
    assert store.get_or_create("conversation-b").agent.conversation_id == "conversation-b"
