import pytest
from pydantic import ValidationError

from agents.task_classification.route_decision import (
    AgentTarget,
    RouteDecision,
    TaskIntent,
)
from agents.task_classification.task_classifier import TaskClassifier


class FakeStructuredChain:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    async def ainvoke(self, payload):
        if self.error:
            raise self.error
        return self.result


def test_route_decision_accepts_valid_structured_output():
    decision = RouteDecision(
        intent=TaskIntent.QUERY,
        target_agent=AgentTarget.CONSULTANT,
        confidence=0.94,
        reasoning="用户正在咨询服务信息",
    )

    assert decision.intent.value == "query"
    assert decision.target_agent.value == "consultant_agent"
    assert decision.needs_clarification is False


def test_route_decision_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        RouteDecision(
            intent=TaskIntent.QUERY,
            target_agent=AgentTarget.CONSULTANT,
            confidence=1.5,
        )


def test_route_decision_has_safe_fallback():
    decision = RouteDecision.fallback()

    assert decision.intent is TaskIntent.OTHER
    assert decision.target_agent is AgentTarget.UNSUPPORTED
    assert decision.confidence == 0
    assert decision.needs_clarification is True


def test_workflow_intent_routes_to_workflow_agent():
    decision = RouteDecision(
        intent=TaskIntent.WORKFLOW,
        target_agent=AgentTarget.WORKFLOW,
        confidence=0.96,
        reasoning="员工正在申请报销",
    )

    assert decision.target_agent is AgentTarget.WORKFLOW


@pytest.mark.asyncio
async def test_classifier_corrects_mismatched_target_agent():
    classifier = TaskClassifier.__new__(TaskClassifier)
    classifier.structured_chain = FakeStructuredChain(
        RouteDecision(
            intent=TaskIntent.QUERY,
            target_agent=AgentTarget.APPOINTMENT,
            confidence=0.9,
        )
    )

    decision = await classifier.classify("公司的服务价格是多少？")

    assert decision.intent is TaskIntent.QUERY
    assert decision.target_agent is AgentTarget.CONSULTANT


@pytest.mark.asyncio
async def test_classifier_falls_back_when_model_output_fails():
    classifier = TaskClassifier.__new__(TaskClassifier)
    classifier.structured_chain = FakeStructuredChain(error=RuntimeError("bad output"))

    decision = await classifier.classify("无法解析的请求")

    assert decision.intent is TaskIntent.OTHER
    assert decision.target_agent is AgentTarget.UNSUPPORTED


@pytest.mark.asyncio
async def test_classifier_normalizes_legacy_appointment_to_enterprise_workflow():
    classifier = TaskClassifier.__new__(TaskClassifier)
    classifier.legacy_appointment_enabled = False
    classifier.structured_chain = FakeStructuredChain(
        RouteDecision(
            intent=TaskIntent.APPOINTMENT,
            target_agent=AgentTarget.APPOINTMENT,
            confidence=0.9,
        )
    )

    decision = await classifier.classify("A301两点到四点给我留着")

    assert decision.intent is TaskIntent.WORKFLOW
    assert decision.target_agent is AgentTarget.WORKFLOW
