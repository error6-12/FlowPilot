"""
简化的任务分类API

只保留第一版核心功能
"""
from fastapi import APIRouter, HTTPException
from .core.response_models import (
    TaskClassificationRequest,
    TaskClassificationResponse,
    DataResponse
)

router = APIRouter(prefix="/api/task", tags=["任务分类"])


@router.post("/classify", response_model=DataResponse)
async def classify_task(request: TaskClassificationRequest):
    """分类任务"""
    try:
        from agents.task_classification.task_classifier import TaskClassifier
        from config.model_provider import create_chat_model

        classifier = TaskClassifier(create_chat_model(temperature=0))
        result = await classifier.classify(request.text)
        
        return DataResponse(
            message="任务分类成功",
            data=result.model_dump(mode="json")
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
