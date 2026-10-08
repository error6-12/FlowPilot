"""Pluggable reranking layer for hybrid retrieval candidates."""

from __future__ import annotations

import math
from typing import Any, Protocol

from .hybrid_retrieval import tokenize


class Reranker(Protocol):
    name: str

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]: ...


class LocalRelevanceReranker:
    """Deterministic zero-cost reranker combining lexical relevance and RRF prior.

    This is the default production-safe implementation. The interface allows a
    Cross-Encoder or LLM reranker to be injected later without changing callers.
    """

    name = "local_relevance_v1"

    @staticmethod
    def _lexical_score(query: str, document: dict[str, Any]) -> float:
        query_tokens = set(tokenize(query))
        if not query_tokens:
            return 0.0
        document_text = " ".join(
            [
                str(document.get("content", "")),
                str(document.get("category", "")),
                " ".join(document.get("keywords") or []),
            ]
        ).lower()
        document_tokens = set(tokenize(document_text))
        overlap = len(query_tokens & document_tokens)
        coverage = overlap / len(query_tokens)
        precision = overlap / max(len(document_tokens), 1)
        phrase_bonus = 0.2 if query.strip().lower() in document_text else 0.0
        return coverage + 0.25 * math.sqrt(precision) + phrase_bonus

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        lexical_scores = [self._lexical_score(query, document) for document in candidates]
        maximum_lexical = max(lexical_scores) or 1.0
        maximum_rrf = max(float(document.get("score", 0.0)) for document in candidates) or 1.0
        scored: list[tuple[float, int, dict[str, Any]]] = []

        for initial_rank, (document, lexical_score) in enumerate(
            zip(candidates, lexical_scores), start=1
        ):
            rrf_score = float(document.get("score", 0.0))
            final_score = 0.55 * (lexical_score / maximum_lexical) + 0.45 * (rrf_score / maximum_rrf)
            enriched = dict(document)
            retrieval = dict(enriched.get("retrieval") or {})
            retrieval.update(
                {
                    "fusion_rank": initial_rank,
                    "reranker": self.name,
                    "reranker_score": round(final_score, 6),
                }
            )
            enriched["retrieval"] = retrieval
            enriched["score"] = final_score
            scored.append((final_score, initial_rank, enriched))

        ordered = sorted(scored, key=lambda item: (-item[0], item[1]))[:top_k]
        results = []
        for final_rank, (_, _, document) in enumerate(ordered, start=1):
            document["rank"] = final_rank
            results.append(document)
        return results
