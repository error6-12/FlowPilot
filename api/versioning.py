"""Read-only version inventory for prompts and runtime configuration."""

from fastapi import APIRouter, HTTPException, Query

from services.prompt_registry import prompt_registry


router = APIRouter(prefix="/api/versions", tags=["Agent 版本治理"])


@router.get("/prompts")
async def list_prompt_versions(
    name: str | None = Query(default=None),
    include_content: bool = Query(default=False),
):
    return {
        "active_versions": prompt_registry.active_versions(),
        "versions": prompt_registry.list_versions(name=name, include_content=include_content),
    }


@router.get("/prompts/{name}/active")
async def get_active_prompt(name: str, include_content: bool = Query(default=False)):
    try:
        return prompt_registry.get_active(name, include_content=include_content)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error))
