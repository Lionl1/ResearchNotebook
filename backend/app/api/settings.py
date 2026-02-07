from typing import Any, Dict

from fastapi import APIRouter

from ..config import LLM_MAX_TOKENS, LLM_TIMEOUT_SECONDS, SEARCH_TOP_K


router = APIRouter()


@router.get("/api/settings")
async def api_settings() -> Dict[str, Any]:
    return {
        "llm": {
            "maxTokens": LLM_MAX_TOKENS,
            "timeoutSeconds": LLM_TIMEOUT_SECONDS,
        },
        "retrieval": {"topK": SEARCH_TOP_K},
    }
