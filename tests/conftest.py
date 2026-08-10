import getpass
import os
import re
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app

pytest_plugins = ("tests.test_clinical.conftest",)


def pytest_sessionstart(session):
    """Keep Windows temp ACLs isolated between users and sandbox runners."""
    config = session.config
    if config.option.basetemp is None:
        identity = getpass.getuser()
        if os.name == "nt":
            try:
                identity = subprocess.check_output(["whoami"], text=True).strip()
            except (OSError, subprocess.SubprocessError):
                pass
        safe_user = re.sub(r"[^A-Za-z0-9_.-]+", "-", identity)
        config.option.basetemp = str(Path(__file__).resolve().parents[1] / f".pytest-tmp-{safe_user}")


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
