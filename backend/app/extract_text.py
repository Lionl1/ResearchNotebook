from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi.concurrency import run_in_threadpool


logger = logging.getLogger(__name__)

EXTRACT_TEXT_ROOT = Path(__file__).resolve().parents[1] / "third_party" / "extract-text"


def _bootstrap_extract_text() -> bool:
    if not EXTRACT_TEXT_ROOT.exists():
        return False
    if str(EXTRACT_TEXT_ROOT) not in sys.path:
        sys.path.insert(0, str(EXTRACT_TEXT_ROOT))
    return True


_AVAILABLE = False
_TextExtractor = None
_is_supported_format = None
_settings = None

if _bootstrap_extract_text():
    try:
        from app.extractors import TextExtractor as _TextExtractor  # type: ignore
        from app.utils import is_supported_format as _is_supported_format  # type: ignore
        from app.config import settings as _settings  # type: ignore

        _AVAILABLE = True
    except Exception as exc:
        logger.warning("extract-text integration disabled: %s", exc)


_EXTRACTOR: Optional[Any] = None
_extractor_lock = threading.Lock()


def is_available() -> bool:
    return _AVAILABLE


def is_supported_filename(filename: str) -> bool:
    if not _AVAILABLE or not _is_supported_format or not _settings:
        return False
    return _is_supported_format(filename, _settings.SUPPORTED_FORMATS)


def extract_text_from_file(file_content: bytes, filename: str) -> List[Dict[str, Any]]:
    if not _AVAILABLE or _TextExtractor is None:
        raise RuntimeError("extract-text is not available")
    global _EXTRACTOR
    if _EXTRACTOR is None:
        with _extractor_lock:
            if _EXTRACTOR is None:
                _EXTRACTOR = _TextExtractor()
    return _EXTRACTOR.extract_text(file_content, filename)


async def extract_text_from_file_async(file_content: bytes, filename: str) -> List[Dict[str, Any]]:
    """Асинхронная неблокирующая обертка для извлечения текста."""
    return await run_in_threadpool(extract_text_from_file, file_content, filename)


async def extract_text_from_url_async(url: str, user_agent: Optional[str] = None) -> List[Dict[str, Any]]:
    """Асинхронное извлечение текста с URL с использованием продвинутого парсера (Playwright/JS)."""
    if not _AVAILABLE or _TextExtractor is None:
        raise RuntimeError("extract-text is not available")
    
    global _EXTRACTOR
    if _EXTRACTOR is None:
        with _extractor_lock:
            if _EXTRACTOR is None:
                _EXTRACTOR = _TextExtractor()
                
    return await run_in_threadpool(_EXTRACTOR.extract_from_url, url, user_agent)


def merge_extracted_text(items: List[Dict[str, Any]]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return (items[0].get("text") or "").strip()
    blocks = []
    for item in items:
        name = item.get("filename") or item.get("path") or "document"
        text = (item.get("text") or "").strip()
        if not text:
            continue
        blocks.append(f"{name}\n{text}")
    return "\n\n".join(blocks).strip()
