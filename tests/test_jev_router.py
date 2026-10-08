import pytest

from agents.task_classification.jev_router import JevRouter, JevRoutingError
from agents.task_classification.route_decision import AgentTarget, TaskIntent
from agents.task_classification.task_classifier import TaskClassifier


@pytest.mark.asyncio
async def test_jev_router_maps_choice_and_usage(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only")
    router = JevRouter()

    async def fake_post(_payload):
        return {
            "answers": {
                "route": {
                    "type": "choice",
                    "choice": "workflow_agent",
                    "confidence": 0.91,
                    "probabilities": {"workflow_agent": 0.94},
                }
            },
            "usage": {"input_tokens": 120, "output_tokens": 18},
        }

    monkeypatch.setattr(router, "_post_json", fake_post)
    decision = await router.classify("帮我预订明天下午的会议室")
    assert decision.intent is TaskIntent.WORKFLOW
    assert decision.target_agent is AgentTarget.WORKFLOW
    assert decision.confidence == pytest.approx(0.91)
    assert router.last_usage["total_tokens"] == 138


def test_jev_payload_keeps_three_enterprise_targets(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only")
    criteria = JevRouter().build_payload("测试")["questions"]["route"]["criteria"]
    assert set(criteria) == {"workflow_agent", "consultant_agent", "unsupported"}


@pytest.mark.asyncio
async def test_jev_router_rejects_unknown_choice(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only")
    router = JevRouter()

    async def fake_post(_payload):
        return {"answers": {"route": {"choice": "unknown"}}, "usage": {}}

    monkeypatch.setattr(router, "_post_json", fake_post)
    with pytest.raises(JevRoutingError):
        await router.classify("测试")


@pytest.mark.asyncio
async def test_hybrid_router_falls_back_on_low_confidence():
    class FakeJev:
        last_usage = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}

        async def classify(self, _task):
            from agents.task_classification.route_decision import RouteDecision

            return RouteDecision(
                intent=TaskIntent.WORKFLOW,
                target_agent=AgentTarget.WORKFLOW,
                confidence=0.1,
            )

    class FakeChain:
        async def ainvoke(self, _payload):
            from agents.task_classification.route_decision import RouteDecision

            return RouteDecision(
                intent=TaskIntent.QUERY,
                target_agent=AgentTarget.CONSULTANT,
                confidence=0.9,
            )

    classifier = TaskClassifier.__new__(TaskClassifier)
    classifier.routing_provider = "jev_hybrid"
    classifier.jev_fallback_confidence = 0.2
    classifier.jev_router = FakeJev()
    classifier.structured_chain = FakeChain()
    classifier.legacy_appointment_enabled = False
    classifier.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    decision = await classifier.classify("同事让我代他请假，可以吗")
    assert decision.intent is TaskIntent.QUERY
    assert classifier.last_usage["total_tokens"] == 120
