"""
知识库管理API
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel, Field
import asyncio

from services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/knowledge", tags=["知识库管理"])
_knowledge_service: KnowledgeService | None = None
_service_lock = asyncio.Lock()


async def get_knowledge_service() -> KnowledgeService:
    """Return one initialized service so index versions survive API requests."""
    global _knowledge_service
    if _knowledge_service is None:
        async with _service_lock:
            if _knowledge_service is None:
                service = KnowledgeService()
                await service.initialize()
                _knowledge_service = service
    return _knowledge_service


class KnowledgeItem(BaseModel):
    id: int = None
    question: str
    answer: str
    category: str = "general"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    category: str | None = None


@router.get("/")
async def get_all_knowledge():
    """获取所有知识条目"""
    try:
        knowledge_service = await get_knowledge_service()
        entries = knowledge_service.get_all_documents()
        
        # 安全获取categories，避免出错
        try:
            categories = knowledge_service.get_all_categories()
        except Exception as e:
            print(f"获取categories失败: {e}")
            categories = []
        
        return {
            "documents": entries or [],
            "categories": categories or [],
            "total_count": len(entries) if entries else 0,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识库失败: {str(e)}")


@router.get("/index/status")
async def get_index_status():
    """Expose non-sensitive retrieval index metadata for the operations UI."""
    try:
        knowledge_service = await get_knowledge_service()
        return {"status": "success", "data": knowledge_service.get_index_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取索引状态失败: {str(e)}")


@router.get("/{knowledge_id}")
async def get_knowledge(knowledge_id: int):
    """获取特定知识条目"""
    try:
        knowledge_service = await get_knowledge_service()
        entry = knowledge_service.get_document(knowledge_id)
        if not entry:
            raise HTTPException(status_code=404, detail="知识条目不存在")
        return {
            "status": "success",
            "data": entry
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识条目失败: {str(e)}")


@router.post("/")
async def add_knowledge(item: KnowledgeItem):
    """添加新的知识条目"""
    try:
        knowledge_service = await get_knowledge_service()
        # 将问答组合成文档内容
        content = f"问题: {item.question}\n答案: {item.answer}"
        result = await knowledge_service.add_document(
            content=content,
            category=item.category
        )
        return {
            "status": "success",
            "message": "知识条目添加成功",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加知识条目失败: {str(e)}")


@router.put("/{knowledge_id}")
async def update_knowledge(knowledge_id: int, item: KnowledgeItem):
    """更新知识条目"""
    try:
        knowledge_service = await get_knowledge_service()
        # 将问答组合成文档内容
        content = f"问题: {item.question}\n答案: {item.answer}"
        result = await knowledge_service.update_document(
            doc_id=knowledge_id,
            content=content,
            category=item.category
        )
        if not result:
            raise HTTPException(status_code=404, detail="知识条目不存在")
        return {
            "status": "success",
            "message": "知识条目更新成功",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新知识条目失败: {str(e)}")


@router.delete("/{knowledge_id}")
async def delete_knowledge(knowledge_id: int):
    """删除知识条目"""
    try:
        knowledge_service = await get_knowledge_service()
        result = await knowledge_service.delete_document(knowledge_id)
        if not result:
            raise HTTPException(status_code=404, detail="知识条目不存在")
        return {
            "status": "success",
            "message": "知识条目删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除知识条目失败: {str(e)}")


@router.post("/search")
async def search_knowledge(request: SearchRequest):
    """搜索知识库"""
    try:
        knowledge_service = await get_knowledge_service()
        results = await knowledge_service.search(request.query, top_k=request.top_k, category=request.category or None)
        return {
            "status": "success",
            "data": results,
            "count": len(results)
            ,"results": results, "query": request.query, "total_found": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索知识库失败: {str(e)}")
