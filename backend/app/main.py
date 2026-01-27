import io
import json
import zipfile
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
import fitz

from .config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CORS_ORIGINS,
    DEFAULT_NOTEBOOK_ID,
    GEMINI_API_KEY,
    MAX_SOURCE_CHARS,
    MAX_IMPORT_SIZE_MB,
    MAX_IMPORT_UNPACK_MB,
    MAX_IMPORT_FILES,
    MAX_UPLOAD_SIZE_MB,
    SEARCH_TOP_K,
    VEO_MODEL,
)
from .embeddings import embed_query, embed_texts
from .llm import chat_completion_text, stream_chat_completion
from .models import (
    ChatRequest,
    CreateProjectRequest,
    DeleteProjectRequest,
    ExportProjectRequest,
    NotebookRequest,
    Project,
    RemoveSourceRequest,
    SearchRequest,
    SourceListRequest,
    Source,
    ScrapeRequest,
    SummaryRequest,
    VeoPollRequest,
    VeoStartRequest,
)
from .extract_text import extract_text_from_file, is_available as extract_available, is_supported_filename, merge_extracted_text
from .scrape import scrape_url
from .store import PROJECT_STORE, SOURCE_STORE
from .stt import transcribe_audio
from .utils import build_chunks_from_sources, build_content_from_sources, parse_json
from .vector_store import VECTOR_STORE


app = FastAPI(title="hyperbooklm-python")
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root() -> HTMLResponse:
    index_path = STATIC_DIR / "index.html"
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.post("/api/scrape")
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


@app.post("/api/upload")
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


@app.post("/api/stt")
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


@app.post("/api/summary")
async def api_summary(payload: SummaryRequest) -> Dict[str, str]:
    if not payload.context:
        return {"summary": "No content to summarize."}

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
        temperature=0.7,
    )
    if not summary:
        raise HTTPException(status_code=500, detail="Empty summary response")
    return {"summary": summary}


@app.post("/api/index")
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


@app.post("/api/search")
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


@app.post("/api/sources")
async def api_sources(payload: SourceListRequest) -> Dict[str, Any]:
    notebook_id = payload.notebookId or DEFAULT_NOTEBOOK_ID
    sources = SOURCE_STORE.list_sources(notebook_id)
    return {
        "notebookId": notebook_id,
        "sources": [source.model_dump() for source in sources],
        "total": len(sources),
    }


@app.post("/api/sources/remove")
async def api_sources_remove(payload: RemoveSourceRequest) -> Dict[str, Any]:
    notebook_id = payload.notebookId or DEFAULT_NOTEBOOK_ID
    removed = SOURCE_STORE.remove_source(notebook_id, payload.sourceId)
    if not removed:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"notebookId": notebook_id, "removed": payload.sourceId}


@app.post("/api/sources/clear")
async def api_sources_clear(payload: SourceListRequest) -> Dict[str, Any]:
    notebook_id = payload.notebookId or DEFAULT_NOTEBOOK_ID
    SOURCE_STORE.clear(notebook_id)
    VECTOR_STORE.delete(notebook_id)
    return {"notebookId": notebook_id, "cleared": True}


@app.post("/api/chat")
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
                results = VECTOR_STORE.search(notebook_id, query_embedding, SEARCH_TOP_K)
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

    async def token_stream():
        async for token in stream_chat_completion(messages):
            yield token

    return StreamingResponse(
        token_stream(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/api/projects")
async def api_projects() -> Dict[str, Any]:
    projects = PROJECT_STORE.list()
    return {
        "projects": [project.model_dump() for project in projects],
        "defaultId": DEFAULT_NOTEBOOK_ID,
    }


@app.post("/api/projects/create")
async def api_projects_create(payload: CreateProjectRequest) -> Dict[str, Any]:
    project = PROJECT_STORE.create(payload.name)
    return {"project": project.model_dump()}


@app.post("/api/projects/delete")
async def api_projects_delete(payload: DeleteProjectRequest) -> Dict[str, Any]:
    removed = PROJECT_STORE.delete(payload.projectId)
    if not removed:
        raise HTTPException(status_code=404, detail="Project not found or cannot be deleted")
    SOURCE_STORE.clear(payload.projectId)
    VECTOR_STORE.delete(payload.projectId)
    return {"deleted": payload.projectId}




def _build_projects_payload(projects) -> Dict[str, Any]:
    sources_by_project = {
        project.id: [source.model_dump() for source in SOURCE_STORE.list_sources(project.id)]
        for project in projects
    }
    return {
        "projects": [project.model_dump() for project in projects],
        "sources": sources_by_project,
        "savedAt": int(time.time() * 1000),
    }


@app.post("/api/projects/export")
async def api_projects_export(payload: ExportProjectRequest) -> Response:
    projects = PROJECT_STORE.list()
    if payload.projectId:
        projects = [p for p in projects if p.id == payload.projectId]
        if not projects:
            raise HTTPException(status_code=404, detail="Project not found")

    payload_data = _build_projects_payload(projects)
    vectors: Dict[str, Any] = {}
    for project in projects:
        data = VECTOR_STORE.export(project.id)
        if data:
            vectors[project.id] = data
    if vectors:
        payload_data["vectors"] = vectors
    archive_name = (
        f"project-{projects[0].id}.zip" if len(projects) == 1 else "projects-export.zip"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(
            "projects.json",
            json.dumps(payload_data, ensure_ascii=True, indent=2),
        )
    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{archive_name}"'},
    )


@app.post("/api/projects/import")
async def api_projects_import(
    file: UploadFile = File(...),
    mode: str = Form("merge"),
) -> Dict[str, Any]:
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    mode_value = (mode or "merge").strip().lower()
    if mode_value not in {"merge", "replace"}:
        raise HTTPException(status_code=400, detail="Invalid import mode")

    data = await file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_IMPORT_SIZE_MB:
        raise HTTPException(status_code=400, detail="Import archive is too large")
    buffer = io.BytesIO(data)
    if not zipfile.is_zipfile(buffer):
        raise HTTPException(status_code=400, detail="Invalid archive")
    buffer.seek(0)

    with zipfile.ZipFile(buffer) as zipf:
        infos = zipf.infolist()
        if len(infos) > MAX_IMPORT_FILES:
            raise HTTPException(status_code=400, detail="Import archive has too many files")
        total_unpacked = sum(info.file_size for info in infos)
        if total_unpacked > MAX_IMPORT_UNPACK_MB * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Import archive is too large to unpack")
        json_name = next(
            (name for name in zipf.namelist() if name.endswith("projects.json")), None
        )
        if not json_name:
            raise HTTPException(status_code=400, detail="projects.json not found")
        payload_data = json.loads(zipf.read(json_name))

        projects_data = payload_data.get("projects", [])
        sources_data = payload_data.get("sources", {})
        vectors_data = payload_data.get("vectors", {})

        if not isinstance(projects_data, list) or not isinstance(sources_data, dict):
            raise HTTPException(status_code=400, detail="Invalid archive payload")

        projects: List[Project] = []
        for item in projects_data:
            try:
                projects.append(Project(**item))
            except Exception:
                continue

        if not projects:
            raise HTTPException(status_code=400, detail="No valid projects to import")

        if mode_value == "replace":
            existing_ids = [project.id for project in PROJECT_STORE.list()]
            for project_id in existing_ids:
                VECTOR_STORE.delete(project_id)
            PROJECT_STORE.replace_all(projects)
            SOURCE_STORE.clear_all()
        else:
            PROJECT_STORE.upsert_many(projects)

        imported_sources = 0
        for project_id, items in sources_data.items():
            if not isinstance(items, list):
                continue
            sources: List[Source] = []
            for item in items:
                try:
                    sources.append(Source(**item))
                except Exception:
                    continue
            SOURCE_STORE.set_sources(project_id, sources)
            imported_sources += len(sources)

        if isinstance(vectors_data, dict):
            for project_id, data in vectors_data.items():
                if not isinstance(data, dict):
                    continue
                VECTOR_STORE.import_data(project_id, data)
            VECTOR_STORE.reset()

    return {
        "projects": len(projects),
        "sources": imported_sources,
        "mode": mode_value,
    }




@app.post("/api/gpt/overview")
async def api_overview(payload: NotebookRequest) -> Dict[str, Any]:
    try:
        content = build_content_from_sources(payload.sources, max_chars=3000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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


@app.post("/api/gpt/mindmap")
async def api_mindmap(payload: NotebookRequest) -> Dict[str, Any]:
    try:
        content = build_content_from_sources(payload.sources, max_chars=4000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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


@app.post("/api/gemini/slides")
async def api_slides(payload: NotebookRequest) -> Dict[str, Any]:
    try:
        content = build_content_from_sources(payload.sources, max_chars=50000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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


@app.post("/api/veo/start")
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


@app.post("/api/veo/poll")
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
