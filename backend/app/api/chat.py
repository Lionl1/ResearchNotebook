from typing import Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..config import DEFAULT_NOTEBOOK_ID, SEARCH_TOP_K
from ..embeddings import embed_query
from ..llm import chat_completion_text, stream_chat_completion
from ..models import ChatRequest, SummaryRequest
from ..vector_store import VECTOR_STORE
from .llm_options import resolve_llm_options


router = APIRouter()


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
    context = payload.context or ""
    notebook_id = payload.notebookId or DEFAULT_NOTEBOOK_ID
    user_query = ""
    for message in reversed(payload.messages):
        if message.role == "user":
            user_query = message.content.strip()
            break

    if use_sources:
        retrieved_context = ""
        if user_query and VECTOR_STORE.has(notebook_id):
            try:
                query_embedding = await embed_query(user_query)
                top_k = payload.topK or SEARCH_TOP_K
                results = VECTOR_STORE.search(notebook_id, query_embedding, top_k)
                if results:
                    blocks = []
                    for idx, (score, meta) in enumerate(results, start=1):
                        title = meta.get("source_title") or meta.get("source_url") or "Source"
                        text = meta.get("text", "")
                        blocks.append(f"[Source {idx}] {title}\n{text}")
                    retrieved_context = "\n\n".join(blocks)
            except Exception:
                retrieved_context = ""

        if not retrieved_context:
            retrieved_context = "No relevant retrieved context available."
        if not context:
            context = "No additional source context provided."

        system_prompt = (
            "You are HyperbookLM, an advanced research assistant. Respond in Russian. "
            "Answer using the retrieved context FIRST. If the answer is not in the retrieved "
            "context, use the additional sources. If still unknown, say that the answer "
            "is not in the sources. Be concise and professional. "
            "Do NOT output retrieved passages, chunk labels, or raw markdown. "
            "If helpful, cite sources as (Source N).\n\n"
            f"Retrieved context (highest priority):\n{retrieved_context}\n\n"
            f"Additional sources:\n{context}"
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

    async def token_stream():
        async for token in stream_chat_completion(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield token

    return StreamingResponse(
        token_stream(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
