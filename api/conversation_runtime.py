"""Conversation-scoped agent runtimes.

The previous implementation kept one module-level agent for every visitor. This
store gives each conversation its own stateful agent graph while keeping the
storage implementation replaceable by Redis or a LangGraph checkpointer later.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Callable
from uuid import uuid4
from api.workflow_query_context import workflow_query_focus

from agents.appointment_agent import AppointmentAgent
from agents.consultant_agent import ConsultantAgent
from agents.task_classification_agent import TaskClassificationAgent
from agents.workflow_agent import WorkflowAgent


AgentFactory = Callable[[str], TaskClassificationAgent]


@dataclass
class ConversationRuntime:
    conversation_id: str
    agent: TaskClassificationAgent
    last_accessed_at: datetime
    execution_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def create_conversation_agent(conversation_id: str) -> TaskClassificationAgent:
    return TaskClassificationAgent(
        AppointmentAgent(session_id=conversation_id),
        ConsultantAgent(session_id=conversation_id),
        WorkflowAgent(session_id=conversation_id),
    )


class ConversationRuntimeStore:
    def __init__(
        self,
        agent_factory: AgentFactory = create_conversation_agent,
        ttl_minutes: int = 60,
        max_sessions: int = 500,
    ):
        self._agent_factory = agent_factory
        self._ttl = timedelta(minutes=ttl_minutes)
        self._max_sessions = max_sessions
        self._runtimes: dict[str, ConversationRuntime] = {}
        self._lock = RLock()

    @staticmethod
    def new_conversation_id() -> str:
        return str(uuid4())

    def get_or_create(self, conversation_id: str) -> ConversationRuntime:
        if not conversation_id or len(conversation_id) > 128:
            raise ValueError("conversation_id must be between 1 and 128 characters")

        now = datetime.now(timezone.utc)
        with self._lock:
            self._evict_expired(now)
            runtime = self._runtimes.get(conversation_id)
            if runtime is None:
                self._evict_oldest_if_full()
                runtime = ConversationRuntime(
                    conversation_id=conversation_id,
                    agent=self._agent_factory(conversation_id),
                    last_accessed_at=now,
                )
                self._runtimes[conversation_id] = runtime
            else:
                runtime.last_accessed_at = now
            return runtime

    def reset(self, conversation_id: str) -> bool:
        workflow_query_focus.clear(conversation_id)
        with self._lock:
            runtime = self._runtimes.pop(conversation_id, None)
        if runtime is None:
            return False
        runtime.agent.reset_conversation()
        return True

    def count(self) -> int:
        with self._lock:
            return len(self._runtimes)

    def _evict_expired(self, now: datetime) -> None:
        expired = [
            key
            for key, runtime in self._runtimes.items()
            if now - runtime.last_accessed_at > self._ttl
        ]
        for key in expired:
            self._runtimes.pop(key, None)

    def _evict_oldest_if_full(self) -> None:
        if len(self._runtimes) < self._max_sessions:
            return
        oldest_key = min(
            self._runtimes,
            key=lambda key: self._runtimes[key].last_accessed_at,
        )
        self._runtimes.pop(oldest_key, None)


conversation_runtime_store = ConversationRuntimeStore()
