from services.hybrid_retrieval import BM25Index, reciprocal_rank_fusion, tokenize


DOCUMENTS = [
    {"id": 1, "content": "上海出差住宿标准为每晚五百元", "category": "travel", "keywords": ["差旅", "住宿"]},
    {"id": 2, "content": "会议室 A301 配有投影仪", "category": "resource", "keywords": ["会议室", "预订"]},
    {"id": 3, "content": "员工报销需要提交合规发票", "category": "finance", "keywords": ["报销", "发票"]},
]


def test_tokenize_mixed_chinese_and_ascii_terms():
    tokens = tokenize("预订 A301 会议室")
    assert "a301" in tokens
    assert "会议" in tokens
    assert "议室" in tokens


def test_bm25_finds_exact_business_entity_and_honors_filter():
    index = BM25Index(DOCUMENTS)
    assert index.search("A301 在哪里", top_k=2)[0].document_id == 2
    assert index.search("发票", top_k=2, allowed_ids={1, 2}) == []


def test_rrf_rewards_document_found_by_both_retrievers():
    fused = reciprocal_rank_fusion([[1, 2, 3], [2, 3, 1]], top_k=3)
    assert fused[0].document_id == 2
    assert {item.document_id for item in fused} == {1, 2, 3}
