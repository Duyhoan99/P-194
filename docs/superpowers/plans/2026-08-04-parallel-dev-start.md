# Parallel Development Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let developers start the FastAPI backend and Next.js frontend together with one local PowerShell command or one Docker Compose command.

**Architecture:** Add a Windows PowerShell process supervisor that starts `python -m uvicorn` and `npm.cmd --prefix frontend run dev`, forwards the current environment, monitors both children, and cleans up the sibling on exit. Keep Docker Compose as the containerized supervisor and expose it through an explicit Make target while documenting both workflows.

**Tech Stack:** PowerShell, Python/Uvicorn, Next.js/npm, Docker Compose, Make, pytest.

## Global Constraints

- Local development uses the existing backend port `8000` and frontend port `3000`.
- The local launcher must prefer `.venv\Scripts\python.exe` and must not silently create databases or change production configuration.
- Docker development must continue using the existing `local` Compose profile and synthetic-only database boundary.
- Existing unrelated working-tree changes must remain untouched.

---

### Task 1: Add the local process supervisor

**Files:**
- Create: `scripts/start-dev.ps1`
- Create: `tests/test_dev_launcher.py`

**Interfaces:**
- The launcher accepts an optional `-CheckOnly` switch for deterministic validation without starting child processes.
- `scripts/start-dev.ps1` starts backend and frontend together, waits while both are alive, and returns non-zero if either fails.

- [ ] **Step 1: Write the failing integration test**

```python
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_local_launcher_check_only_validates_the_project():
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "start-dev.ps1"),
            "-CheckOnly",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Validation passed" in result.stdout
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_dev_launcher.py::test_local_launcher_check_only_validates_the_project -q`

Expected: FAIL because `scripts/start-dev.ps1` does not exist yet.

- [ ] **Step 3: Implement the minimal launcher**

Implement these PowerShell behaviors:

```powershell
param([switch]$CheckOnly)

# Resolve the repository root from $PSScriptRoot\.. and validate:
# - .venv\Scripts\python.exe when present, otherwise python on PATH
# - npm.cmd on PATH
# - frontend\package.json
#
# In normal mode:
# - set NEXT_PUBLIC_API_URL to http://localhost:8000 only when it is unset
# - start `python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000`
# - start `npm.cmd --prefix frontend run dev`
# - poll both Process objects every 250ms
# - stop the sibling process when one exits
# - stop both processes in a finally block, including Ctrl+C cleanup
# - return the first non-zero child exit code, or 0 on clean termination
```

Use `Start-Process -PassThru -NoNewWindow` so both logs remain in the invoking terminal. Quote paths with `-LiteralPath` where applicable and do not use broad process-kill commands.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_dev_launcher.py::test_local_launcher_check_only_validates_the_project -q`

Expected: PASS and the launcher prints `Validation passed` without starting Uvicorn or Next.js.

- [ ] **Step 5: Commit the launcher**

```powershell
git add scripts/start-dev.ps1 tests/test_dev_launcher.py
git commit -m "feat: add local parallel dev launcher"
```

### Task 2: Expose and document both startup paths

**Files:**
- Modify: `Makefile:1-21`
- Modify: `README.md` in the local development and synthetic demo startup sections
- Modify: `docs/guide/setup/quick-start.md` in the Windows quick-start section

**Interfaces:**
- `make dev-local` invokes `scripts/start-dev.ps1` through PowerShell on Windows.
- `make demo-up` remains the Docker Compose command for both services.

- [ ] **Step 1: Add the Make target**

Add `dev-local` to `.PHONY` and define:

```make
dev-local:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-dev.ps1
```

Keep `demo-up` unchanged so existing Docker usage remains compatible.

- [ ] **Step 2: Update user-facing documentation**

Replace the two-terminal local command sequence with:

```powershell
# Prepare once
python scripts/create_synthetic_demo.py data/synthetic_demo.db
npm.cmd --prefix frontend install

# Start backend and frontend together
.\scripts\start-dev.ps1
```

Document Docker separately:

```powershell
make demo-db
docker compose --profile local up --build
```

State that local mode requires Python dependencies and frontend `node_modules`, while Docker mode requires Docker Desktop; both expose `http://localhost:3000` and `http://localhost:8000`.

- [ ] **Step 3: Validate documentation commands and Makefile syntax**

Run: `git diff --check`

Expected: no whitespace errors, and only the intended Makefile/documentation lines are changed.

- [ ] **Step 4: Commit the workflow documentation**

```powershell
git add Makefile README.md docs/guide/setup/quick-start.md
git commit -m "docs: document parallel local and docker startup"
```

### Task 3: Run focused and regression verification

**Files:**
- No source changes expected.

- [ ] **Step 1: Run launcher validation and backend tests**

Run: `python -m pytest tests/test_dev_launcher.py tests/test_api/test_routes.py -q`

Expected: PASS.

- [ ] **Step 2: Run frontend unit tests and build**

Run: `npm.cmd --prefix frontend test -- --run` and `npm.cmd --prefix frontend run build`

Expected: both commands complete successfully.

- [ ] **Step 3: Validate the Compose file structurally**

Run: `docker compose config`

Expected: exit code 0. If Docker is unavailable, record that limitation without changing the Compose file.

- [ ] **Step 4: Review the final diff and status**

Run: `git diff HEAD~2 --check; git status --short`

Expected: no whitespace errors; unrelated pre-existing modifications remain present and are not staged by this change.
