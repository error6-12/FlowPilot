import pytest

from agents.workflow import (
    WorkflowAction,
    WorkflowDraft,
    WorkflowExtraction,
    WorkflowStatus,
    WorkflowType,
)
from agents.workflow_agent import WorkflowAgent


class FakeExtractionChain:
    def __init__(self, *results):
        self.results = list(results)
        self.inputs = []

    async def ainvoke(self, payload):
        self.inputs.append(payload)
        return self.results.pop(0)


class FakeWorkflowEngine:
    def __init__(self):
        self.saved = []

    def save_draft(self, draft, conversation_id):
        if draft.workflow_id is None:
            draft.workflow_id = "WF-TEST000001"
        self.saved.append(("save", conversation_id, draft.model_copy(deep=True)))
        return draft

    def submit(self, draft, conversation_id):
        if draft.workflow_id is None:
            self.save_draft(draft, conversation_id)
        draft.status = WorkflowStatus.SUBMITTED
        self.saved.append(("submit", conversation_id, draft.model_copy(deep=True)))
        return draft

    def cancel(self, draft, conversation_id):
        draft.status = WorkflowStatus.CANCELLED
        self.saved.append(("cancel", conversation_id, draft.model_copy(deep=True)))
        return draft


def make_agent(chain):
    return WorkflowAgent(extraction_chain=chain, workflow_engine=FakeWorkflowEngine())


@pytest.mark.asyncio
async def test_semantic_extraction_builds_reimbursement_draft():
    chain = FakeExtractionChain(
        WorkflowExtraction(
            workflow_type=WorkflowType.REIMBURSEMENT,
            amount=500,
            expense_type="差旅",
            description="客户现场交通费用",
        )
    )
    draft = await make_agent(chain).create_draft("这500块是去客户现场的")

    assert draft.fields["amount"] == 500
    assert draft.status is WorkflowStatus.READY_FOR_CONFIRMATION


@pytest.mark.asyncio
async def test_semantic_extraction_reports_missing_fields():
    chain = FakeExtractionChain(WorkflowExtraction(workflow_type=WorkflowType.LEAVE))
    draft = await make_agent(chain).create_draft("我想休息几天")

    assert draft.missing_fields == ["start_date", "end_date", "reason"]


@pytest.mark.asyncio
async def test_agent_understands_chinese_time_followup_from_screenshot():
    chain = FakeExtractionChain(
        WorkflowExtraction(
            workflow_type=WorkflowType.RESOURCE_BOOKING,
            resource="A301会议室",
        ),
        WorkflowExtraction(
            workflow_type=WorkflowType.RESOURCE_BOOKING,
            start_time="14:00",
            end_time="16:00",
            assumptions=["未说明上午/下午，按工作时间推定为下午"],
        ),
    )
    agent = make_agent(chain)
    await agent.create_draft("帮我预订A301会议室")
    draft = await agent.create_draft("开始时间，两点，结束时间，四点")

    assert draft.fields["resource"] == "A301会议室"
    assert draft.fields["start_time"] == "14:00"
    assert draft.fields["end_time"] == "16:00"
    assert draft.status is WorkflowStatus.READY_FOR_CONFIRMATION
    assert draft.assumptions
    assert "A301会议室" in chain.inputs[1]["current_draft"]


@pytest.mark.asyncio
async def test_model_failure_preserves_existing_draft():
    class FailingChain:
        async def ainvoke(self, payload):
            raise RuntimeError("provider unavailable")

    agent = make_agent(FailingChain())
    agent.current_draft = WorkflowDraft.build(
        WorkflowType.IT_SUPPORT,
        {"issue_description": "无法联网"},
    )
    result = await agent.create_draft("很紧急")

    assert result is agent.current_draft
    assert result.fields["issue_description"] == "无法联网"


@pytest.mark.asyncio
async def test_confirmation_submits_ready_draft_with_workflow_id():
    chain = FakeExtractionChain(
        WorkflowExtraction(
            workflow_type=WorkflowType.RESOURCE_BOOKING,
            user_action=WorkflowAction.CONFIRM,
        )
    )
    agent = make_agent(chain)
    agent.current_draft = WorkflowDraft.build(
        WorkflowType.RESOURCE_BOOKING,
        {"resource": "A301会议室", "start_time": "14:00", "end_time": "16:00"},
    )

    draft = await agent.create_draft("对的")

    assert draft.status is WorkflowStatus.SUBMITTED
    assert draft.workflow_id.startswith("WF-")


@pytest.mark.asyncio
async def test_cancel_does_not_submit_workflow():
    chain = FakeExtractionChain(
        WorkflowExtraction(
            workflow_type=WorkflowType.RESOURCE_BOOKING,
            user_action=WorkflowAction.CANCEL,
        )
    )
    agent = make_agent(chain)
    agent.current_draft = WorkflowDraft.build(
        WorkflowType.RESOURCE_BOOKING,
        {"resource": "A301会议室", "start_time": "14:00", "end_time": "16:00"},
    )

    draft = await agent.create_draft("算了，不订了")

    assert draft.status is WorkflowStatus.CANCELLED
    assert draft.workflow_id.startswith("WF-")


@pytest.mark.asyncio
async def test_duplicate_confirmation_keeps_submitted_workflow_terminal():
    chain = FakeExtractionChain(
        WorkflowExtraction(
            workflow_type=WorkflowType.IT_SUPPORT,
            user_action=WorkflowAction.CONFIRM,
        )
    )
    agent = make_agent(chain)
    agent.current_draft = WorkflowDraft(
        workflow_type=WorkflowType.IT_SUPPORT,
        fields={"issue_description": "电脑无法开机", "urgency": "紧急"},
        missing_fields=[],
        status=WorkflowStatus.SUBMITTED,
        workflow_id="WF-TEST000001",
    )

    draft = await agent.create_draft("确认")

    assert draft.status is WorkflowStatus.SUBMITTED
    assert draft.workflow_id == "WF-TEST000001"
    assert chain.inputs == []


@pytest.mark.asyncio
async def test_tool_adapter_drops_fields_outside_target_schema():
    chain = FakeExtractionChain(
        WorkflowExtraction(
            workflow_type=WorkflowType.RESOURCE_BOOKING,
            resource="A301会议室",
            start_date="明天",
            start_time="14:00",
            end_time="16:00",
            user_action=WorkflowAction.CONFIRM,
        )
    )
    agent = make_agent(chain)

    draft = await agent.create_draft("预订A301会议室，明天下午两点到四点并确认")

    assert draft.status is WorkflowStatus.SUBMITTED
    assert agent.last_tool_result.success is True
