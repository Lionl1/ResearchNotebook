import json
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .config import LLM_MAX_TOKENS, LLM_TIMEOUT_SECONDS, VLLM_API_BASE, VLLM_API_KEY, VLLM_MODEL


class LLMError(RuntimeError):
    """The OpenAI-compatible server is unreachable or returned an error."""


def _describe(exc: httpx.HTTPError) -> str:
    detail = str(exc) or type(exc).__name__
    return f"LLM server at {VLLM_API_BASE} is unavailable: {detail}"


def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if VLLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_API_KEY}"
    return headers


def _chat_url() -> str:
    return f"{VLLM_API_BASE}/chat/completions"


async def chat_completion(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
    response_format: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model or VLLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or LLM_MAX_TOKENS,
    }
    if response_format:
        payload["response_format"] = response_format

    timeout = httpx.Timeout(LLM_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(_chat_url(), headers=_headers(), json=payload)
    except httpx.HTTPError as exc:
        raise LLMError(_describe(exc)) from exc
    if response.status_code >= 400:
        raise LLMError(f"LLM server error {response.status_code}: {response.text}")
    return response.json()


async def chat_completion_text(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
    response_format: Optional[Dict[str, Any]] = None,
) -> str:
    data = await chat_completion(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


async def stream_chat_completion(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
) -> AsyncIterator[str]:
    payload: Dict[str, Any] = {
        "model": model or VLLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or LLM_MAX_TOKENS,
        "stream": True,
    }

    timeout = httpx.Timeout(None)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", _chat_url(), headers=_headers(), json=payload
            ) as response:
                if response.status_code >= 400:
                    text = await response.aread()
                    raise LLMError(
                        f"LLM server error {response.status_code}: "
                        + text.decode("utf-8", errors="replace")
                    )

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = (
                        payload.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content")
                    )
                    if not delta:
                        continue
                    if isinstance(delta, list):
                        parts = []
                        for item in delta:
                            if isinstance(item, dict) and "text" in item:
                                parts.append(item["text"])
                            elif isinstance(item, str):
                                parts.append(item)
                        delta = "".join(parts)
                    if delta:
                        yield str(delta)
    except httpx.HTTPError as exc:
        raise LLMError(_describe(exc)) from exc
