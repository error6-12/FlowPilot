from dotenv import load_dotenv
from config.model_provider import create_chat_model
from config.constants import SharedState, StateEnum
from .task_classification import (
    TaskClassifier,
    StateManager,
    AgentRouter,
    UnrelatedHandler,
    ClassificationProcessor
)

load_dotenv()


class TaskClassificationAgent:
    """
    任务分类代理主控制器
    
    职责：
    1. 初始化各个分类组件
    2. 提供统一的任务分类接口
    3. 管理与其他Agent的协调
    """
    
    def __init__(self, appointment_agent, consultant_agent, workflow_agent=None):
        # 基础设置
        self.appointment_agent = appointment_agent
        self.consultant_agent = consultant_agent
        self.workflow_agent = workflow_agent
        self._handoff_depth = 0
        
        # 初始化LLM
        self.llm = self._initialize_llm()
        
        # 初始化组件
        self.state_manager = StateManager(SharedState())
        self.task_classifier = TaskClassifier(self.llm)
        self.agent_router = AgentRouter(
            appointment_agent, 
            consultant_agent, 
            self.state_manager,
            workflow_agent,
        )
        self.unrelated_handler = UnrelatedHandler(self.state_manager)
        self.classification_processor = ClassificationProcessor(
            self.task_classifier,
            self.state_manager,
            self.agent_router,
            self.unrelated_handler
        )
        
        # 设置回调函数
        self._setup_callbacks()
        
        # 保持向后兼容的state属性
        self.state = self.state_manager.state

    def _initialize_llm(self):
        """初始化通用聊天模型"""
        return create_chat_model(temperature=0)
    
    def _setup_callbacks(self):
        """设置Agent的回调函数"""
        if self.appointment_agent and hasattr(self.appointment_agent, 'unrelated_callback'):
            self.appointment_agent.unrelated_callback = self.handle_unrelated
        
        # Enterprise agents return control to the supervisor through a single
        # structured result. Reverse callbacks are intentionally disabled to
        # prevent agent-to-agent loops. The appointment callback remains only
        # as a temporary legacy compatibility path.

    # ===========================================
    # 主要接口方法 - 保持与原版本的兼容性
    # ===========================================
    
    async def classify_task(self, task):
        """分类任务（向后兼容方法）"""
        return await self.classification_processor.process_task_sync(task)

    async def classify_task_stream(self, task):
        """流式分类任务（主要入口）"""
        async for token in self.classification_processor.process_task_stream(task):
            yield token

    async def handle_unrelated(self, user_input):
        """处理无关请求（同步版本）"""
        # 与预约无关的请求应该重新进行分类，而不是直接拒绝
        print(f"[DEBUG] 预约机器人转交的请求：{user_input}")
        
        # 重新进行任务分类
        result = ""
        async for token in self.classification_processor.process_task_stream(user_input):
            result += token
        return result

    async def handle_unrelated_async(self, user_input):
        """处理无关请求（异步流版本）"""
        # 与预约无关的请求应该重新进行分类，而不是直接拒绝
        print(f"[DEBUG] 预约机器人转交的请求：{user_input}")
        
        if self._handoff_depth >= 1:
            yield (
                "[REPLY][任务协调Agent]当前任务在专业 Agent 之间无法确定归属，"
                "已停止继续转交。请补充更具体的企业知识或流程需求。"
            )
            self.state_manager.force_reset()
            return

        self._handoff_depth += 1
        try:
            async for token in self.classification_processor.process_task_stream(user_input):
                yield token
        finally:
            self._handoff_depth -= 1

    # ===========================================
    # 扩展功能方法
    # ===========================================
    
    def get_classification_info(self):
        """获取分类系统信息"""
        return self.classification_processor.get_current_state_info()
    
    def reset_conversation(self):
        """重置对话状态"""
        self.classification_processor.reset_conversation()
        if self.workflow_agent:
            self.workflow_agent.reset()
    
    def set_business_context(self, service_name: str = "企业内部流程与知识服务"):
        """设置业务上下文"""
        self.unrelated_handler.set_business_context(service_name)
