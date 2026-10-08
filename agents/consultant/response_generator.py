"""
响应生成器

负责生成AI响应内容
"""

from typing import Dict, Any, AsyncGenerator
from langchain_core.language_models.chat_models import BaseChatModel
from .prompt_builder import PromptBuilder


class ResponseGenerator:
    """响应生成器"""
    
    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.prompt_builder = PromptBuilder()
    
    async def generate_response(self, user_input: str, knowledge_docs: list) -> str:
        """生成标准响应"""
        try:
            prompt = self.prompt_builder.build_consultation_prompt(user_input, knowledge_docs)
            response = await self.llm.ainvoke([{"role": "user", "content": prompt}])
            return self._with_citations(response.content, knowledge_docs)
        except Exception as e:
            return f"抱歉，处理您的问题时出现了错误。请稍后再试。"
    
    async def generate_response_stream(self, user_input: str, knowledge_docs: list) -> AsyncGenerator[str, None]:
        """生成流式响应"""
        try:
            prompt = self.prompt_builder.build_consultation_prompt(user_input, knowledge_docs)
            response = await self.llm.ainvoke([{"role": "user", "content": prompt}])
            content = self._with_citations(response.content, knowledge_docs)
            
            # 只在开头添加一次REPLY标签，然后逐字符输出
            yield "[REPLY][咨询机器人]"
            for char in content:
                yield char
                
        except Exception as e:
            error_msg = f"抱歉，处理您的问题时出现了错误：{str(e)}"
            yield "[REPLY][咨询机器人]"
            for char in error_msg:
                yield char
    
    def create_unrelated_message(self) -> str:
        """创建与咨询无关的回复消息"""
        return "[THOUGHT][咨询机器人] 咨询机器人：这个问题不是咨询类问题，我将转回给归类机器人处理。"

    @staticmethod
    def _source_files(knowledge_docs: list) -> list[str]:
        sources: list[str] = []
        for document in knowledge_docs:
            source = next(
                (
                    keyword.split(":", 1)[1]
                    for keyword in document.get("keywords", [])
                    if isinstance(keyword, str) and keyword.startswith("source:")
                ),
                None,
            )
            if source and source not in sources:
                sources.append(source)
        return sources

    @classmethod
    def _with_citations(cls, content: str, knowledge_docs: list) -> str:
        """Append deterministic citations instead of trusting the model to do so."""
        sources = cls._source_files(knowledge_docs)
        if not sources:
            return content
        citation_lines = "\n".join(f"- [{index}] {source}" for index, source in enumerate(sources, 1))
        return f"{content.rstrip()}\n\n参考来源：\n{citation_lines}"
