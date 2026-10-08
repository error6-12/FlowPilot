from services.reranker import LocalRelevanceReranker


def test_local_reranker_promotes_exact_business_terms():
    candidates = [
        {
            "id": 1,
            "content": "办公资源可以在系统中预约。",
            "category": "resource",
            "keywords": ["会议室"],
            "score": 0.033,
            "retrieval": {"strategy": "dense_bm25_rrf"},
        },
        {
            "id": 2,
            "content": "A301 会议室配有投影仪，可容纳十二人。",
            "category": "resource",
            "keywords": ["A301", "会议室"],
            "score": 0.031,
            "retrieval": {"strategy": "dense_bm25_rrf"},
        },
    ]

    results = LocalRelevanceReranker().rerank("A301会议室", candidates, top_k=2)

    assert results[0]["id"] == 2
    assert results[0]["rank"] == 1
    assert results[0]["retrieval"]["reranker"] == "local_relevance_v1"
    assert results[0]["retrieval"]["fusion_rank"] == 2


def test_local_reranker_is_stable_for_equal_scores_and_respects_top_k():
    candidates = [
        {"id": 1, "content": "无关", "score": 0.1},
        {"id": 2, "content": "无关", "score": 0.1},
    ]
    results = LocalRelevanceReranker().rerank("查询", candidates, top_k=1)
    assert [document["id"] for document in results] == [1]
