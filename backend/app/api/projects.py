import io
import json
import time
import zipfile
from typing import Any, Dict, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from ..config import (
    DEFAULT_NOTEBOOK_ID,
    MAX_IMPORT_FILES,
    MAX_IMPORT_SIZE_MB,
    MAX_IMPORT_UNPACK_MB,
)
from ..models import (
    CreateProjectRequest,
    DeleteProjectRequest,
    ExportProjectRequest,
    Project,
    Source,
)
from ..store import PROJECT_STORE, SOURCE_STORE
from ..vector_store import VECTOR_STORE


router = APIRouter()


@router.post("/api/projects")
async def api_projects() -> Dict[str, Any]:
    projects = PROJECT_STORE.list()
    return {
        "projects": [project.model_dump() for project in projects],
        "defaultId": DEFAULT_NOTEBOOK_ID,
    }


@router.post("/api/projects/create")
async def api_projects_create(payload: CreateProjectRequest) -> Dict[str, Any]:
    project = PROJECT_STORE.create(payload.name)
    return {"project": project.model_dump()}


@router.post("/api/projects/delete")
async def api_projects_delete(payload: DeleteProjectRequest) -> Dict[str, Any]:
    removed = PROJECT_STORE.delete(payload.projectId)
    if not removed:
        raise HTTPException(status_code=404, detail="Project not found or cannot be deleted")
    SOURCE_STORE.clear(payload.projectId)
    VECTOR_STORE.delete(payload.projectId)
    return {"deleted": payload.projectId}


def _build_projects_payload(projects: List[Project]) -> Dict[str, Any]:
    sources_by_project = {
        project.id: [source.model_dump() for source in SOURCE_STORE.list_sources(project.id)]
        for project in projects
    }
    return {
        "projects": [project.model_dump() for project in projects],
        "sources": sources_by_project,
        "savedAt": int(time.time() * 1000),
    }


@router.post("/api/projects/export")
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


@router.post("/api/projects/import")
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
