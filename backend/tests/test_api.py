import time

from backend.app import main
from backend.app.config import DEFAULT_NOTEBOOK_ID
from backend.app.models import Project, Source
from backend.app.store import PROJECT_STORE, SOURCE_STORE


def _make_source(source_id: str, text: str) -> Source:
    return Source(
        id=source_id,
        url="https://example.com",
        title="Example",
        content=text,
        text=text,
        addedAt=int(time.time() * 1000),
        status="success",
    )


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_sources_list_and_remove(client):
    source = _make_source("source-1", "hello")
    SOURCE_STORE.add_source(DEFAULT_NOTEBOOK_ID, source)

    response = client.post("/api/sources", json={"notebookId": DEFAULT_NOTEBOOK_ID})
    payload = response.json()
    assert response.status_code == 200
    assert payload["total"] == 1

    response = client.post(
        "/api/sources/remove",
        json={"notebookId": DEFAULT_NOTEBOOK_ID, "sourceId": source.id},
    )
    assert response.status_code == 200


def test_scrape_requires_url(client):
    response = client.post("/api/scrape", json={"url": ""})
    assert response.status_code == 400


def test_index_uses_cached_sources(client, monkeypatch):
    source = _make_source("source-idx", "hello world")
    SOURCE_STORE.add_source(DEFAULT_NOTEBOOK_ID, source)

    async def fake_embed_texts(texts):
        return [[0.1, 0.2] for _ in texts]

    captured = {}

    def fake_replace(notebook_id, embeddings, chunks):
        captured["notebook_id"] = notebook_id
        captured["embeddings"] = embeddings
        captured["chunks"] = chunks

    monkeypatch.setattr(main, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(main.VECTOR_STORE, "replace", fake_replace)

    response = client.post("/api/index", json={"notebookId": DEFAULT_NOTEBOOK_ID})
    assert response.status_code == 200
    assert captured["notebook_id"] == DEFAULT_NOTEBOOK_ID
    assert captured["embeddings"]
    assert captured["chunks"]


def test_search_requires_index(client, monkeypatch):
    monkeypatch.setattr(main.VECTOR_STORE, "has", lambda _: False)
    response = client.post(
        "/api/search",
        json={"notebookId": DEFAULT_NOTEBOOK_ID, "query": "test"},
    )
    assert response.status_code == 404


def test_search_returns_results(client, monkeypatch):
    monkeypatch.setattr(main.VECTOR_STORE, "has", lambda _: True)

    async def fake_embed_query(_):
        return [0.1, 0.2]

    def fake_search(_, __, ___):
        return [
            (
                0.92,
                {
                    "text": "chunk text",
                    "source_id": "source-1",
                    "source_url": "https://example.com",
                    "source_title": "Example",
                    "source_index": 1,
                    "chunk_index": 0,
                },
            )
        ]

    monkeypatch.setattr(main, "embed_query", fake_embed_query)
    monkeypatch.setattr(main.VECTOR_STORE, "search", fake_search)

    response = client.post(
        "/api/search",
        json={"notebookId": DEFAULT_NOTEBOOK_ID, "query": "test"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["total"] == 1
    assert payload["results"][0]["source"]["title"] == "Example"


def test_summary_uses_llm(client, monkeypatch):
    async def fake_summary(*_, **__):
        return "summary text"

    monkeypatch.setattr(main, "chat_completion_text", fake_summary)
    response = client.post("/api/summary", json={"context": "hello"})
    payload = response.json()
    assert response.status_code == 200
    assert payload["summary"] == "summary text"


def test_chat_streaming(client, monkeypatch):
    monkeypatch.setattr(main.VECTOR_STORE, "has", lambda _: False)

    async def fake_stream(_):
        yield "Hello "
        yield "world"

    monkeypatch.setattr(main, "stream_chat_completion", fake_stream)
    response = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "context": "",
            "notebookId": DEFAULT_NOTEBOOK_ID,
            "useSources": False,
        },
    )
    assert response.status_code == 200
    assert "Hello world" in response.text


def test_projects_export_import(client):
    project = PROJECT_STORE.create("Project A")
    SOURCE_STORE.add_source(project.id, _make_source("source-a", "alpha"))

    export_response = client.post(
        "/api/projects/export", json={"projectId": project.id}
    )
    assert export_response.status_code == 200

    PROJECT_STORE.replace_all(
        [
            Project(
                id=DEFAULT_NOTEBOOK_ID,
                name="Default",
                createdAt=int(time.time() * 1000),
            )
        ]
    )
    SOURCE_STORE.clear_all()

    files = {
        "file": (
            "export.zip",
            export_response.content,
            "application/zip",
        )
    }
    response = client.post(
        "/api/projects/import",
        data={"mode": "replace"},
        files=files,
    )
    assert response.status_code == 200
    assert any(p.id == project.id for p in PROJECT_STORE.list())
