"""Process-wide, bounded metrics store for governed tool executions."""

from __future__ import annotations

from collections import Counter, deque
from threading import RLock
from typing import Any


class ToolAuditStore:
    def __init__(self, capacity: int = 2000):
        self._records: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = RLock()

    def record(self, item: dict[str, Any]) -> None:
        with self._lock:
            self._records.append(dict(item))

    def recent(self, limit: int = 50, tool_name: str | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 200))
        with self._lock:
            records = list(self._records)
        if tool_name:
            records = [item for item in records if item["tool_name"] == tool_name]
        return records[-safe_limit:][::-1]

    def for_trace(self, trace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._records if item.get("trace_id") == trace_id]

    def trend(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._lock:
            records = list(self._records)[-safe_limit:]
        return [
            {
                "recorded_at": item.get("recorded_at"),
                "tool_name": item.get("tool_name"),
                "success": bool(item.get("success")),
                "duration_ms": item.get("duration_ms"),
            }
            for item in records
        ]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            records = list(self._records)
        successful = [item for item in records if item["success"]]
        durations = [item["duration_ms"] for item in records]
        by_tool = Counter(item["tool_name"] for item in records)
        successes_by_tool = Counter(item["tool_name"] for item in successful)
        errors = Counter(item["error"] for item in records if item["error"])
        return {
            "total_calls": len(records),
            "successful_calls": len(successful),
            "failed_calls": len(records) - len(successful),
            "success_rate": round(len(successful) / len(records), 4) if records else None,
            "average_latency_ms": round(sum(durations) / len(durations), 2) if durations else None,
            "idempotency_hits": sum(bool(item["idempotency_hit"]) for item in records),
            "by_tool": {
                name: {
                    "calls": count,
                    "successful": successes_by_tool[name],
                    "success_rate": round(successes_by_tool[name] / count, 4),
                }
                for name, count in sorted(by_tool.items())
            },
            "errors": dict(errors),
        }

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


tool_audit_store = ToolAuditStore()
