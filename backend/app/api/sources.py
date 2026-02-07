from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..config import DEFAULT_NOTEBOOK_ID
from ..models import RemoveSourceRequest, SourceListRequest
from ..store import SOURCE_STORE
from ..vector_store import VECTOR_STORE


router = APIRouter()


@router.post("/api/sources")
async def api_sources(payload: SourceListRequest) -> Dict[str, Any]:
    notebook_id = payload.notebookId or DEFAULT_NOTEBOOK_ID
    sources = SOURCE_STORE.list_sources(notebook_id)
    return {
        "notebookId": notebook_id,
        "sources": [source.model_dump() for source in sources],
        "total": len(sources),
    }


@router.post("/api/sources/remove")
async def api_sources_remove(payload: RemoveSourceRequest) -> Dict[str, Any]:
    notebook_id = payload.notebookId or DEFAULT_NOTEBOOK_ID
    removed = SOURCE_STORE.remove_source(notebook_id, payload.sourceId)
    if not removed:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"notebookId": notebook_id, "removed": payload.sourceId}


@router.post("/api/sources/clear")
async def api_sources_clear(payload: SourceListRequest) -> Dict[str, Any]:
    notebook_id = payload.notebookId or DEFAULT_NOTEBOOK_ID
    SOURCE_STORE.clear(notebook_id)
    VECTOR_STORE.delete(notebook_id)
    return {"notebookId": notebook_id, "cleared": True}
