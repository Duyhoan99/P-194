# Task 6 report: FastAPI dependency wiring and REST routes

## Files

- `src/api/dependencies.py`
  - Builds `ClinicalRetrievalService` with `SQLiteClinicalRepository`, the configured clinical database path and timeout, a fail-closed service checker, and `StructuredAuditSink`.
  - Provides a default `get_access_context()` dependency that creates a server-side trace ID and raises `ClinicalAuthNotConfigured` without reading client headers or identifiers.
- `src/api/clinical_routes.py`
  - Adds the separate clinical router and six documented routes:
    - `GET /api/v1/clinical/patients/{subject_id}`
    - `GET /api/v1/clinical/patients/{subject_id}/timeline`
    - `GET /api/v1/clinical/patients/{subject_id}/diagnoses-procedures`
    - `GET /api/v1/clinical/patients/{subject_id}/labs`
    - `GET /api/v1/clinical/patients/{subject_id}/microbiology`
    - `GET /api/v1/clinical/patients/{subject_id}/icu-events`
  - Maps query parameters to `ClinicalQuery`, calls one `ClinicalRetrievalService` method per route, serializes safe domain errors, and registers the required HTTP mappings with a trace ID in every clinical result/error body.
- `src/main.py`
  - Includes the clinical router under `/api/v1` and registers clinical domain-error handlers. Existing chat/status/health routes remain unchanged.
- `tests/test_api/test_clinical_routes.py`
  - Uses FastAPI dependency overrides with the existing fake service and allowed access context; it never requires `mimic_demo.db`.
  - Covers fail-closed auth, invalid scope, lineage, denied responses, all requested service-error mappings, trace IDs, and all six service delegations.

## Verification

All Python commands used the project virtualenv:

`C:\Users\daohi\OneDrive\Máy tính\GITHURB\P-194\.venv\Scripts\python.exe`

### Required focused red phase

Command:

```powershell
& 'C:\Users\daohi\OneDrive\Máy tính\GITHURB\P-194\.venv\Scripts\python.exe' -m pytest tests\test_api\test_clinical_routes.py -q
```

Output before implementation:

```text
E   ModuleNotFoundError: No module named 'src.api.dependencies'
1 error during collection
```

### Focused API tests

Command:

```powershell
& 'C:\Users\daohi\OneDrive\Máy tính\GITHURB\P-194\.venv\Scripts\python.exe' -m pytest tests\test_api\test_clinical_routes.py -q
```

Output:

```text
.............                                                            [100%]
13 passed in 0.10s
```

### Task-required regression tests

Command:

```powershell
& 'C:\Users\daohi\OneDrive\Máy tính\GITHURB\P-194\.venv\Scripts\python.exe' -m pytest tests\test_api\test_clinical_routes.py tests\test_api\test_routes.py tests\test_agents\test_graph.py -q
```

Output:

```text
..................                                                       [100%]
18 passed in 0.20s
```

### Task-specific lint

Command:

```powershell
& 'C:\Users\daohi\OneDrive\Máy tính\GITHURB\P-194\.venv\Scripts\python.exe' -m ruff check src\api\dependencies.py src\api\clinical_routes.py src\main.py tests\test_api\test_clinical_routes.py
```

Output:

```text
All checks passed!
```

### Full test suite

Command:

```powershell
& 'C:\Users\daohi\OneDrive\Máy tính\GITHURB\P-194\.venv\Scripts\python.exe' -m pytest -q
```

Output:

```text
...............................................................          [100%]
63 passed in 0.58s
```

### Full lint

Command:

```powershell
& 'C:\Users\daohi\OneDrive\Máy tính\GITHURB\P-194\.venv\Scripts\python.exe' -m ruff check src/ tests/
```

Output:

```text
Found 4 errors.
[*] 4 fixable with the `--fix` option.
```

The four findings are pre-existing `I001`/`W293` issues in `src/logger.py`; Task 6 files pass the task-specific lint command.

### Diff check

Command:

```powershell
git diff --check
```

Output: no output, exit code 0.

## Self-review

- Confirmed every clinical route only constructs `ClinicalQuery` and delegates to one `ClinicalRetrievalService` method; no route has SQL or domain joins.
- Confirmed the default access dependency ignores client-supplied headers/identifiers and raises `ClinicalAuthNotConfigured`; the fallback service checker cannot grant access.
- Confirmed dependency-overridden API tests use only the existing synthetic fake service and allowed context, so no route test opens the absent worktree database.
- Confirmed required mappings: auth-not-configured/database-unavailable `503`, access-denied `403`, invalid scope `422`, and timeout `504`.
- Confirmed every service response includes its existing `trace_id`; the clinical error serializer supplies the trusted context trace ID or creates a server-side UUID before an early dependency error.
- Confirmed the six documented endpoint paths and lineage serialization.
- Confirmed `/api/v1/chat` and graph regressions pass without modifying their route implementation.
- Confirmed focused tests, required regressions, full tests, task-specific lint, and diff checks.

## Commit

`99b290489fbf94a4aef97a6a6b0c00ac2a2a4c2b` — `feat: add clinical retrieval API`

## Concerns

- Production remains intentionally fail-closed until a trusted authentication provider replaces `get_access_context`; this is required behavior, so clinical endpoints return `503` by default.
- Repository-wide Ruff is non-zero because of four pre-existing findings in `src/logger.py`; Task 6 files are lint-clean.
- The requested independent read-only review could not start because the review-agent connector returned `McpServerError: Connection failed`; the in-session self-review and all stated verification commands completed.
