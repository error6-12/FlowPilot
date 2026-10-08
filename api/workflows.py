"""Read APIs for persisted enterprise workflow instances."""

from fastapi import APIRouter, HTTPException, Query

from services.workflow_engine import WorkflowEngine


router = APIRouter(prefix="/api/workflows", tags=["企业流程"])


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    engine = WorkflowEngine()
    try:
        workflow = engine.get(workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="流程不存在")
        return workflow
    finally:
        engine.close()


@router.get("")
async def list_workflows(
    conversation_id: str = Query(min_length=1, max_length=128),
    limit: int = Query(default=20, ge=1, le=100),
):
    engine = WorkflowEngine()
    try:
        return {"workflows": engine.list_by_conversation(conversation_id, limit)}
    finally:
        engine.close()
