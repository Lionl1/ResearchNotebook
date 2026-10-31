import base64
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..config import CHAT_CONTEXT_CHAR_BUDGET, DEFAULT_NOTEBOOK_ID, SEARCH_TOP_K
from ..embeddings import embed_query
from ..llm import LLMError, chat_completion_text, stream_chat_completion
from ..models import ChatRequest, SummaryRequest
from ..store import SOURCE_STORE
from ..utils import build_content_from_sources
from ..vector_store import VECTOR_STORE
from .llm_options import resolve_llm_options


router = APIRouter()

CITATION_SNIPPET_CHARS = 300


def _citation(n: int, source_id, title, url, text: str) -> Dict[str, Any]:
    snippet = text.strip()
    if len(snippet) > CITATION_SNIPPET_CHARS:
        snippet = snippet[:CITATION_SNIPPET_CHARS].rstrip() + "..."
    return {"n": n, "sourceId": source_id, "title": title, "url": url, "snippet": snippet}


def _encode_citations(citations: List[Dict[str, Any]]) -> str:
    raw = json.dumps(citations, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _fit_context_budget(
    results, budget: int, citations: Optional[List[Dict[str, Any]]] = None
) -> str:
    if budget <= 0:
        return ""

    blocks = []
    used = 0
    for idx, (_score, meta) in enumerate(results, start=1):
        title = meta.get("source_title") or meta.get("source_url") or "Source"
        text = (meta.get("text") or "").strip()
        if not text:
            continue
        block = f"[Source {idx}] {title}\n{text}"
        remaining = budget - used
        if remaining <= 0:
            break
        if len(block) > remaining:
            if remaining < 64:
                break
            block = block[: max(0, remaining - 3)].rstrip() + "..."
        blocks.append(block)
        if citations is not None:
            citations.append(
                _citation(idx, meta.get("source_id"), title, meta.get("source_url"), text)
            )
        used += len(block) + 2
        if used >= budget:
            break
    return "\n\n".join(blocks)


def _fallback_context(
    notebook_id: str, budget: int, citations: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Stored source text, capped to the same budget, for notebooks without an index."""
    if budget <= 0:
        return ""
    sources = SOURCE_STORE.list_sources(notebook_id)
    if not sources:
        return ""
    per_source = max(1, budget // len(sources))
    try:
        content = build_content_from_sources(sources, max_chars=per_source)
    except ValueError:
        return ""
    content = content[:budget]
    if citations is not None:
        # Same numbering as build_content_from_sources; keep sources that survived the cut.
        for idx, source in enumerate(sources, start=1):
            if f"[Source {idx}] " not in content:
                continue
            body = source.text or source.content or ""
            citations.append(
                _citation(idx, source.id, source.title or source.url, source.url, body)
            )
    return content


@router.post("/api/summary")
async def api_summary(payload: SummaryRequest) -> Dict[str, str]:
    if not payload.context:
        return {"summary": "No content to summarize."}

    temperature, max_tokens = resolve_llm_options(
        payload.temperature,
        payload.maxTokens,
        0.7,
    )
    system_prompt = (
        "You are an expert research assistant. Respond in Russian. "
        "Analyze the provided context and provide a comprehensive summary. "
        "Structure: 1) a brief 1-2 sentence overview, "
        "2) 3-5 bullet points with key facts or insights, "
        "3) a concluding sentence. Be concise and professional."
    )
    user_prompt = f"Context:\n{payload.context}"
    summary = await chat_completion_text(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if not summary:
        raise HTTPException(status_code=500, detail="Empty summary response")
    return {"summary": summary}


@router.post("/api/chat")
async def api_chat(payload: ChatRequest) -> StreamingResponse:
    use_sources = payload.useSources if payload.useSources is not None else True
    notebook_id = payload.notebookId or DEFAULT_NOTEBOOK_ID
    user_query = ""
    for message in reversed(payload.messages):
        if message.role == "user":
            user_query = message.content.strip()
            break

    citations: List[Dict[str, Any]] = []
    if use_sources:
        context = ""
        if user_query and VECTOR_STORE.has(notebook_id):
            try:
                query_embedding = await embed_query(user_query)
                top_k = payload.topK or SEARCH_TOP_K
                results = VECTOR_STORE.search(notebook_id, query_embedding, top_k)
                if results:
                    context = _fit_context_budget(
                        results, CHAT_CONTEXT_CHAR_BUDGET, citations
                    )
            except Exception:
                context = ""
                citations.clear()

        if not context:
            context = _fallback_context(notebook_id, CHAT_CONTEXT_CHAR_BUDGET, citations)
        if not context:
            context = "No source context available."

        system_prompt = (
            "You are HyperbookLM, an advanced research assistant. Respond in Russian. "
            "Answer using the source context below. If the answer is not in the "
            "context, say that the answer is not in the sources. Be concise and "
            "professional. Do NOT output raw passages, chunk labels, or raw markdown. "
            "If helpful, cite sources as (Source N).\n\n"
            f"Source context:\n{context}"
        )
    else:
        system_prompt = (
            "You are HyperbookLM, a helpful assistant. Respond in Russian. "
            "Answer naturally and concisely. If you are unsure, say so."
        )

    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m.role, "content": m.content} for m in payload.messages
    ]
    temperature, max_tokens = resolve_llm_options(
        payload.temperature,
        payload.maxTokens,
        0.2,
    )

    tokens = stream_chat_completion(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
    ).__aiter__()
    # Wait for the first token so connection/HTTP errors surface as a 502
    # (via the LLMError handler) instead of an empty 200 stream.
    try:
        first_token = await tokens.__anext__()
    except StopAsyncIteration:
        first_token = ""

    async def token_stream():
        if first_token:
            yield first_token
        try:
            async for token in tokens:
                yield token
        except LLMError as exc:
            yield f"\n\n[LLM error: {exc}]"

    return StreamingResponse(
        token_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Chat-Sources": _encode_citations(citations),
        },
    )
