# Clinical Retrieval Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the clinical retrieval backend so local MIMIC-IV development cannot be mistaken for production, while adding safe pagination, trusted authorization boundaries, and a PostgreSQL production adapter.

**Architecture:** The service and response contracts remain backend-agnostic. SQLite remains a read-only local/test adapter; PostgreSQL is selected explicitly in production through configuration, with no fallback. Authentication and assignment are protocols supplied by the deploying organization; until they are configured, clinical access remains fail-closed.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite stdlib, optional psycopg 3 for PostgreSQL, pytest, httpx, Ruff, loguru.

## Global Constraints

- MIMIC-IV 3.1 is a de-identified development/research profile, not a live production patient source.
- No patient count, subject ID, encounter ID, fixture size, or database backend is hard-coded for production.
- Production must explicitly select PostgreSQL and must never silently fall back to SQLite.
- Production clinical access requires a trusted authentication and assignment provider; client-supplied identity, role, or assignments are never authorization evidence.
- SQLite and PostgreSQL repositories use parameterized, allow-listed queries and read-only database access.
- Public pagination uses a bounded, authenticated, expiring cursor; `limit` remains the per-page size for compatibility.
- Cursor scope includes endpoint, subject, hadm/stay filters, time filters, source profile, and ordering version.
- Event ordering uses effective event time plus typed source columns; it never sorts by rendered `source_row_key`.
- Missing data, missing lineage, unavailable sources, timeouts, authorization failures, and database errors fail closed or are represented explicitly.
- No raw clinical values, secrets, tokens, SQL parameters, or MIMIC rows are added to tests, logs, prompts, or AI logs.
- Every task adds tests before implementation, runs focused tests, and ends with a separate commit.

---

## File Map

| File | Responsibility |
|---|---|
| `src/config.py` | Backend/source/auth/cursor settings and production validation |
| `src/clinical/schemas.py` | Cursor, source profile, query, page metadata, lineage and response contracts |
| `src/clinical/pagination.py` | HMAC-signed cursor encode/decode and query binding |
| `src/clinical/access.py` | Auth and assignment protocols plus development-only provider |
| `src/api/dependencies.py` | Explicit backend factory and trusted auth dependency boundary |
| `src/clinical/repository.py` | SQLite query ordering, cursor boundaries and repository protocol |
| `src/clinical/postgres_repository.py` | Optional PostgreSQL read-only adapter with statement timeout |
| `src/api/clinical_routes.py` | Cursor query parameters and page response serialization |
| `src/agents/tools/clinical_tools.py` | Cursor-aware LangChain tool inputs |
| `tests/test_clinical/test_pagination.py` | Cursor integrity, expiry and query binding |
| `tests/test_clinical/test_access.py` | Provider boundary and fail-closed production behavior |
| `tests/test_clinical/test_repository.py` | Stable ordering, null times and cursor page boundaries |
| `tests/test_api/test_clinical_routes.py` | HTTP cursor/auth/backend contracts |
| `tests/test_clinical/test_postgres_repository.py` | Optional PostgreSQL contract tests, skipped without explicit test DSN |
| `scripts/check_clinical_indexes.py` | Read-only query-plan/index inspection; never mutates the database |
| `README.md` | Deployment boundary, source profiles, configuration and rollout warnings |
| `requirements.txt` | Optional PostgreSQL dependency declaration |

Baseline before each task: `pytest -q` must pass. If a regression appears, stop that task and record the cause before continuing.

## Task 1: Production configuration and contracts

**Files:**
- Modify: `src/config.py`
- Modify: `src/clinical/schemas.py`
- Test: `tests/test_clinical/test_schemas.py`

**Interfaces:**
- `Settings.clinical_backend: Literal["sqlite", "postgresql"]`.
- `Settings.clinical_postgres_dsn: str` and `clinical_pool_size: int`.
- `Settings.clinical_source_dataset`, `clinical_source_version`, `clinical_source_profile`.
- `Settings.clinical_cursor_secret`, `clinical_cursor_ttl_seconds`, `clinical_max_limit`.
- `ClinicalQuery(..., cursor: str | None = None)` keeps `limit` as page size.
- `ClinicalPage(next_cursor: str | None, has_more: bool)`.
- `ClinicalResponse.page: ClinicalPage` with a backward-compatible default.

- [ ] **Step 1: Write failing contract tests**

```python
def test_production_settings_require_explicit_backend_and_cursor_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CLINICAL_CURSOR_SECRET", raising=False)
    monkeypatch.setenv("CLINICAL_BACKEND", "sqlite")
    with pytest.raises(ValueError):
        Settings()


def test_query_rejects_naive_datetimes_and_bounds_limit_and_cursor():
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=101, from_time=datetime(2025, 1, 1))
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=101, limit=1001)
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=101, cursor="x" * 10001)
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest tests/test_clinical/test_schemas.py -q`  
Expected: FAIL because backend/source/cursor settings and cursor/page contracts are not defined.

- [ ] **Step 3: Implement the minimal settings and models**

Use `model_validator` to require a non-empty cursor secret and explicit PostgreSQL DSN when `app_env == "production"`; reject naive `from_time` or `to_time` individually, not only mixed awareness. Keep `ClinicalResponse.page` defaulted so existing fixtures remain valid.

- [ ] **Step 4: Run focused and regression tests**

Run: `pytest tests/test_clinical/test_schemas.py tests/test_api/test_routes.py tests/test_agents/test_graph.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config.py src/clinical/schemas.py tests/test_clinical/test_schemas.py
git commit -m "feat: add production clinical source contracts"
```

## Task 2: Auth and assignment provider boundary

**Files:**
- Modify: `src/clinical/access.py`
- Modify: `src/api/dependencies.py`
- Test: `tests/test_clinical/test_access.py`
- Test: `tests/test_api/test_clinical_routes.py`

**Interfaces:**
- `AuthProvider.authenticate(request: Request) -> AccessContext`.
- `AssignmentProvider.assert_access(context: AccessContext, subject_id: int, hadm_id: int | None, stay_id: int | None) -> None`.
- `ConfiguredAuthProvider` is an integration boundary that raises `ClinicalAuthNotConfigured` until a trusted implementation is injected/configured.
- `DemoAssignmentProvider` remains test/development-only and cannot be constructed in production.

- [ ] **Step 1: Write failing provider tests**

```python
def test_production_auth_dependency_never_uses_client_identity(client):
    response = client.get(
        "/api/v1/clinical/patients/101/labs",
        headers={"X-User-Id": "doctor-1", "X-Role": "ADMIN"},
    )
    assert response.status_code == 503


def test_demo_provider_is_rejected_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    with pytest.raises(ClinicalAuthNotConfigured):
        DemoAssignmentProvider({"doctor-1": {101}}, set())
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest tests/test_clinical/test_access.py tests/test_api/test_clinical_routes.py -q`  
Expected: FAIL because the provider protocols and explicit production boundary are incomplete.

- [ ] **Step 3: Implement fail-closed provider wiring**

Make the FastAPI dependency call only `AuthProvider`; remove any implication that headers can create an `AccessContext`. Keep dependency overrides as the only path for tests. Ensure authorization runs before repository scope validation and that hadm/stay scope is passed to the assignment provider.

- [ ] **Step 4: Run focused and regression tests**

Run: `pytest tests/test_clinical/test_access.py tests/test_api/test_clinical_routes.py tests/test_api/test_routes.py -q`  
Expected: PASS; `/api/v1/chat` remains unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/clinical/access.py src/api/dependencies.py tests/test_clinical/test_access.py tests/test_api/test_clinical_routes.py
git commit -m "feat: enforce trusted clinical authorization boundary"
```

## Task 3: Signed cursor pagination

**Files:**
- Create: `src/clinical/pagination.py`
- Modify: `src/clinical/service.py`
- Modify: `src/clinical/repository.py`
- Test: `tests/test_clinical/test_pagination.py`
- Test: `tests/test_clinical/test_service.py`

**Interfaces:**
- `CursorBinding(endpoint: str, subject_id: int, hadm_id: int | None, stay_id: int | None, from_time: datetime | None, to_time: datetime | None, source_profile: str, order_version: str)`.
- `CursorPosition(event_time: datetime | None, domain: str, source_key: str)`.
- `CursorPayload(binding: CursorBinding, position: CursorPosition, issued_at: datetime, expires_at: datetime)`.
- `encode_cursor(payload: CursorPayload, secret: str, now: datetime | None = None) -> str`.
- `decode_cursor(token: str, secret: str, expected: CursorBinding, now: datetime | None = None) -> CursorPayload` raises `ClinicalScopeInvalid` for tampering, expiry, or binding mismatch.
- `ClinicalRepository.fetch_*` accepts `cursor_position: CursorPosition | None = None`.
- `RepositoryFetch(records, unavailable_sources, next_position: CursorPosition | None, has_more: bool)`.

- [ ] **Step 1: Write failing cursor tests**

```python
def test_cursor_round_trip_and_binding(secret):
    binding = CursorBinding(
        endpoint="labs", subject_id=101, hadm_id=None, stay_id=None,
        from_time=None, to_time=None, source_profile="mimic-iv-3.1", order_version="v1",
    )
    payload = CursorPayload(
        binding=binding,
        position=CursorPosition(event_time=aware("2125-01-01T10:00:00Z"), domain="labevents", source_key="9001"),
        issued_at=aware("2025-01-01T00:00:00Z"),
        expires_at=aware("2025-01-02T00:00:00Z"),
    )
    token = encode_cursor(payload, secret)
    assert decode_cursor(token, secret, binding) == payload
    with pytest.raises(ClinicalScopeInvalid):
        decode_cursor(token, secret, binding.model_copy(update={"subject_id": 202}))


def test_expired_or_modified_cursor_is_rejected(secret):
    binding = CursorBinding(
        endpoint="labs", subject_id=101, hadm_id=None, stay_id=None,
        from_time=None, to_time=None, source_profile="mimic-iv-3.1", order_version="v1",
    )
    payload = CursorPayload(
        binding=binding,
        position=CursorPosition(event_time=None, domain="labevents", source_key="9001"),
        issued_at=aware("2025-01-01T00:00:00Z"),
        expires_at=aware("2025-01-01T00:00:01Z"),
    )
    token = encode_cursor(payload, secret)
    with pytest.raises(ClinicalScopeInvalid):
        decode_cursor(token + "x", secret, binding, now=aware("2025-01-01T00:00:01Z"))
    with pytest.raises(ClinicalScopeInvalid):
        decode_cursor(token, secret, binding, now=aware("2025-01-01T00:00:02Z"))
```

- [ ] **Step 2: Run cursor tests and verify failure**

Run: `pytest tests/test_clinical/test_pagination.py -q`  
Expected: FAIL because the pagination module does not exist.

- [ ] **Step 3: Implement HMAC cursor encoding**

Serialize only JSON-safe fields, include an issued-at and expiry timestamp, sign the canonical payload with HMAC-SHA256, use constant-time signature comparison, and reject unknown fields or oversized tokens. Never put clinical values in the cursor; source keys and timestamps are identifiers needed only for the page boundary.

- [ ] **Step 4: Thread cursor through service and repository contracts**

Validate and decode the cursor before `validate_scope` or any fetch. Bind the decoded cursor to the current query and endpoint. Return `next_cursor` only when the repository fetched one extra record beyond the requested page size.

- [ ] **Step 5: Run focused and regression tests**

Run: `pytest tests/test_clinical/test_pagination.py tests/test_clinical/test_service.py tests/test_clinical/test_repository.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/clinical/pagination.py src/clinical/service.py src/clinical/repository.py tests/test_clinical/test_pagination.py tests/test_clinical/test_service.py
git commit -m "feat: add bound clinical cursor pagination"
```

## Task 4: Correct SQLite ordering and page boundaries

**Files:**
- Modify: `src/clinical/repository.py`
- Modify: `tests/clinical_fixtures.py`
- Test: `tests/test_clinical/test_repository.py`

**Interfaces:**
- Each fetch method applies one deterministic domain order and returns at most `limit + 1` rows to compute `has_more`.
- Composite domain methods merge rows before applying the page boundary.
- `COALESCE(charttime, storetime)` is used consistently for event filtering, ordering, cursor values, and lineage event time where applicable.

- [ ] **Step 1: Write failing repository tests**

```python
def test_labs_are_newest_first_with_stable_numeric_tie_break(tmp_path):
    repo = repository_with_rows(tmp_path, same_charttime=True, ids=[9, 10])
    result = repo.fetch_laboratory_results(ClinicalQuery(subject_id=101, limit=1))
    assert result.records[0].lineage.source_row_key == "labevent_id=10"
    assert result.has_more is True


def test_missing_charttime_uses_storetime_for_window_and_lineage(tmp_path):
    repo = repository_with_missing_charttime(tmp_path)
    result = repo.fetch_laboratory_results(
        ClinicalQuery(subject_id=101, from_time=aware("2125-01-01T09:00:00Z"))
    )
    assert result.records[0].lineage.event_time == aware("2125-01-01T10:00:00Z")


def test_cursor_page_has_no_duplicates_or_gaps(tmp_path):
    repo = repository_with_rows(tmp_path, same_charttime=False, ids=[1, 2, 3])
    first = repo.fetch_laboratory_results(ClinicalQuery(subject_id=101, limit=2))
    second = repo.fetch_laboratory_results(ClinicalQuery(subject_id=101, limit=2), first.next_position)
    assert [r.lineage.source_row_key for r in first.records + second.records] == [
        "labevent_id=3", "labevent_id=2", "labevent_id=1"
    ]
```

- [ ] **Step 2: Run repository tests and verify failure**

Run: `pytest tests/test_clinical/test_repository.py -q`  
Expected: FAIL because current queries sort ascending, do not use a consistent effective time, and do not implement cursor boundaries.

- [ ] **Step 3: Implement typed deterministic ordering**

Use native columns in SQL tie-breakers. Use explicit `NULLS LAST` semantics compatible with SQLite. Apply the same effective time expression to `WHERE`, `ORDER BY`, selected `event_time`, and cursor extraction. Fetch one extra row and apply the cursor boundary before returning. Do not independently limit each source in a composite response before the global merge.

- [ ] **Step 4: Run focused and regression tests**

Run: `pytest tests/test_clinical/test_repository.py tests/test_clinical/test_service.py tests/test_api/test_clinical_routes.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/clinical/repository.py tests/clinical_fixtures.py tests/test_clinical/test_repository.py
git commit -m "fix: make clinical pages stable and source ordered"
```

## Task 5: Cursor-aware API and LangChain tools

**Files:**
- Modify: `src/api/clinical_routes.py`
- Modify: `src/agents/tools/clinical_tools.py`
- Modify: `tests/test_api/test_clinical_routes.py`
- Modify: `tests/test_clinical/test_tools.py`

**Interfaces:**
- Every clinical route accepts `cursor: str | None = None` and existing `limit` as page size.
- Every clinical tool accepts `cursor` and returns `page.next_cursor`/`page.has_more`.
- Invalid cursor returns `422` before service/repository invocation.

- [ ] **Step 1: Write failing API/tool tests**

```python
async def test_clinical_route_returns_next_cursor(authenticated_client, fake_service):
    fake_service.next_cursor = "signed-cursor"
    response = await authenticated_client.get("/api/v1/clinical/patients/101/labs?limit=1")
    assert response.status_code == 200
    assert response.json()["page"]["next_cursor"] == "signed-cursor"


async def test_invalid_cursor_does_not_call_service(authenticated_client, fake_service):
    response = await authenticated_client.get("/api/v1/clinical/patients/101/labs?cursor=bad")
    assert response.status_code == 422
    assert fake_service.fetch_calls == []
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest tests/test_api/test_clinical_routes.py tests/test_clinical/test_tools.py -q`  
Expected: FAIL because routes and tool schemas do not expose cursor/page metadata.

- [ ] **Step 3: Implement cursor plumbing**

Pass cursor into `ClinicalQuery`, serialize `ClinicalResponse` with JSON-safe page metadata, and keep `access_context` closure-bound. Do not expose cursor internals in route errors.

- [ ] **Step 4: Run API/tool/regression tests**

Run: `pytest tests/test_api/test_clinical_routes.py tests/test_clinical/test_tools.py tests/test_api/test_routes.py tests/test_agents/test_graph.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/clinical_routes.py src/agents/tools/clinical_tools.py tests/test_api/test_clinical_routes.py tests/test_clinical/test_tools.py
git commit -m "feat: expose safe clinical pagination"
```

## Task 6: PostgreSQL production adapter and backend factory

**Files:**
- Create: `src/clinical/postgres_repository.py`
- Modify: `src/api/dependencies.py`
- Modify: `requirements.txt`
- Modify: `.env.example`
- Test: `tests/test_clinical/test_postgres_repository.py`
- Test: `tests/test_api/test_clinical_routes.py`

**Interfaces:**
- `PostgresClinicalRepository(dsn: str, query_timeout_seconds: float, pool_size: int)` implements every `ClinicalRepository` method.
- `build_clinical_repository(settings: Settings) -> ClinicalRepository` selects SQLite or PostgreSQL explicitly and raises `ClinicalDatabaseUnavailable` for unsupported/missing production configuration.

- [ ] **Step 1: Write failing factory/adapter tests**

```python
def test_production_factory_does_not_fallback_to_sqlite(monkeypatch):
    settings = Settings(
        app_env="production", clinical_backend="postgresql",
        clinical_postgres_dsn="", clinical_cursor_secret="test-secret",
    )
    with pytest.raises(ClinicalDatabaseUnavailable):
        build_clinical_repository(settings)


def test_postgres_contract_is_skipped_without_explicit_test_dsn():
    dsn = os.getenv("CLINICAL_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("CLINICAL_TEST_POSTGRES_DSN is not configured")
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest tests/test_clinical/test_postgres_repository.py tests/test_api/test_clinical_routes.py -q`  
Expected: FAIL because the factory and PostgreSQL adapter do not exist.

- [ ] **Step 3: Implement explicit backend selection**

Add the optional psycopg dependency. Use parameterized SQL and a pool with bounded connections. Set a per-transaction `statement_timeout`, use a read-only transaction/role, close connections on shutdown, and map driver errors to domain errors. Keep imports lazy enough that local SQLite tests work without a PostgreSQL server, while production startup fails clearly if the PostgreSQL driver or DSN is absent.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_clinical/test_postgres_repository.py tests/test_clinical/test_repository.py tests/test_api/test_clinical_routes.py -q`  
Expected: PASS; PostgreSQL integration tests are skipped only when the explicit test DSN is absent.

- [ ] **Step 5: Commit**

```bash
git add src/clinical/postgres_repository.py src/api/dependencies.py requirements.txt .env.example tests/test_clinical/test_postgres_repository.py tests/test_api/test_clinical_routes.py
git commit -m "feat: add explicit PostgreSQL clinical backend"
```

## Task 7: Index inspection, operational docs and final hardening

**Files:**
- Create: `scripts/check_clinical_indexes.py`
- Modify: `README.md`
- Modify: `docker-compose.yml`
- Modify: `tests/test_clinical/test_repository.py`
- Test: `tests/test_api/test_clinical_routes.py`

- [ ] **Step 1: Write failing safety/regression tests**

```python
async def test_cursor_is_bound_to_subject_and_page_size(authenticated_client, fake_service):
    response = await authenticated_client.get(
        "/api/v1/clinical/patients/202/labs?cursor=signed-for-101"
    )
    assert response.status_code == 422
    assert fake_service.fetch_calls == []


def test_missing_source_is_not_reported_as_success(assigned_service):
    response = assigned_service.get_laboratory_results(
        allowed_context(), ClinicalQuery(subject_id=101)
    )
    assert response.status in {"PARTIAL", "NOT_LOADED"}
    assert response.status != "SUCCESS"
```

Add companion tests for page-size bounds, null-time ordering, no raw value in audit/error bodies, unauthorized subject isolation, no SQLite fallback in production, and cursor tampering/expiry.

- [ ] **Step 2: Implement read-only index/query-plan inspection**

`check_clinical_indexes.py` accepts an explicit database path, opens SQLite read-only, prints only table/index names and query-plan summaries, and returns non-zero when required indexes are absent. It never executes `CREATE INDEX`, never prints row values, and never accepts arbitrary SQL from arguments.

- [ ] **Step 3: Update deployment documentation**

Document local/test MIMIC usage, production PostgreSQL and auth requirements, source profile configuration, cursor pagination, read-only role, migration/index process, health/readiness behavior, rollback, backups, and the fact that test success is not clinical approval. Add a compose profile that does not mount a demo SQLite file as a production database.

- [ ] **Step 4: Run quality checks**

Run:

```bash
pytest -q
ruff check src tests scripts/check_clinical_indexes.py
git diff --check
```

Expected: all tests pass, the changed clinical code has no Ruff errors, and no raw clinical values/secrets appear in changed files or logs. Legacy logging/setup scripts are outside this hardening scope.

- [ ] **Step 5: Commit final hardening**

```bash
git add scripts/check_clinical_indexes.py README.md docker-compose.yml tests/test_clinical/test_repository.py tests/test_api/test_clinical_routes.py
git commit -m "test: harden clinical retrieval for production rollout"
```

## Self-review checklist

- Every production requirement in the approved design has a task and a test.
- MIMIC is never described as a live clinical source.
- PostgreSQL is explicit in production and SQLite fallback is impossible.
- Auth and assignment are trusted-provider boundaries and fail closed.
- Cursor binding, expiry, tamper detection, ordering and page boundaries are tested.
- Composite clinical domains apply a global page boundary after deterministic merge.
- Index inspection is read-only and does not mutate source databases.
- Existing chat/graph behavior remains covered by regression tests.
