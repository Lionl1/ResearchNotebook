import time
from typing import Any, Dict

import fitz
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import DEFAULT_NOTEBOOK_ID, MAX_UPLOAD_SIZE_MB
from ..extract_text import (
    extract_text_from_file,
    is_available as extract_available,
    is_supported_filename,
    merge_extracted_text,
)
from ..models import ScrapeRequest, Source
from ..scrape import scrape_url
from ..store import SOURCE_STORE
from ..stt import transcribe_audio


router = APIRouter()


@router.post("/api/scrape")
async def api_scrape(payload: ScrapeRequest) -> Dict[str, str]:
    if not payload.url:
        raise HTTPException(status_code=400, detail="URL is required")
    try:
        title, content, text, final_url = await scrape_url(payload.url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    notebook_id = payload.notebookId or DEFAULT_NOTEBOOK_ID
    source = {
        "id": f"source-{int(time.time() * 1000)}",
        "url": final_url,
        "title": title,
        "content": content,
        "text": text,
        "addedAt": int(time.time() * 1000),
        "status": "success",
    }
    SOURCE_STORE.add_source(notebook_id, Source(**source))
    return {"title": title, "content": content, "text": text, "url": final_url, "id": source["id"]}


@router.post("/api/upload")
async def api_upload(
    file: UploadFile = File(...),
    notebookId: str | None = Form(None),
) -> Dict[str, Any]:
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    filename = file.filename or "upload"
    lower = filename.lower()
    is_pdf = lower.endswith(".pdf")
    is_txt = lower.endswith(".txt")
    if extract_available():
        if not is_supported_filename(filename):
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Update extract-text settings to allow this type.",
            )
    else:
        if not is_pdf and not is_txt:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Only PDF and TXT files are supported without extract-text. "
                    "Enable extract-text to add more formats."
                ),
            )

    data = await file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_UPLOAD_SIZE_MB}MB)")

    text = ""
    total_pages = 1
    if extract_available():
        try:
            extracted_items = extract_text_from_file(data, filename)
            text = merge_extracted_text(extracted_items)
            total_pages = len(extracted_items) if extracted_items else 1
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    elif is_txt:
        text = data.decode("utf-8", errors="replace")
    else:
        doc = fitz.open(stream=data, filetype="pdf")
        total_pages = doc.page_count
        parts = []
        for page in doc:
            parts.append(page.get_text("text") or "")
        text = "\n".join(parts)
        doc.close()

    title = filename.rsplit(".", 1)[0]
    notebook_id = notebookId or DEFAULT_NOTEBOOK_ID
    source = {
        "id": f"file-{int(time.time() * 1000)}",
        "url": filename,
        "title": title,
        "text": text,
        "content": text,
        "addedAt": int(time.time() * 1000),
        "status": "success",
    }
    SOURCE_STORE.add_source(notebook_id, Source(**source))

    return {
        "title": title,
        "text": text,
        "content": text,
        "filename": filename,
        "pages": total_pages,
        "id": source["id"],
    }


@router.post("/api/stt")
async def api_stt(
    file: UploadFile = File(...),
    notebookId: str | None = Form(None),
) -> Dict[str, Any]:
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    data = await file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_UPLOAD_SIZE_MB}MB)")

    try:
        text, segments = transcribe_audio(data, file.filename or "")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    title = (file.filename or "audio").rsplit(".", 1)[0]
    notebook_id = notebookId or DEFAULT_NOTEBOOK_ID
    source = {
        "id": f"audio-{int(time.time() * 1000)}",
        "url": file.filename or "audio",
        "title": title,
        "text": text,
        "content": text,
        "addedAt": int(time.time() * 1000),
        "status": "success",
    }
    SOURCE_STORE.add_source(notebook_id, Source(**source))

    return {"text": text, "segments": segments, "source": source}
