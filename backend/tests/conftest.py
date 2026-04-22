import os
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
TEST_STATE_DIR = ROOT_DIR / ".pytest_state"
os.environ.setdefault("CHROMA_DIR", str(TEST_STATE_DIR / "chroma"))
os.environ.setdefault("STATE_FILE", str(TEST_STATE_DIR / "app_state.json"))

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
