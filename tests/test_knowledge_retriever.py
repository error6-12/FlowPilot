from agents.consultant.knowledge_retriever import KnowledgeRetriever


def test_expands_relative_meeting_room_availability_query():
    expanded = KnowledgeRetriever._expand_retrieval_query("明天哪些会议室有空")

    assert expanded.startswith("明天哪些会议室有空")
    assert "会议室一周占用快照" in expanded
    assert "已确认预订记录" in expanded


def test_does_not_expand_generic_meeting_room_policy_query():
    query = "会议室如何预约"

    assert KnowledgeRetriever._expand_retrieval_query(query) == query
