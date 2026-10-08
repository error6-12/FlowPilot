"""Versioned FAISS index with document IDs and incremental mutations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

import faiss
import numpy as np


class VersionedVectorIndex:
    def __init__(self) -> None:
        self.index: faiss.IndexIDMap2 | None = None
        self.dimension: int | None = None
        self.version = 0
        self.updated_at: str | None = None
        self.last_operation = "empty"

    @staticmethod
    def _vector(values: list[float]) -> np.ndarray:
        vector = np.asarray([values], dtype="float32")
        if vector.ndim != 2 or vector.shape[1] == 0:
            raise ValueError("Embedding must be a non-empty one-dimensional vector")
        return vector

    def _new_index(self, dimension: int) -> faiss.IndexIDMap2:
        return faiss.IndexIDMap2(faiss.IndexFlatIP(dimension))

    def _touch(self, operation: str) -> None:
        self.version += 1
        self.updated_at = datetime.now(UTC).isoformat(timespec="seconds")
        self.last_operation = operation

    def build(self, entries: Iterable[tuple[int, list[float]]]) -> None:
        materialized = list(entries)
        if not materialized:
            self.index = None
            self.dimension = None
            self._touch("rebuild_empty")
            return
        vectors = np.asarray([embedding for _, embedding in materialized], dtype="float32")
        ids = np.asarray([document_id for document_id, _ in materialized], dtype="int64")
        self.dimension = int(vectors.shape[1])
        self.index = self._new_index(self.dimension)
        self.index.add_with_ids(vectors, ids)
        self._touch("rebuild")

    def upsert(self, document_id: int, embedding: list[float]) -> None:
        vector = self._vector(embedding)
        if self.index is None:
            self.dimension = int(vector.shape[1])
            self.index = self._new_index(self.dimension)
        if vector.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimension}, got {vector.shape[1]}"
            )
        ids = np.asarray([document_id], dtype="int64")
        self.index.remove_ids(ids)
        self.index.add_with_ids(vector, ids)
        self._touch("upsert")

    def delete(self, document_id: int) -> bool:
        if self.index is None:
            return False
        removed = int(self.index.remove_ids(np.asarray([document_id], dtype="int64")))
        if removed:
            self._touch("delete")
        return bool(removed)

    def search(self, embedding: list[float], top_k: int) -> tuple[list[float], list[int]]:
        if self.index is None or top_k <= 0:
            return [], []
        vector = self._vector(embedding)
        if vector.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimension}, got {vector.shape[1]}"
            )
        scores, ids = self.index.search(vector, min(top_k, self.index.ntotal))
        valid = [(float(score), int(document_id)) for score, document_id in zip(scores[0], ids[0]) if document_id >= 0]
        return [score for score, _ in valid], [document_id for _, document_id in valid]

    def status(self) -> dict:
        return {
            "version": self.version,
            "document_count": int(self.index.ntotal) if self.index is not None else 0,
            "dimension": self.dimension,
            "updated_at": self.updated_at,
            "last_operation": self.last_operation,
            "index_type": "faiss.IndexIDMap2(IndexFlatIP)",
        }
