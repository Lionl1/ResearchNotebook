import time
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4

from .config import DEFAULT_NOTEBOOK_ID
from .models import Project, Source


class SourceStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._store: Dict[str, List[Source]] = {}

    def set_sources(self, notebook_id: str, sources: List[Source]) -> None:
        with self._lock:
            self._store[notebook_id] = list(sources)

    def add_source(self, notebook_id: str, source: Source) -> None:
        with self._lock:
            existing = self._store.get(notebook_id, [])
            existing = [s for s in existing if s.id != source.id]
            existing.append(source)
            self._store[notebook_id] = existing

    def list_sources(self, notebook_id: str) -> List[Source]:
        with self._lock:
            return list(self._store.get(notebook_id, []))

    def remove_source(self, notebook_id: str, source_id: str) -> bool:
        with self._lock:
            sources = self._store.get(notebook_id, [])
            next_sources = [source for source in sources if source.id != source_id]
            if len(next_sources) == len(sources):
                return False
            self._store[notebook_id] = next_sources
            return True

    def clear(self, notebook_id: str) -> None:
        with self._lock:
            self._store.pop(notebook_id, None)

    def clear_all(self) -> None:
        with self._lock:
            self._store.clear()


SOURCE_STORE = SourceStore()


class ProjectStore:
    def __init__(self) -> None:
        self._lock = Lock()
        created_at = int(time.time() * 1000)
        self._projects: Dict[str, Project] = {
            DEFAULT_NOTEBOOK_ID: Project(
                id=DEFAULT_NOTEBOOK_ID,
                name="Default",
                createdAt=created_at,
            )
        }

    def list(self) -> List[Project]:
        with self._lock:
            return sorted(self._projects.values(), key=lambda p: p.createdAt)

    def get(self, project_id: str) -> Optional[Project]:
        with self._lock:
            return self._projects.get(project_id)

    def create(self, name: Optional[str]) -> Project:
        with self._lock:
            label = (name or "").strip() or f"Project {len(self._projects) + 1}"
            project_id = f"proj-{uuid4().hex[:8]}"
            project = Project(id=project_id, name=label, createdAt=int(time.time() * 1000))
            self._projects[project_id] = project
            return project

    def delete(self, project_id: str) -> bool:
        if project_id == DEFAULT_NOTEBOOK_ID:
            return False
        with self._lock:
            return self._projects.pop(project_id, None) is not None

    def upsert_many(self, projects: List[Project]) -> None:
        with self._lock:
            for project in projects:
                self._projects[project.id] = project

    def replace_all(self, projects: List[Project]) -> None:
        with self._lock:
            self._projects = {project.id: project for project in projects}
            if DEFAULT_NOTEBOOK_ID not in self._projects:
                self._projects[DEFAULT_NOTEBOOK_ID] = Project(
                    id=DEFAULT_NOTEBOOK_ID,
                    name="Default",
                    createdAt=int(time.time() * 1000),
                )


PROJECT_STORE = ProjectStore()
