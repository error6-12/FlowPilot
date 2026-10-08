"""
智能体路由器 - 专门负责根据分类结果将请求路由到对应的Agent

职责：
1. 接收分类结果，决定使用哪个Agent处理
2. 协调各个Agent之间的调用
3. 管理Agent的初始化和状态同步
4. 提供统一的Agent调用接口
"""

import logging
from typing import Any, AsyncGenerator
from .state_manager import StateManager


logger = logging.getLogger(__name__)


class AgentRouter:
    """智能体路由器 - 根据任务类型路由到对应的处理Agent"""
    
    def __init__(self, appointment_agent: Any, consultant_agent: Any, state_manager: StateManager, workflow_agent: Any = None):
        """
        初始化路由器
        
        Args:
            appointment_agent: 预约处理Agent
            consultant_agent: 咨询处理Agent
            state_manager: 状态管理器
        """
        self.appointment_agent = appointment_agent
        self.consultant_agent = consultant_agent
        self.workflow_agent = workflow_agent
        self.state_manager = state_manager
        
        # 设置Agent的共享状态
        self._setup_agent_states()
    
    def _setup_agent_states(self):
        """设置各Agent的共享状态"""
        if self.appointment_agent and hasattr(self.appointment_agent, 'set_shared_state'):
            self.appointment_agent.set_shared_state(self.state_manager.state)
        
        if self.consultant_agent and hasattr(self.consultant_agent, 'set_shared_state'):
            self.consultant_agent.set_shared_state(self.state_manager.state)

        if self.workflow_agent and hasattr(self.workflow_agent, 'set_shared_state'):
            self.workflow_agent.set_shared_state(self.state_manager.state)

    async def route_to_workflow(self, task: str) -> AsyncGenerator[str, None]:
        if not self.workflow_agent:
            yield "[ERROR]企业流程服务暂时不可用"
            return
        self.state_manager.transition_to_workflow()
        yield "[THOUGHT][归类机器人]这是企业流程任务，转交给流程机器人处理。"
        async for token in self.workflow_agent.run_stream(user_input=task):
            yield token
    
    async def route_to_appointment(self, task: str) -> AsyncGenerator[str, None]:
        """
        路由到预约Agent处理
        
        Args:
            task: 用户任务内容
            
        Yields:
            str: 流式响应内容
        """
        if not self.appointment_agent:
            yield "[ERROR]预约服务暂时不可用"
            return
        
        # 转换状态
        self.state_manager.transition_to_appointment()
        
        # 生成思考提示
        yield "[THOUGHT][归类机器人] 归类机器人：我发现这是一个预约任务，我将转给预约机器人处理。"
        
        # 调用预约Agent
        try:
            async for token in self.appointment_agent.run_stream(user_input=task):
                yield token
        except Exception:
            logger.exception("预约 Agent 处理失败")
            yield "[ERROR]预约服务暂时不可用，请稍后重试。"
            self.state_manager.reset_to_classify()
    
    async def route_to_consultation(self, task: str) -> AsyncGenerator[str, None]:
        """
        路由到咨询Agent处理
        
        Args:
            task: 用户任务内容
            
        Yields:
            str: 流式响应内容
        """
        if not self.consultant_agent:
            yield "[ERROR]咨询服务暂时不可用"
            return
        
        # 转换状态
        self.state_manager.transition_to_consultation()
        
        # 生成思考提示
        yield "[THOUGHT][归类机器人] 归类机器人：我发现这是一个咨询任务，我将转给咨询机器人处理。"
        
        # 调用咨询Agent
        try:
            async with self.consultant_agent as agent:
                async for token in agent.consult_stream(task, allow_handoff=False):
                    yield token
        except Exception:
            logger.exception("咨询 Agent 处理失败")
            yield "[ERROR]知识咨询服务暂时不可用，请稍后重试。"
            self.state_manager.reset_to_classify()
    
    async def handle_unsupported_task(self, category: str, task: str = "") -> AsyncGenerator[str, None]:
        """
        处理不支持的任务类型
        
        Args:
            category: 任务分类结果
            
        Yields:
            str: 回复内容
        """
        normalized = (task or "").strip().lower().replace("！", "").replace("!", "")
        greetings = {"你好", "您好", "hi", "hello", "嗨", "在吗"}
        if normalized in greetings:
            reply = (
                "你好，我是企业智能协作助手。你可以咨询企业制度，"
                "也可以办理请假、报销、IT 工单和会议室预订。请告诉我你需要什么帮助。"
            )
        else:
            reply = (
                "当前暂不支持这类任务。我可以协助企业知识查询、请假申请、费用报销、"
                "IT 工单和会议室预订；请换一种方式描述你的需求。"
            )
        yield "[REPLY][任务协调Agent]"
        for char in reply:
            yield char
    
    async def route_by_state(self, task: str) -> AsyncGenerator[str, None]:
        """
        根据当前状态路由任务（用于状态持续的场景）
        
        Args:
            task: 用户任务内容
            
        Yields:
            str: 流式响应内容
        """
        if self.state_manager.is_in_appointment_flow():
            async for token in self.appointment_agent.run_stream(user_input=task):
                yield token
        elif self.state_manager.is_in_consultation_flow():
            async with self.consultant_agent as agent:
                async for token in agent.consult_stream(task, allow_handoff=False):
                    yield token
        elif self.state_manager.is_in_workflow_flow():
            async for token in self.workflow_agent.run_stream(user_input=task):
                yield token
        else:
            # 状态异常，重置并提示
            self.state_manager.reset_to_classify()
            yield "[ERROR]会话状态异常，已重置。请重新开始对话。"
    
    def get_available_services(self) -> list:
        """获取可用的服务列表"""
        services = []
        if self.appointment_agent:
            services.append("预约服务")
        if self.consultant_agent:
            services.append("咨询服务")
        if self.workflow_agent:
            services.append("企业流程服务")
        return services
