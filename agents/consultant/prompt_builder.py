"""
提示词构建器

负责构建各种类型的提示词
"""

from typing import List, Dict, Any
from services.prompt_registry import prompt_registry


class PromptBuilder:
    """提示词构建器"""
    
    def __init__(self):
        self.system_prompt = self._create_system_prompt()
        self.classification_prompt_template = self._create_classification_prompt_template()
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词"""
        return prompt_registry.active_content("consultation_answer")
    
    def _create_classification_prompt_template(self) -> str:
        """创建分类提示词模板"""
        return (
            "你是企业知识咨询分类器。\n"
            "咨询类问题包括公司制度、员工手册、请假或报销规则、IT知识、行政服务和流程说明。\n"
            "创建、提交或修改具体流程的执行请求，以及与企业无关的话题，不属于知识咨询。\n"
            "如果是知识咨询，回答'YES'；否则回答'NO'。\n"
            "只回答YES或NO。\n\n"
            "用户输入：{user_input}"
        )
    
    def build_consultation_prompt(self, user_input: str, knowledge_docs: List[Dict[str, Any]]) -> str:
        """构建咨询提示词"""
        context = self._build_knowledge_context(knowledge_docs)
        return f"{self.system_prompt}\n\n{context}\n用户问题：{user_input}\n\n请回答用户的问题。"
    
    def build_classification_prompt(self, user_input: str) -> str:
        """构建分类提示词"""
        return self.classification_prompt_template.format(user_input=user_input)
    
    def _build_knowledge_context(self, knowledge_docs: List[Dict[str, Any]]) -> str:
        """构建知识库上下文"""
        if not knowledge_docs:
            return "没有找到直接相关的企业知识库信息。请明确说明证据不足，不要自行编造制度。"
        
        context = "\n以下是相关的知识库信息：\n"
        for i, doc in enumerate(knowledge_docs, 1):
            source = next(
                (
                    keyword.split(":", 1)[1]
                    for keyword in doc.get("keywords", [])
                    if keyword.startswith("source:")
                ),
                "未知来源",
            )
            context += f"{i}. [来源：{source}]\n{doc['content']}\n"
        context += "\n请只依据以上资料回答，并在答案末尾列出引用来源。\n"
        
        return context
