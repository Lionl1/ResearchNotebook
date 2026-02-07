from typing import Any, Dict

import httpx
from fastapi import APIRouter, HTTPException

from ..config import GEMINI_API_KEY, VEO_MODEL
from ..models import VeoPollRequest, VeoStartRequest


router = APIRouter()


@router.post("/api/veo/start")
async def api_veo_start(payload: VeoStartRequest) -> Dict[str, str]:
    if not payload.prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key is missing")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{VEO_MODEL}:predictLongRunning"
    params = {"key": GEMINI_API_KEY}
    body = {"instances": [{"prompt": payload.prompt}]}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, params=params, json=body)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        data = response.json()

    name = data.get("name")
    if not name:
        raise HTTPException(status_code=500, detail="No operation name returned for Veo job")
    return {"operationName": name}


@router.post("/api/veo/poll")
async def api_veo_poll(payload: VeoPollRequest) -> Dict[str, Any]:
    if not payload.operationName:
        raise HTTPException(status_code=400, detail="Operation name is required")
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key is missing")

    url = f"https://generativelanguage.googleapis.com/v1beta/{payload.operationName}"
    params = {"key": GEMINI_API_KEY}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        data = response.json()

    if not data.get("done"):
        return {"done": False, "operationName": payload.operationName}

    uri = (
        data.get("response", {})
        .get("generateVideoResponse", {})
        .get("generatedSamples", [{}])[0]
        .get("video", {})
        .get("uri")
    )
    return {"done": True, "operationName": payload.operationName, "videoUri": uri}
