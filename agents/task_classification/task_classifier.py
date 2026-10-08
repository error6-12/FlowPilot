"""
任务分类器 - 专门负责判断用户请求的类型

职责：
1. 接收用户输入，分析其意图
2. 根据预定义的分类规则，将任务归类为：
   - appointment（预约任务）
   - query（查询任务）  
   - pay（支付任务）
   - statistics（统计任务）
   - other（其他任务）
3. 提供清晰的分类结果和置信度
"""

import os

from langchain.prompts import PromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from typing import Any

from .route_decision import AgentTarget, INTENT_TARGETS, RouteDecision, TaskIntent
from .jev_router import JevRouter
from services.prompt_registry import prompt_registry


class TaskClassifier:
    """任务分类器 - 使用LLM进行智能任务分类"""
    
    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.routing_provider = os.getenv("ROUTING_PROVIDER", "deepseek").strip().lower()
        self.jev_fallback_confidence = float(os.getenv("JEV_FALLBACK_CONFIDENCE", "0.2"))
        self.jev_router = JevRouter()
        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.last_shadow_decision: RouteDecision | None = None
        self.legacy_appointment_enabled = os.getenv(
            "ENABLE_LEGACY_APPOINTMENT", "false"
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._initialize_prompt()
        self.chain = self.prompt | self.llm
        # DeepSeek's OpenAI-compatible endpoint currently rejects LangChain's
        # default response_format path. Tool/function calling is supported by
        # both DeepSeek and the other configured providers.
        self.structured_chain = self.prompt | self.llm.with_structured_output(
            RouteDecision,
            method="function_calling",
        )
    
    def _initialize_prompt(self):
        """初始化分类提示词模板"""
        legacy_instructions = (
            "旧按摩门店兼容模式已开启：明确的按摩服务预约可归类为appointment。\n"
            if self.legacy_appointment_enabled
            else (
                "当前运行在企业流程模式。appointment、pay、statistics 是已停用的旧按摩门店类别，"
                "不得输出；会议室、工位、设备等所有资源预订统一归类为workflow。\n"
            )
        )
        self.prompt = PromptTemplate(
            input_variables=["task"],
            template=(
                "你是企业内部流程智能协作平台的任务协调助手，负责识别员工请求并分发给专业Agent。\n"
                "企业员工发起请假、报销、IT工单、会议室或资源预订时，统一归类为workflow。\n"
                "员工咨询企业制度、报销规则、办事指南和内部知识时，归类为query。\n"
                "必须区分“办理动作”和“规则咨询”：用户明确要求代为提交、创建、预订、报销时才是workflow；"
                "用户问“怎么申请、需要什么、能否办理、多少、有哪些步骤、由谁审批”时是query，"
                "即使问题中出现请假、报销、会议室等流程名词也不能直接判为workflow。\n"
                "代码发布、上线、Review、Hotfix、软件使用、IT规范等企业技术制度问题也属于query。\n"
                "普通问候或平台暂不支持的内容归类为other。\n"
                + legacy_instructions +
                "如果输入的任务与上述都无关，请归类为其它任务。\n"
                "请将以下任务归类为以下类别：\n"
                "1. workflow（企业流程任务）\n"
                "2. query（查询任务）\n"
                "3. other（其它任务）\n"
                "同时给出0到1之间的置信度、目标Agent、是否需要澄清以及简短理由。\n"
                "企业流程模式下目标Agent只能是 workflow_agent、consultant_agent 或 unsupported。\n\n"
                "例如：'我要申请明天的年假'输出workflow；'我想休息几天，需要怎么申请'输出query；"
                "'差旅报销标准是什么'输出query；'报销500元交通费'输出workflow；"
                "'上线前到底要几个人看代码'输出query。\n"
                "以下是本次归类任务:\n"
                "任务内容：{task}"
            )
        )
        registry_template = prompt_registry.active_content("routing").replace(
            "{legacy_instructions}", legacy_instructions
        )
        self.prompt = PromptTemplate(input_variables=["task"], template=registry_template)
    
    async def classify(self, task: str) -> RouteDecision:
        """Return a validated routing decision with a safe fallback."""
        if not task or not task.strip():
            return RouteDecision.fallback()

        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        try:
            routing_provider = getattr(self, "routing_provider", "deepseek")
            if routing_provider in {"jev", "jev_hybrid"}:
                try:
                    decision = await self.jev_router.classify(task)
                    self.last_usage = dict(self.jev_router.last_usage)
                    threshold = getattr(self, "jev_fallback_confidence", 0.2)
                    if routing_provider == "jev" or decision.confidence >= threshold:
                        return decision
                except Exception as exc:
                    # Jev is an optimization layer, never a single point of
                    # failure. Fall back to the established LLM classifier.
                    print(f"Jev 路由失败，回退到主分类器: {type(exc).__name__}")
            decision = await self.structured_chain.ainvoke({"task": task})
            if not getattr(self, "legacy_appointment_enabled", False):
                if decision.intent is TaskIntent.APPOINTMENT:
                    decision.intent = TaskIntent.WORKFLOW
                    decision.reasoning = "旧预约类别已停用，已归一化为企业资源流程。"
                elif decision.intent in {TaskIntent.PAY, TaskIntent.STATISTICS}:
                    decision.intent = TaskIntent.OTHER
                    decision.reasoning = "旧按摩门店类别已停用。"
            if decision.target_agent != INTENT_TARGETS[decision.intent]:
                decision.target_agent = INTENT_TARGETS[decision.intent]
            return decision
        except Exception as e:
            print(f"结构化任务分类失败: {str(e)}")
            return RouteDecision.fallback()

    async def classify_task(self, task: str) -> str:
        """
        分类任务
        
        Args:
            task: 用户输入的任务内容
            
        Returns:
            str: 分类结果 ('appointment', 'query', 'pay', 'statistics', 'other')
        """
        try:
            return (await self.classify(task)).intent.value
        except Exception as e:
            print(f"任务分类失败: {str(e)}")
            return TaskIntent.OTHER.value
    
    def get_category_description(self, category: str) -> str:
        """获取分类类别的描述信息"""
        descriptions = {
            'workflow': '企业流程任务 - 请假、报销、IT工单或资源预订',
            'appointment': '旧预约任务（仅在 ENABLE_LEGACY_APPOINTMENT=true 时启用）',
            'query': '知识查询任务 - 企业制度、办事指南和内部资料',
            'pay': '支付任务 - 完成预约后的支付相关事务',
            'statistics': '统计任务 - 工作人员上报工作完成状态',
            'other': '其他任务 - 问候或平台暂不支持的请求'
        }
        return descriptions.get(category, '未知任务类型')
