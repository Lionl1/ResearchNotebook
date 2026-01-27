import time

from backend.app.config import DEFAULT_NOTEBOOK_ID
from backend.app.models import Project, Source
from backend.app.store import PROJECT_STORE, SOURCE_STORE


def test_project_store_default_guard():
    PROJECT_STORE.replace_all([])
    projects = PROJECT_STORE.list()
    assert any(project.id == DEFAULT_NOTEBOOK_ID for project in projects)
    assert PROJECT_STORE.delete(DEFAULT_NOTEBOOK_ID) is False


def test_project_store_create_delete():
    PROJECT_STORE.replace_all(
        [
            Project(
                id=DEFAULT_NOTEBOOK_ID,
                name="Default",
                createdAt=int(time.time() * 1000),
            )
        ]
    )
    project = PROJECT_STORE.create("Test Project")
    assert project.id != DEFAULT_NOTEBOOK_ID
    assert PROJECT_STORE.delete(project.id) is True


def test_source_store_add_remove_clear():
    SOURCE_STORE.clear_all()
    source = Source(
        id="source-1",
        url="https://example.com",
        title="Example",
        content="Hello",
        text="Hello",
        addedAt=int(time.time() * 1000),
        status="success",
    )
    SOURCE_STORE.add_source(DEFAULT_NOTEBOOK_ID, source)
    assert SOURCE_STORE.list_sources(DEFAULT_NOTEBOOK_ID)
    assert SOURCE_STORE.remove_source(DEFAULT_NOTEBOOK_ID, source.id) is True
    SOURCE_STORE.add_source(DEFAULT_NOTEBOOK_ID, source)
    SOURCE_STORE.clear_all()
    assert SOURCE_STORE.list_sources(DEFAULT_NOTEBOOK_ID) == []
