import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..config import CHUNK_OVERLAP, CHUNK_SIZE, MAX_SOURCE_CHARS, SEARCH_TOP_K
from ..embeddings import embed_query, embed_texts
from ..models import NotebookRequest, SearchRequest
from ..store import SOURCE_STORE
from ..utils import build_chunks_from_sources
from ..vector_store import VECTOR_STORE


router = APIRouter()


@router.post("/api/index")
async def api_index(payload: NotebookRequest) -> Dict[str, Any]:
    sources = payload.sources
    if not sources:
        sources = SOURCE_STORE.list_sources(payload.notebookId)
    if not sources:
        raise HTTPException(status_code=400, detail="No sources available for indexing")

    try:
        chunks = build_chunks_from_sources(
            sources,
            max_chars=MAX_SOURCE_CHARS,
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    texts = [chunk["text"] for chunk in chunks]
    try:
        embeddings = await embed_texts(texts)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if len(embeddings) != len(chunks):
        raise HTTPException(status_code=500, detail="Embeddings count mismatch")

    VECTOR_STORE.replace(payload.notebookId, embeddings, chunks)
    SOURCE_STORE.set_sources(payload.notebookId, sources)
    dimension = len(embeddings[0]) if embeddings else 0
    return {
        "notebookId": payload.notebookId,
        "indexedAt": int(time.time() * 1000),
        "chunks": len(chunks),
        "dimension": dimension,
    }


@router.post("/api/search")
async def api_search(payload: SearchRequest) -> Dict[str, Any]:
    if not payload.query:
        raise HTTPException(status_code=400, detail="Query is required")

    if not VECTOR_STORE.has(payload.notebookId):
        raise HTTPException(status_code=404, detail="Notebook index not found")

    try:
        query_embedding = await embed_query(payload.query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    top_k = payload.topK or SEARCH_TOP_K
    results = VECTOR_STORE.search(payload.notebookId, query_embedding, top_k)
    formatted = []
    for score, meta in results:
        formatted.append(
            {
                "score": score,
                "text": meta.get("text", ""),
                "source": {
                    "id": meta.get("source_id"),
                    "url": meta.get("source_url"),
                    "title": meta.get("source_title"),
                    "index": meta.get("source_index"),
                    "chunkIndex": meta.get("chunk_index"),
                },
            }
        )

    return {
        "notebookId": payload.notebookId,
        "query": payload.query,
        "results": formatted,
        "total": len(formatted),
    }
