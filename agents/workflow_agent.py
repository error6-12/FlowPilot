"""LLM-driven enterprise workflow Agent with typed validation."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from langchain.prompts import PromptTemplate

from agents.workflow import (
    WorkflowAction,
    WorkflowDraft,
    WorkflowExtraction,
    WorkflowStatus,
    WorkflowType,
)
from config.model_provider import create_chat_model
from services.enterprise_tools import (
    INPUT_MODEL_BY_WORKFLOW_TYPE,
    TOOL_BY_WORKFLOW_TYPE,
    create_workflow_tool_registry,
)
from services.workflow_engine import WorkflowEngine
from services.workflow_validation import validate_workflow
from services.prompt_registry import prompt_registry


WORKFLOW_LABELS = {
    WorkflowType.LEAVE: "请假申请",
    WorkflowType.REIMBURSEMENT: "费用报销",
    WorkflowType.IT_SUPPORT: "IT 工单",
    WorkflowType.RESOURCE_BOOKING: "资源预订",
    WorkflowType.UNKNOWN: "企业流程",
}

FIELD_LABELS = {
    "start_date": "开始日期",
    "end_date": "结束日期",
    "reason": "请假原因",
    "amount": "报销金额",
    "expense_type": "费用类型",
    "description": "费用说明",
    "issue_description": "故障描述",
    "urgency": "紧急程度",
    "resource": "资源名称",
    "start_time": "开始时间",
    "end_time": "结束时间",
}


EXTRACTION_PROMPT = PromptTemplate.from_template(
    """你是企业流程 Agent 的语义理解模块。请结合已有流程草稿理解用户最新一句话，
输出符合 WorkflowExtraction Schema 的结构化结果。

支持的流程：leave（请假）、reimbursement（费用报销）、it_support（IT 工单）、
resource_booking（会议室或资源预订）、unknown（确实无法判断）。

理解原则：
1. 结合已有草稿理解省略表达，不要求用户重复流程名称或已有字段。
2. 理解自然中文、口语、中文数字、相对时间和字段标签，不依赖固定关键词格式。
3. 只提取用户已经表达或可由上下文合理推断的字段，不捏造人员、金额或原因。
4. 企业工作时间语境中，单独出现“两点到四点”可规范为14:00到16:00，
   但必须在 assumptions 中记录“未说明上午/下午，按工作时间推定为下午”。
5. 用户纠正字段时输出新值；未提到的已有字段保持为 null，由系统负责合并。
6. 如果已有草稿类型明确，用户只是在补充字段，workflow_type 必须沿用已有类型。
7. 当已有草稿状态为 ready_for_confirmation 时：
   - “对、对的、正确、确认、可以、提交”等肯定回复输出 user_action=confirm；
   - “取消、不要了、算了”等输出 user_action=cancel；
   - 用户提出字段改动时输出 user_action=modify，并只填写发生变化的字段。
   其他情况下 user_action=none。不要仅依赖固定词，要理解语义和上下文。

已有流程草稿：
{current_draft}

用户最新输入：
{user_input}
"""
)
EXTRACTION_PROMPT = PromptTemplate.from_template(
    prompt_registry.active_content("workflow_extraction")
)


class WorkflowAgent:
    def __init__(
        self,
        session_id: str = "default",
        extraction_chain=None,
        workflow_engine=None,
        tool_registry=None,
    ):
        self.session_id = session_id
        self.current_draft: WorkflowDraft | None = None
        self.shared_state = None
        self.workflow_engine = workflow_engine or WorkflowEngine()
        self.tool_registry = tool_registry or create_workflow_tool_registry(self.workflow_engine)
        self.last_tool_result = None
        if extraction_chain is None:
            llm = create_chat_model(temperature=0)
            extraction_chain = EXTRACTION_PROMPT | llm.with_structured_output(
                WorkflowExtraction,
                method="function_calling",
            )
        self.extraction_chain = extraction_chain

    def set_shared_state(self, shared_state) -> None:
        self.shared_state = shared_state

    def reset(self) -> None:
        self.current_draft = None

    def _draft_context(self) -> str:
        if self.current_draft is None:
            return "尚未创建流程草稿"
        return json.dumps(self.current_draft.model_dump(mode="json"), ensure_ascii=False)

    async def create_draft(self, text: str) -> WorkflowDraft:
        """Use semantic extraction and merge only validated non-empty fields."""
        # Terminal workflow operations are idempotent. A delayed or duplicated
        # confirmation must not rebuild a submitted/cancelled draft and move it
        # back to ready_for_confirmation.
        if self.current_draft and self.current_draft.status in {
            WorkflowStatus.SUBMITTED,
            WorkflowStatus.CANCELLED,
        }:
            return self.current_draft

        try:
            extraction = await self.extraction_chain.ainvoke(
                {"current_draft": self._draft_context(), "user_input": text}
            )
            if not isinstance(extraction, WorkflowExtraction):
                extraction = WorkflowExtraction.model_validate(extraction)
        except Exception:
            if self.current_draft is not None:
                return self.current_draft
            return WorkflowDraft.build(WorkflowType.UNKNOWN, {})

        workflow_type = extraction.workflow_type
        if workflow_type is WorkflowType.UNKNOWN and self.current_draft is not None:
            workflow_type = self.current_draft.workflow_type

        fields = (
            dict(self.current_draft.fields)
            if self.current_draft and self.current_draft.workflow_type is workflow_type
            else {}
        )
        fields.update(extraction.extracted_fields())
        previous_workflow_id = self.current_draft.workflow_id if self.current_draft else None
        self.current_draft = WorkflowDraft.build(
            workflow_type,
            fields,
            assumptions=extraction.assumptions,
        )
        self.current_draft.workflow_id = previous_workflow_id

        if extraction.user_action is WorkflowAction.CONFIRM:
            try:
                validate_workflow(self.current_draft.workflow_type, self.current_draft.fields)
            except ValueError:
                return self.workflow_engine.save_draft(self.current_draft, self.session_id)
            self.last_tool_result = await self._submit_with_tool(self.current_draft)
            if self.last_tool_result.success:
                self.current_draft.status = WorkflowStatus.SUBMITTED
            else:
                self.current_draft = self.workflow_engine.save_draft(
                    self.current_draft,
                    self.session_id,
                )
        elif extraction.user_action is WorkflowAction.CANCEL:
            if self.current_draft.workflow_id is None:
                self.current_draft = self.workflow_engine.save_draft(
                    self.current_draft,
                    self.session_id,
                )
            self.current_draft = self.workflow_engine.cancel(
                self.current_draft,
                self.session_id,
            )
        else:
            self.current_draft = self.workflow_engine.save_draft(
                self.current_draft,
                self.session_id,
            )
        return self.current_draft

    async def _submit_with_tool(self, draft: WorkflowDraft):
        """Submit a validated draft through the governed execution boundary."""
        tool_name = TOOL_BY_WORKFLOW_TYPE.get(draft.workflow_type)
        if tool_name is None or draft.status is not WorkflowStatus.READY_FOR_CONFIRMATION:
            from services.tool_registry import ToolExecutionResult

            return ToolExecutionResult(
                tool_name=tool_name or "unknown_workflow_tool",
                success=False,
                error="workflow_not_ready",
            )

        if draft.workflow_id is None:
            draft = self.workflow_engine.save_draft(draft, self.session_id)
            self.current_draft = draft
        input_model = INPUT_MODEL_BY_WORKFLOW_TYPE[draft.workflow_type]
        allowed_fields = set(input_model.model_fields) - {"workflow_id", "conversation_id"}
        payload = {
            "workflow_id": draft.workflow_id,
            "conversation_id": self.session_id,
            **{key: value for key, value in draft.fields.items() if key in allowed_fields},
        }
        return await self.tool_registry.execute(
            tool_name,
            payload,
            permissions={"workflow:submit"},
            idempotency_key=draft.workflow_id,
            trace_id=self.session_id,
        )

    async def run_stream(self, user_input: str) -> AsyncGenerator[str, None]:
        draft = await self.create_draft(user_input)
        label = WORKFLOW_LABELS[draft.workflow_type]
        yield f"[THOUGHT][流程机器人]已识别流程类型：{label}。"

        if draft.status is WorkflowStatus.SUBMITTED:
            yield (
                f"[REPLY][流程机器人]{label}已提交成功，"
                f"流程编号：{draft.workflow_id}。你可以使用该编号查询后续状态。"
            )
            self._finish_workflow()
            return

        if draft.status is WorkflowStatus.CANCELLED:
            yield f"[REPLY][流程机器人]已取消当前{label}草稿，未提交任何流程。"
            self._finish_workflow()
            return

        if draft.workflow_type is WorkflowType.UNKNOWN:
            yield "[REPLY][流程机器人]我暂时无法确定要办理的流程，请再描述一下你的目标。"
            return

        if draft.missing_fields:
            missing = "、".join(FIELD_LABELS[field] for field in draft.missing_fields)
            yield f"[REPLY][流程机器人]已创建{label}草稿，还需要补充：{missing}。"
            return

        try:
            validate_workflow(draft.workflow_type, draft.fields)
        except ValueError as error:
            yield f"[REPLY][流程机器人]{error} 当前仍为草稿，未提交。"
            return

        summary = "、".join(
            f"{('设备与位置说明' if key == 'description' and draft.workflow_type is WorkflowType.IT_SUPPORT else FIELD_LABELS.get(key, key))}：{value}" for key, value in draft.fields.items()
            if value is not None and key in FIELD_LABELS
        )
        if draft.assumptions:
            assumptions = "；".join(draft.assumptions)
            yield (
                f"[REPLY][流程机器人]{label}信息已收集完整：{summary}。"
                f"我做了以下理解：{assumptions}。请确认是否正确。"
            )
            return

        yield f"[REPLY][流程机器人]{label}信息已收集完整：{summary}。请确认后提交。"

    def _finish_workflow(self) -> None:
        self.current_draft = None
        if self.shared_state:
            from config.constants import StateEnum

            self.shared_state.value = StateEnum.CLASSIFY
