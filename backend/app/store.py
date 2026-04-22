import json
import logging
import tempfile
import time
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4

from .config import DEFAULT_NOTEBOOK_ID, STATE_FILE
from .models import Project, Source

logger = logging.getLogger(__name__)


class PersistentState:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, object]:
        with self._lock:
            if not self._path.exists():
                logger.info("State file does not exist yet: %s", self._path)
                return {}
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Failed to load state from %s: %s", self._path, exc)
                return {}
            logger.info("Loaded state from %s", self._path)
            return payload if isinstance(payload, dict) else {}

    def save(self, projects: Dict[str, Project], sources: Dict[str, List[Source]]) -> None:
        payload = {
            "projects": [project.model_dump() for project in projects.values()],
            "sources": {
                notebook_id: [source.model_dump() for source in items]
                for notebook_id, items in sources.items()
            },
            "savedAt": int(time.time() * 1000),
        }
        raw = json.dumps(payload, ensure_ascii=True, indent=2)
        with self._lock:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._path.parent,
                prefix=f"{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(raw)
                tmp_path = Path(handle.name)
            tmp_path.replace(self._path)
        logger.info(
            "Persisted state to %s (%d projects, %d notebooks)",
            self._path,
            len(projects),
            len(sources),
        )


STATE = PersistentState(STATE_FILE)


class SourceStore:
    def __init__(self, state: PersistentState) -> None:
        self._lock = Lock()
        self._store: Dict[str, List[Source]] = {}
        self._state = state

    def _snapshot(self) -> Dict[str, List[Source]]:
        return {notebook_id: list(sources) for notebook_id, sources in self._store.items()}

    def set_sources(self, notebook_id: str, sources: List[Source]) -> None:
        with self._lock:
            self._store[notebook_id] = list(sources)
            snapshot = self._snapshot()
        PROJECT_STORE.persist(source_snapshot=snapshot)

    def add_source(self, notebook_id: str, source: Source) -> None:
        with self._lock:
            existing = self._store.get(notebook_id, [])
            existing = [s for s in existing if s.id != source.id]
            existing.append(source)
            self._store[notebook_id] = existing
            snapshot = self._snapshot()
        PROJECT_STORE.persist(source_snapshot=snapshot)

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
            snapshot = self._snapshot()
        PROJECT_STORE.persist(source_snapshot=snapshot)
        return True

    def clear(self, notebook_id: str) -> None:
        with self._lock:
            self._store.pop(notebook_id, None)
            snapshot = self._snapshot()
        PROJECT_STORE.persist(source_snapshot=snapshot)

    def clear_all(self) -> None:
        with self._lock:
            self._store.clear()
            snapshot = self._snapshot()
        PROJECT_STORE.persist(source_snapshot=snapshot)

    def replace_all(self, sources: Dict[str, List[Source]]) -> None:
        with self._lock:
            self._store = {notebook_id: list(items) for notebook_id, items in sources.items()}
            snapshot = self._snapshot()
        PROJECT_STORE.persist(source_snapshot=snapshot)

    def restore(self, sources: Dict[str, List[Source]]) -> None:
        with self._lock:
            self._store = {notebook_id: list(items) for notebook_id, items in sources.items()}

    def snapshot(self) -> Dict[str, List[Source]]:
        with self._lock:
            return self._snapshot()


class ProjectStore:
    def __init__(self, state: PersistentState) -> None:
        self._lock = Lock()
        self._state = state
        self._projects: Dict[str, Project] = {}
        self._restore_defaults()

    def _default_project(self) -> Project:
        return Project(
            id=DEFAULT_NOTEBOOK_ID,
            name="Default",
            createdAt=int(time.time() * 1000),
        )

    def _restore_defaults(self) -> None:
        self._projects = {DEFAULT_NOTEBOOK_ID: self._default_project()}

    def _snapshot(self) -> Dict[str, Project]:
        return dict(self._projects)

    def restore(self, projects: List[Project]) -> None:
        with self._lock:
            self._projects = {project.id: project for project in projects}
            if DEFAULT_NOTEBOOK_ID not in self._projects:
                self._projects[DEFAULT_NOTEBOOK_ID] = self._default_project()

    def persist(self, source_snapshot: Optional[Dict[str, List[Source]]] = None) -> None:
        with self._lock:
            projects_snapshot = self._snapshot()
        if source_snapshot is None:
            source_snapshot = SOURCE_STORE.snapshot()
        self._state.save(projects_snapshot, source_snapshot)

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
        self.persist()
        return project

    def delete(self, project_id: str) -> bool:
        if project_id == DEFAULT_NOTEBOOK_ID:
            return False
        with self._lock:
            removed = self._projects.pop(project_id, None) is not None
        if removed:
            self.persist()
        return removed

    def upsert_many(self, projects: List[Project]) -> None:
        with self._lock:
            for project in projects:
                self._projects[project.id] = project
        self.persist()

    def replace_all(self, projects: List[Project]) -> None:
        with self._lock:
            self._projects = {project.id: project for project in projects}
            if DEFAULT_NOTEBOOK_ID not in self._projects:
                self._projects[DEFAULT_NOTEBOOK_ID] = self._default_project()
        self.persist()


PROJECT_STORE = ProjectStore(STATE)
SOURCE_STORE = SourceStore(STATE)


def _load_state() -> None:
    payload = STATE.load()

    projects_payload = payload.get("projects", [])
    sources_payload = payload.get("sources", {})

    projects: List[Project] = []
    if isinstance(projects_payload, list):
        for item in projects_payload:
            try:
                projects.append(Project(**item))
            except Exception as exc:
                logger.warning("Skipping invalid project entry from state: %s", exc)

    sources: Dict[str, List[Source]] = {}
    if isinstance(sources_payload, dict):
        for notebook_id, entries in sources_payload.items():
            if not isinstance(entries, list):
                continue
            restored: List[Source] = []
            for item in entries:
                try:
                    restored.append(Source(**item))
                except Exception as exc:
                    logger.warning("Skipping invalid source entry from state: %s", exc)
            sources[notebook_id] = restored

    PROJECT_STORE.restore(projects)
    SOURCE_STORE.restore(sources)


_load_state()
