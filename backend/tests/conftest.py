import time

import pytest
from fastapi.testclient import TestClient

from backend.app.config import DEFAULT_NOTEBOOK_ID
from backend.app.main import app
from backend.app.models import Project
from backend.app.store import PROJECT_STORE, SOURCE_STORE


@pytest.fixture
def client():
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
    with TestClient(app) as test_client:
        yield test_client
