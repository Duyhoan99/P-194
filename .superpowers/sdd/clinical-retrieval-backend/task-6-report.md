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

## Fix round 1: FastAPI validation trace IDs

### Reviewer finding addressed

FastAPI typed path/query validation happens before `_retrieve` and therefore bypassed the clinical domain-error handlers. Malformed clinical requests returned status `422` without `trace_id`.

### Files changed

- `src/api/clinical_routes.py`
  - Registers a `RequestValidationError` handler alongside the existing clinical handlers.
  - Delegates non-clinical requests to FastAPI's original `request_validation_exception_handler` unchanged.
  - For paths beginning `/api/v1/clinical/`, preserves the default safe `detail` and adds a server-generated canonical UUID-v4 `trace_id` with status `422`.
- `tests/test_api/test_clinical_routes.py`
  - Adds malformed `subject_id` and malformed `limit` regression tests requiring `422` plus UUID-v4 `trace_id`.
  - Adds a `/api/v1/chat` malformed request regression asserting no clinical `trace_id` is added.

### Fix-round red phase

Command:

```powershell
& 'C:\Users\daohi\OneDrive\Máy tính\GITHURB\P-194\.venv\Scripts\python.exe' -m pytest tests\test_api\test_clinical_routes.py -q
```

Output before the handler fix:

```text
...FF...........                                                         [100%]
2 failed, 14 passed in 0.26s
KeyError: 'trace_id' for malformed subject_id
KeyError: 'trace_id' for malformed limit
```

### Fix-round verification

Focused API tests:

```text
................                                                         [100%]
16 passed in 0.13s
```

Required regression command:

```text
.....................                                                    [100%]
21 passed in 0.26s
```

Full suite:

```text
..................................................................       [100%]
66 passed in 0.62s
```

Task lint:

```text
All checks passed!
```

`git diff --check` produced no output and exited 0.

### Fix-round self-review

- The handler uses the exact `/api/v1/clinical/` path prefix, so `/api/v1/chat` retains FastAPI's original validation response.
- The clinical body preserves FastAPI's existing `detail` payload and adds only a server-generated `str(uuid4())` trace ID.
- Malformed path and query validation are tested independently.
- No client-supplied trace, user, subject, or header is trusted.
- Existing domain errors, service-only route architecture, and `/api/v1/chat` behavior remain unchanged.

### Fix-round commit

`ab4050e0c9e60d9215eec8380c9f9bd68964f45b` — `fix: trace clinical validation errors`

## Fix round 2: validation response Content-Length

### Reviewer finding addressed

The clinical `RequestValidationError` handler copied the original FastAPI response headers after adding `trace_id`. That preserved a stale `Content-Length` and made the declared length differ from the actual response body.

### Files changed

- `src/api/clinical_routes.py`
  - Stops copying the original response headers into the new `JSONResponse`.
  - Lets `JSONResponse` preserve its normal safe JSON content type and recalculate `Content-Length` from the augmented body.
- `tests/test_api/test_clinical_routes.py`
  - Adds a focused clinical validation test asserting `Content-Length == len(response.content)`.

### Fix-round red phase

Command:

```powershell
& 'C:\Users\daohi\OneDrive\Máy tính\GITHURB\P-194\.venv\Scripts\python.exe' -m pytest tests\test_api\test_clinical_routes.py -q
```

Output before the header fix:

```text
.....F...........                                                        [100%]
1 failed, 16 passed in 0.16s
assert 162 == 212
```

The failing test observed the stale `Content-Length` header of 162 bytes versus the actual 212-byte body.

### Fix-round verification

Focused API tests:

```text
.................                                                        [100%]
17 passed in 0.14s
```

Chat and required regression tests:

```text
......................                                                   [100%]
22 passed in 0.20s
```

Full suite:

```text
...................................................................      [100%]
67 passed in 0.67s
```

Task lint:

```text
All checks passed!
```

`git diff --check` produced no output and exited 0.

### Fix-round self-review

- Clinical validation responses now use `JSONResponse`'s recalculated headers; no stale `Content-Length` is copied.
- The test checks the actual serialized response bytes, not only header presence.
- The clinical-only path filter and server-generated UUID-v4 trace ID remain unchanged.
- `/api/v1/chat` continues to use FastAPI's original validation handler and has a regression assertion that no clinical `trace_id` is added.
- No SQL, domain joins, client identity, or route/service contracts changed.

### Fix-round 2 commit

`21e018ba21a9b354a2b45cedf71bf76308f4dce2` — `fix: recalculate clinical validation length`
