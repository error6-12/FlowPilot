"""Dependency-free BM25 and reciprocal-rank fusion for knowledge retrieval."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable


_ASCII_TOKEN = re.compile(r"[a-zA-Z0-9_]+")
_CJK_SEQUENCE = re.compile(r"[\u3400-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """Tokenize mixed Chinese/ASCII text without requiring jieba.

    Chinese unigrams preserve short entities while bigrams provide useful phrase
    discrimination for policy names, resource names and business terminology.
    """
    normalized = text.lower()
    tokens = _ASCII_TOKEN.findall(normalized)
    for sequence in _CJK_SEQUENCE.findall(normalized):
        tokens.extend(sequence)
        tokens.extend(sequence[index:index + 2] for index in range(len(sequence) - 1))
    return tokens


@dataclass(frozen=True)
class RankedDocument:
    document_id: int
    score: float


class BM25Index:
    def __init__(self, documents: Iterable[dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._term_frequencies: dict[int, Counter[str]] = {}
        self._document_lengths: dict[int, int] = {}
        document_frequency: Counter[str] = Counter()

        for document in documents:
            document_id = int(document["id"])
            text = " ".join(
                [
                    str(document.get("content", "")),
                    str(document.get("category", "")),
                    " ".join(document.get("keywords") or []),
                ]
            )
            frequencies = Counter(tokenize(text))
            self._term_frequencies[document_id] = frequencies
            self._document_lengths[document_id] = sum(frequencies.values())
            document_frequency.update(frequencies.keys())

        self.document_count = len(self._term_frequencies)
        self.average_length = (
            sum(self._document_lengths.values()) / self.document_count
            if self.document_count
            else 0.0
        )
        self._idf = {
            term: math.log(1 + (self.document_count - count + 0.5) / (count + 0.5))
            for term, count in document_frequency.items()
        }

    def search(self, query: str, top_k: int, allowed_ids: set[int] | None = None) -> list[RankedDocument]:
        query_terms = tokenize(query)
        if not query_terms or not self.document_count:
            return []

        scores: list[RankedDocument] = []
        for document_id, frequencies in self._term_frequencies.items():
            if allowed_ids is not None and document_id not in allowed_ids:
                continue
            length = self._document_lengths[document_id]
            score = 0.0
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * length / max(self.average_length, 1.0)
                )
                score += self._idf.get(term, 0.0) * frequency * (self.k1 + 1) / denominator
            if score > 0:
                scores.append(RankedDocument(document_id=document_id, score=score))
        return sorted(scores, key=lambda item: (-item.score, item.document_id))[:top_k]


def reciprocal_rank_fusion(
    rankings: Iterable[Iterable[int]],
    top_k: int,
    rank_constant: int = 60,
) -> list[RankedDocument]:
    """Fuse multiple rankings using RRF; raw scores need not share a scale."""
    scores: Counter[int] = Counter()
    for ranking in rankings:
        for rank, document_id in enumerate(ranking, start=1):
            scores[int(document_id)] += 1.0 / (rank_constant + rank)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]
    return [RankedDocument(document_id=document_id, score=score) for document_id, score in ordered]
