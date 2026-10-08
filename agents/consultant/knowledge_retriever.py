"""
知识检索器

负责从知识库中检索相关信息
"""

import logging
from typing import List, Dict, Any
from services.knowledge_service import KnowledgeService


logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """知识检索器"""
    
    def __init__(self):
        self.knowledge_service = KnowledgeService()
        self.kb_initialized = False
    
    async def initialize(self):
        """初始化知识库服务"""
        if not self.kb_initialized:
            await self.knowledge_service.initialize()
            self.kb_initialized = True
            logger.info("咨询机器人知识库服务已初始化")
    
    async def search_knowledge(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """搜索相关知识"""
        # 确保知识库已初始化
        if not self.kb_initialized:
            await self.initialize()
        
        # 搜索相关知识
        retrieval_query = self._expand_retrieval_query(query)
        relevant_docs = await self.knowledge_service.search(retrieval_query, top_k=top_k)
        
        # 记录检索日志
        self._log_search_results(query, relevant_docs)
        
        return relevant_docs or []

    @staticmethod
    def _expand_retrieval_query(query: str) -> str:
        """Add retrieval-only context for short resource availability questions.

        Relative expressions such as ``明天哪些会议室有空`` contain little
        lexical overlap with a booking snapshot.  The original question is
        still passed unchanged to the answer model; this expansion only helps
        hybrid retrieval select the operational snapshot instead of generic
        meeting-room rules.
        """
        normalized = (query or "").strip()
        has_meeting_room = "会议室" in normalized
        has_availability = any(
            term in normalized
            for term in ("有空", "空闲", "可用", "占用", "排期", "预约情况")
        )
        has_time = any(
            term in normalized
            for term in (
                "当前", "现在", "今天", "明天", "后天", "星期", "周一", "周二",
                "周三", "周四", "周五", "周六", "周日", "上午", "下午", "晚上",
                "点", "时", "2026-10-",
            )
        )
        if has_meeting_room and has_availability and has_time:
            return (
                f"{normalized} 会议室一周占用快照 演示基准时间 "
                "已确认预订记录 当前空闲 可用会议室"
            )
        return normalized
    
    def _log_search_results(self, query: str, relevant_docs: List[Dict[str, Any]]):
        """记录搜索结果日志"""
        if relevant_docs:
            logger.info("知识库检索结果 query=%r count=%s", query, len(relevant_docs))
            for i, doc in enumerate(relevant_docs, 1):
                score = doc.get('score', 0)
                category = doc.get('category', '未知')
                content = doc.get('content', '')[:80]
                logger.debug(
                    "检索结果 rank=%s score=%.3f category=%s preview=%s",
                    i,
                    score,
                    category,
                    content,
                )
            logger.info("知识库统计 count=%s", len(relevant_docs))
        else:
            logger.warning("知识库未找到相关内容 query=%r", query)
