import time

import pytest

from backend.app.models import Source
from backend.app.utils import build_chunks_from_sources, build_content_from_sources, chunk_text


def test_chunk_text_splits():
    text = "Hello world. This is a test sentence."
    chunks = chunk_text(text, chunk_size=12, overlap=2)
    assert chunks
    assert all(chunk.strip() for chunk in chunks)
    assert len(chunks) > 1


def test_build_content_from_sources_requires_text():
    source = Source(
        id="source-1",
        url="https://example.com",
        title="Example",
        content="",
        text="",
        addedAt=int(time.time() * 1000),
        status="success",
    )
    with pytest.raises(ValueError, match="No source text available"):
        build_content_from_sources([source], max_chars=1000)


def test_build_chunks_from_sources_creates_chunks():
    source = Source(
        id="source-2",
        url="https://example.com",
        title="Example",
        content="Hello world. Second sentence.",
        text="Hello world. Second sentence.",
        addedAt=int(time.time() * 1000),
        status="success",
    )
    chunks = build_chunks_from_sources([source], max_chars=200, chunk_size=10, overlap=2)
    assert chunks
    assert chunks[0]["source_id"] == source.id
