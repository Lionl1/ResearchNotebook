import json
import re
from typing import Any, Dict, Iterable, List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .models import Source


def build_content_from_sources(sources: Iterable[Source], max_chars: int) -> str:
    chunks = []
    for idx, source in enumerate(sources, start=1):
        if source.status != "success":
            continue
        body = (source.text or source.content or "").strip()
        if not body:
            continue
        snippet = body[:max_chars]
        label = source.title or source.url
        chunks.append(f"[Source {idx}] {label}\n{snippet}")
    content = "\n\n".join(chunks)
    if not content:
        raise ValueError("No source text available for generation.")
    return content


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    if not text:
        return []
    if chunk_size <= 0:
        return [text.strip()]
    overlap = max(0, min(overlap, chunk_size - 1))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
        keep_separator=False,
        length_function=len,
    )
    chunks = splitter.split_text(text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def build_chunks_from_sources(
    sources: Iterable[Source], max_chars: int, chunk_size: int, overlap: int
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for idx, source in enumerate(sources, start=1):
        if source.status != "success":
            continue
        body = (source.text or source.content or "").strip()
        if not body:
            continue
        body = body[:max_chars]
        for chunk_index, chunk in enumerate(chunk_text(body, chunk_size, overlap)):
            results.append(
                {
                    "text": chunk,
                    "source_index": idx,
                    "source_id": source.id,
                    "source_url": source.url,
                    "source_title": source.title or source.url,
                    "chunk_index": chunk_index,
                }
            )
    if not results:
        raise ValueError("No source text available for indexing.")
    return results


def clean_json_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"```json\\s*|\\s*```", "", cleaned)
    return cleaned.strip()


def parse_json(text: str) -> Any:
    cleaned = clean_json_text(text)
    return json.loads(cleaned)
