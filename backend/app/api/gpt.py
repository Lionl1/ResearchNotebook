import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..llm import chat_completion_text
from ..models import LLMNotebookRequest
from ..utils import build_content_from_sources, parse_json
from .llm_options import resolve_llm_options


router = APIRouter()


@router.post("/api/gpt/overview")
async def api_overview(payload: LLMNotebookRequest) -> Dict[str, Any]:
    try:
        content = build_content_from_sources(payload.sources, max_chars=3000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    temperature, max_tokens = resolve_llm_options(
        payload.temperature,
        payload.maxTokens,
        0.2,
    )
    system_prompt = (
        "You summarize user-provided extracts in Russian. "
        'Respond with JSON {"bullets": string[], "keyStats": string[]}. '
        "Be concise, bullet-first, and cite sources like (Source 1)."
    )
    response_text = await chat_completion_text(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )

    try:
        parsed = parse_json(response_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to parse overview JSON") from exc

    return {
        "notebookId": payload.notebookId,
        "generatedAt": int(time.time() * 1000),
        "bullets": parsed.get("bullets", []),
        "keyStats": parsed.get("keyStats", []),
    }


@router.post("/api/gpt/mindmap")
async def api_mindmap(payload: LLMNotebookRequest) -> Dict[str, Any]:
    try:
        content = build_content_from_sources(payload.sources, max_chars=4000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    temperature, max_tokens = resolve_llm_options(
        payload.temperature,
        payload.maxTokens,
        0.2,
    )
    system_prompt = (
        "You produce concise mindmaps in Russian. "
        'Output ONLY valid JSON with this EXACT structure: '
        '{"root": {"title": "Main Topic", "children": [{"title": "Subtopic 1"}, '
        '{"title": "Subtopic 2", "children": [{"title": "Detail"}]}]}}. '
        'Every node must have a "title" string. Keep hierarchy shallow (max 3 levels).'
    )
    response_text = await chat_completion_text(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )

    try:
        parsed = parse_json(response_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to parse mindmap JSON") from exc

    root = parsed.get("root") if isinstance(parsed, dict) else None
    if root is None and isinstance(parsed, dict):
        root = parsed
    if not isinstance(root, dict) or "title" not in root:
        raise HTTPException(status_code=500, detail="Invalid mindmap structure")
    root.setdefault("children", [])

    return {
        "notebookId": payload.notebookId,
        "generatedAt": int(time.time() * 1000),
        "root": root,
    }


@router.post("/api/gemini/slides")
async def api_slides(payload: LLMNotebookRequest) -> Dict[str, Any]:
    try:
        content = build_content_from_sources(payload.sources, max_chars=50000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    temperature, max_tokens = resolve_llm_options(
        payload.temperature,
        payload.maxTokens,
        0.2,
    )
    system_prompt = (
        "You are an expert presentation designer. Respond in Russian. "
        "Create a slide deck outline based on the provided source content. "
        "Create 5-8 slides. Each slide has a title and 2-4 bullets. "
        "Return ONLY valid JSON with this structure: "
        '{"slides":[{"title":"Slide Title","bullets":["Point 1","Point 2"]}]}'
    )
    user_prompt = f"Sources:\n{content}"
    response_text = await chat_completion_text(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )

    try:
        parsed = parse_json(response_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to parse slides JSON") from exc

    slides = parsed.get("slides", []) if isinstance(parsed, dict) else []
    if not isinstance(slides, list):
        raise HTTPException(status_code=500, detail="Invalid slides structure")

    return {
        "notebookId": payload.notebookId,
        "generatedAt": int(time.time() * 1000),
        "slides": slides,
    }
