"""Repository-wide pytest bootstrap settings."""

import getpass
import os
import re
import subprocess
from pathlib import Path

import pytest

# The repository may be configured for a live LLM in a developer's ignored
# .env file.  Test collection must stay deterministic and must never make
# network calls merely because that local file is present.
os.environ.setdefault("AGENT_GENERATION_BACKEND", "deterministic")


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Choose the temp root before pytest creates its TempPathFactory."""
    if config.option.basetemp is not None:
        return
    identity = getpass.getuser()
    if os.name == "nt":
        try:
            identity = subprocess.check_output(["whoami"], text=True).strip()
        except (OSError, subprocess.SubprocessError):
            pass
    safe_user = re.sub(r"[^A-Za-z0-9_.-]+", "-", identity)
    config.option.basetemp = str(
        Path(__file__).resolve().parent / f".pytest-tmp-{safe_user}-{os.getpid()}"
    )
