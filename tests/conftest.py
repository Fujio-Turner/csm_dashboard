from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from csm_dashboard.storage.memory import MemoryStore
from csm_dashboard.storage.repo import CsmRepo
from csm_dashboard.web.app import create_app


@pytest.fixture
def repo() -> CsmRepo:
    return CsmRepo(MemoryStore())


@pytest.fixture
def client(repo: CsmRepo) -> TestClient:
    return TestClient(create_app(repo=repo))
