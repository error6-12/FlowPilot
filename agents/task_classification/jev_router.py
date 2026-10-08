"""TypeSafe Jev adapter for compact, typed Agent routing decisions."""

from __future__ import annotations

import os
from typing import Any

import aiohttp

from .route_decision import AgentTarget, RouteDecision, TaskIntent


class JevRoutingError(RuntimeError):
    """Raised when Jev cannot produce a valid routing decision."""


class JevRouter:
    """Call System One with one Choice question and expose usage metadata."""

    def __init__(self) -> None:
        self.api_key = os.getenv("TYPESAFE_API_KEY", "").strip()
        self.base_url = os.getenv(
            "JEV_BASE_URL", "https://api.typesafe.ai/v1/systemone"
        ).strip()
        self.model = os.getenv("JEV_MODEL", "jev-latest").strip()
        self.timeout_seconds = float(os.getenv("JEV_TIMEOUT_SECONDS", "15"))
        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def build_payload(self, task: str) -> dict[str, Any]:
        return {
            "state": task,
            "model": self.model,
            "questions": {
                "route": {
                    "type": "choice",
                    "instructions": (
                        "选择应处理该员工消息的目标。区分办理动作与规则咨询；"
                        "明确提交/创建/预订，或已完整表达需办理的请假、报障事实时选择 workflow_agent；"
                        "缺少对象和上下文的孤立指令、个人提醒以及平台范围外能力选择 unsupported。"
                    ),
                    "criteria": {
                        "workflow_agent": (
                            "请假、报销、IT故障报修、会议室/工位/设备预订等可执行请求；"
                            "允许口语省略动作词，例如说明断网故障，或说明哪天因私不来"
                        ),
                        "consultant_agent": (
                            "企业制度、规则、步骤、条件、知识或资源信息查询"
                        ),
                        "unsupported": (
                            "问候、闲聊、个人提醒等平台范围外请求；或仅说取消、照办、"
                            "订一个东西等缺少必要对象/上下文、当前无法可靠执行的指令"
                        ),
                    },
                }
            },
        }

    async def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise JevRoutingError("TYPESAFE_API_KEY is not configured")
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.base_url, headers=headers, json=payload) as response:
                body = await response.json(content_type=None)
                if response.status >= 400:
                    raise JevRoutingError(f"Jev HTTP {response.status}: {body}")
                return body

    async def classify(self, task: str) -> RouteDecision:
        body = await self._post_json(self.build_payload(task))
        answer = body.get("answers", {}).get("route", {})
        choice = answer.get("choice")
        target_map = {
            "workflow_agent": (TaskIntent.WORKFLOW, AgentTarget.WORKFLOW),
            "consultant_agent": (TaskIntent.QUERY, AgentTarget.CONSULTANT),
            "unsupported": (TaskIntent.OTHER, AgentTarget.UNSUPPORTED),
        }
        if choice not in target_map:
            raise JevRoutingError(f"Invalid Jev route choice: {choice!r}")

        usage = body.get("usage", {})
        prompt_tokens = int(usage.get("input_tokens", 0) or 0)
        completion_tokens = int(usage.get("output_tokens", 0) or 0)
        self.last_usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        intent, target = target_map[choice]
        return RouteDecision(
            intent=intent,
            target_agent=target,
            confidence=float(answer.get("confidence", 0.0) or 0.0),
            needs_clarification=False,
            reasoning=f"Jev typed decision: {choice}",
        )
