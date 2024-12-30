import asyncio
import warnings
import pytest
import pytest_asyncio
from typing import Generator
from fastapi.testclient import TestClient
from pathlib import Path
from api import app

#
# 1) Define a session-scoped event_loop fixture via pytest-asyncio.
#    This ensures a single event loop is used throughout all tests,
#    preventing SSE-Starlette from binding to a different loop.
#
@pytest_asyncio.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

def pytest_configure():
    """
    Filter out deprecation warnings for:
      1) The event_loop fixture redefinition (pytest-asyncio).
      2) datetime.datetime.utcnow() usage in sse-starlette.
    """
    warnings.filterwarnings(
        "ignore",
        message=".*the event_loop fixture provided by pytest-asyncio has been redefined.*",
        category=DeprecationWarning
    )
    warnings.filterwarnings(
        "ignore",
        message=".*datetime\\.datetime\\.utcnow\\(\\) is deprecated.*",
        category=DeprecationWarning
    )

@pytest.fixture(scope="session")
def test_files_dir() -> Path:
    """Return the path to the test files directory"""
    return Path(__file__).parent / "test_files"

@pytest.fixture
def test_client() -> Generator:
    """Create a test client for the FastAPI app"""
    with TestClient(app) as client:
        yield client

@pytest.fixture
def anyio_backend():
    return "asyncio"