import pytest

from agents.task_classification.agent_router import AgentRouter
from agents.task_classification.state_manager import StateManager


class FakeConsultant:
    def __init__(self):
        self.allow_handoff_values = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def consult_stream(self, task, allow_handoff=True):
        self.allow_handoff_values.append(allow_handoff)
        yield "answer"


@pytest.mark.asyncio
async def test_supervisor_to_consultant_disables_reverse_handoff():
    consultant = FakeConsultant()
    router = AgentRouter(None, consultant, StateManager())

    output = []
    async for token in router.route_to_consultation("公司的年假制度是什么？"):
        output.append(token)

    assert "answer" in output
    assert consultant.allow_handoff_values == [False]
