from agents.consultant.response_generator import ResponseGenerator


def test_citations_are_deduplicated_and_preserve_retrieval_order():
    documents = [
        {"keywords": ["source:hr_policy/leave.md"]},
        {"keywords": ["source:hr_policy/leave.md"]},
        {"keywords": ["source:company_policy/approval.md"]},
    ]
    answer = ResponseGenerator._with_citations("请按流程提交。", documents)

    assert answer.count("hr_policy/leave.md") == 1
    assert answer.index("hr_policy/leave.md") < answer.index("company_policy/approval.md")
    assert "参考来源：" in answer


def test_answer_without_retrieved_sources_is_unchanged():
    assert ResponseGenerator._with_citations("证据不足。", []) == "证据不足。"
