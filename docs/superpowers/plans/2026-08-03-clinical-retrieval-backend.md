# Clinical Retrieval Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng backend retrieval có kiểm soát quyền, lineage MIMIC-IV 3.1 và API/LangChain tools cho bệnh nhân, encounter, chẩn đoán, thủ thuật, xét nghiệm, vi sinh và ICU events.

**Architecture:** FastAPI và LangChain tools cùng gọi `ClinicalRetrievalService`. Service kiểm tra `AccessContext`, giới hạn scope và đóng gói kết quả; repository SQLite chỉ chứa SQL tham số hóa/allow-list và thực hiện đọc read-only từ `mimic_demo.db`. Tất cả record có `SourceLineage`, còn lỗi quyền/dữ liệu không chắc chắn được xử lý fail-closed.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, LangChain `StructuredTool`, SQLite stdlib `sqlite3`, pytest, httpx, loguru.

## Global Constraints

- Không đưa CSV/CSV.GZ MIMIC thô, restricted excerpt hoặc credential vào repository, test fixture, prompt hay AI log.
- Mọi truy vấn clinical phải có `AccessContext`; không tin user ID do client gửi trong production.
- `subject_id` bắt buộc; `hadm_id`/`stay_id` phải thuộc đúng subject trước khi query dữ liệu.
- SQL chỉ nằm trong repository, luôn tham số hóa và giới hạn bởi allow-list bảng/cột; không nhận SQL/table/column tùy ý từ client hoặc LLM.
- Giữ nguyên giá trị, đơn vị, reference range, flag và thời gian xét nghiệm; không tự đổi đơn vị hoặc bù khóa bị thiếu.
- Không suy diễn chẩn đoán, sự kiện, treatment hoặc dữ liệu không có trong nguồn.
- Bất kỳ record nào trả về cũng phải có dataset `MIMIC-IV`, version `3.1`, module, table, source row key và khóa bệnh nhân phù hợp.
- Auth chưa cấu hình thì clinical endpoint không được mở quyền mặc định; `DemoAssignmentProvider` chỉ dùng ở development/test và bị vô hiệu hóa ở production.
- Giữ nguyên `/api/v1/chat` skeleton; không nối nó vào dữ liệu clinical trong plan này.
- Mỗi task phải có test trước implementation, chạy test mục tiêu và commit riêng khi đạt.

---

## File map

| File | Trách nhiệm |
|---|---|
| `src/clinical/__init__.py` | Public exports tối thiểu của clinical package |
| `src/clinical/schemas.py` | Query, access, lineage, evidence và response models |
| `src/clinical/errors.py` | Domain errors và status mapping |
| `src/clinical/config.py` | Không tạo file mới; mở rộng `src/config.py` cho clinical settings |
| `src/clinical/access.py` | Assignment checker, demo provider và fail-closed authorization |
| `src/clinical/audit.py` | Audit event model/sink, không ghi clinical values |
| `src/clinical/availability.py` | Module/table availability và trạng thái `NOT_LOADED` |
| `src/clinical/repository.py` | Repository protocol, SQLite read-only adapter, allow-list SQL |
| `src/clinical/service.py` | Scope validation, retrieval orchestration, status/warning wrapping |
| `src/agents/tools/clinical_tools.py` | LangChain tool factory bound với access context |
| `src/api/dependencies.py` | Clinical DB/service/auth dependency wiring |
| `src/api/clinical_routes.py` | Sáu nhóm REST routes |
| `src/main.py` | Include clinical router |
| `tests/clinical_fixtures.py` | SQLite schema/rows mock tối thiểu, không phải raw MIMIC |
| `tests/test_clinical/conftest.py` | Shared test contexts, fake checker/repository/service |
| `tests/test_clinical/test_schemas.py` | Schema validation và query bounds |
| `tests/test_clinical/test_access.py` | Assignment và audit behavior |
| `tests/test_clinical/test_repository.py` | SQL retrieval, lineage, read-only behavior |
| `tests/test_clinical/test_service.py` | Service status, scope và partial data |
| `tests/test_clinical/test_tools.py` | LangChain tool binding |
| `tests/test_api/test_clinical_routes.py` | HTTP contract, errors và endpoint isolation |

Baseline trước khi bắt đầu: `pytest -q` phải vẫn đạt toàn bộ test hiện có; nếu baseline thay đổi, dừng và ghi nhận nguyên nhân trước Task 1.

## Task 1: Clinical contracts and settings

**Files:**
- Create: `src/clinical/__init__.py`
- Create: `src/clinical/schemas.py`
- Create: `src/clinical/errors.py`
- Modify: `src/config.py`
- Test: `tests/test_clinical/test_schemas.py`

**Interfaces:**
- Produces `ClinicalQuery`, `AccessContext`, `SourceLineage`, `EvidenceRecord`, `ClinicalResponse`, `ClinicalStatus` and domain errors used by every later task.
- `ClinicalQuery(subject_id: int, hadm_id: int | None = None, stay_id: int | None = None, from_time: datetime | None = None, to_time: datetime | None = None, limit: int = 200, offset: int = 0)` rejects non-positive IDs, `limit > settings.clinical_max_limit`, and `from_time > to_time`. Ensure `from_time` and `to_time` enforce timezone-aware datetime parsing to avoid naive datetime comparison errors.
- `SourceLineage(dataset: Literal["MIMIC-IV"], version: Literal["3.1"], module: Literal["hosp", "icu"], table: str, source_row_key: str, subject_id: int, hadm_id: int | None, stay_id: int | None, event_time: datetime | None)`.
- `EvidenceRecord(record_type: str, data: dict[str, Any], lineage: SourceLineage, related_sources: list[SourceLineage] = Field(default_factory=list))`.
- `ClinicalResponse(status: Literal["SUCCESS", "PARTIAL", "EMPTY", "DENIED", "NOT_LOADED"], records: list[EvidenceRecord], warnings: list[str], limitations: list[str], trace_id: str)`.
- `AccessContext(user_id: str, role: Literal["DOCTOR", "ADMIN"], assigned_subject_ids: set[int], trace_id: str)`.
- `ClinicalAuthNotConfigured`, `ClinicalAccessDenied`, `ClinicalScopeInvalid`, `ClinicalDatabaseUnavailable` and `ClinicalQueryTimeout` are concrete exception classes.

- [ ] **Step 1: Write failing contract tests**

```python
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.clinical.schemas import ClinicalQuery, SourceLineage


def test_query_requires_positive_subject_and_bounded_limit():
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=0)
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=1, limit=1001)
    with pytest.raises(ValidationError):
        ClinicalQuery(subject_id=1, offset=-1)


def test_query_rejects_reversed_time_window():
    with pytest.raises(ValidationError):
        ClinicalQuery(
            subject_id=1,
            from_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            to_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )


def test_lineage_requires_mimic_version_and_source_identity():
    lineage = SourceLineage(
        dataset="MIMIC-IV",
        version="3.1",
        module="hosp",
        table="labevents",
        source_row_key="labevent_id=1",
        subject_id=1,
        event_time=None,
    )
    assert lineage.table == "labevents"
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `pytest tests/test_clinical/test_schemas.py -q`  
Expected: FAIL because `src.clinical` and its models do not exist.

- [ ] **Step 3: Implement models and settings**

Add to `src/config.py` without changing the existing app database setting:

```python
clinical_database_path: str = "mimic_demo.db"
clinical_query_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
clinical_max_limit: int = Field(default=1000, ge=1, le=5000)
```

Use Pydantic validators for positive IDs, limit bounds and ordered times. Use mutable defaults only through `Field(default_factory=list)` or `Field(default_factory=set)`.

- [ ] **Step 4: Run focused and regression tests**

Run: `pytest tests/test_clinical/test_schemas.py tests/test_api/test_routes.py tests/test_agents/test_graph.py -q`  
Expected: PASS; existing `/chat`, health and graph behavior remains unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/clinical src/config.py tests/test_clinical/test_schemas.py
git commit -m "feat: add clinical retrieval contracts"
```

## Task 2: Access control and audit sink

**Files:**
- Create: `src/clinical/access.py`
- Create: `src/clinical/audit.py`
- Create: `tests/test_clinical/conftest.py`
- Test: `tests/test_clinical/test_access.py`

**Interfaces:**
- `AssignmentChecker.can_access(context: AccessContext, subject_id: int) -> bool`.
- `AssignmentChecker.assert_access(context: AccessContext, subject_id: int) -> None` raises `ClinicalAccessDenied`.
- `DemoAssignmentProvider(assignments: Mapping[str, set[int]], admin_users: set[str])` grants only explicitly assigned subjects to doctors; `ADMIN` access is explicit by `admin_users`, never by an arbitrary client header.
- `AuditEvent(user_id: str, action: str, subject_id: int, hadm_id: int | None, stay_id: int | None, result: str, trace_id: str, timestamp: datetime)` contains no clinical value.
- `AuditSink.record(event: AuditEvent) -> None`; provide `InMemoryAuditSink` for tests and `StructuredAuditSink` using loguru fields for development.
- Shared test helpers created here: `allowed_context() -> AccessContext` returns subject 101 assigned to `doctor-1`; `DenyAllChecker` raises `ClinicalAccessDenied`; `InMemoryAuditSink` is exposed as the `audit_sink` fixture.

- [ ] **Step 1: Write failing access and audit tests**

```python
from datetime import datetime, timezone

from src.clinical.access import DemoAssignmentProvider
from src.clinical.audit import AuditEvent, InMemoryAuditSink
from src.clinical.schemas import AccessContext


def test_doctor_can_access_only_assigned_subject():
    provider = DemoAssignmentProvider({"doctor-1": {10}}, set())
    context = AccessContext(user_id="doctor-1", role="DOCTOR", assigned_subject_ids={10}, trace_id="t1")
    provider.assert_access(context, 10)
    try:
        provider.assert_access(context, 11)
    except Exception as exc:
        assert exc.__class__.__name__ == "ClinicalAccessDenied"
    else:
        raise AssertionError("unassigned subject was accepted")


def test_audit_sink_keeps_scope_only():
    sink = InMemoryAuditSink()
    sink.record(AuditEvent(user_id="doctor-1", action="VIEW_LABS", subject_id=10,
                           hadm_id=20, stay_id=None, result="SUCCESS",
                           trace_id="t1", timestamp=datetime.now(timezone.utc)))
    assert sink.events[0].subject_id == 10
    assert not hasattr(sink.events[0], "raw_value")
```

- [ ] **Step 2: Run tests to verify the access layer is missing**

Run: `pytest tests/test_clinical/test_access.py -q`  
Expected: FAIL because the provider and sink do not exist.

- [ ] **Step 3: Implement fail-closed provider and sinks**

`assert_access` must compare the context assignment set with the requested subject and raise `ClinicalAccessDenied` before any repository call. `StructuredAuditSink` must emit only the fields on `AuditEvent`; never interpolate record values into the message.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/test_clinical/test_access.py -q`  
Expected: PASS, including an explicit test for an empty assignment set and a non-admin context.

- [ ] **Step 5: Commit**

```bash
git add src/clinical/access.py src/clinical/audit.py tests/test_clinical/test_access.py
git commit -m "feat: enforce clinical access context"
```

## Task 3: Read-only SQLite repository and availability

**Files:**
- Create: `src/clinical/availability.py`
- Create: `src/clinical/repository.py`
- Create: `tests/clinical_fixtures.py`
- Test: `tests/test_clinical/test_repository.py`

**Interfaces:**
- `SourceAvailability(available_tables: set[str], unavailable_modules: list[str])`.
- `RepositoryFetch(records: list[EvidenceRecord], unavailable_sources: list[str])`.
- `ClinicalRepository` methods: `validate_scope(query) -> bool`, `available_sources() -> SourceAvailability`, `fetch_patient_overview(query)`, `fetch_encounter_timeline(query)`, `fetch_diagnoses_and_procedures(query)`, `fetch_laboratory_results(query)`, `fetch_microbiology_results(query)`, `fetch_icu_events(query)`, each returning `RepositoryFetch`.
- `SQLiteClinicalRepository(db_path: str, query_timeout_seconds: float = 2.0)` opens SQLite using a read-only URI and `sqlite3.Row`.

- [ ] **Step 1: Build a safe mock database fixture**

Create `tests/clinical_fixtures.py` with `create_mock_clinical_db(path)` that creates only the columns used by the fixed queries, inserts two subjects, two admissions, one ICU stay, one diagnosis, one procedure, two labs, one microbiology row, one chart event and one output event. Use synthetic IDs and values such as `subject_id=101`; do not copy rows from `mimic_demo.db`.

- [ ] **Step 2: Write failing repository tests**

```python
def test_repository_returns_lab_value_and_lineage(tmp_path):
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)
    repo = SQLiteClinicalRepository(str(db_path))
    result = repo.fetch_laboratory_results(ClinicalQuery(subject_id=101))
    assert result.records[0].data["value"] == "1.2"
    assert result.records[0].lineage.table == "labevents"
    assert result.records[0].lineage.source_row_key == "labevent_id=9001"


def test_repository_is_read_only(tmp_path):
    db_path = tmp_path / "clinical.sqlite"
    create_mock_clinical_db(db_path)
    repo = SQLiteClinicalRepository(str(db_path))
    repo.fetch_patient_overview(ClinicalQuery(subject_id=101))
    with pytest.raises(sqlite3.OperationalError):
        repo.connection.execute("CREATE TABLE should_not_exist (id INTEGER)")
```

- [ ] **Step 3: Run repository tests and verify they fail**

Run: `pytest tests/test_clinical/test_repository.py -q`  
Expected: FAIL because the fixture/repository implementation is incomplete.

- [ ] **Step 4: Implement availability and fixed, parameterized queries**

Use a fixed query per domain. Bind values with SQLite parameters (`?`); never interpolate `subject_id`, filters or table names into SQL. Use explicit selected columns and deterministic ordering by source event time DESC, then source key DESC so the most recent events are returned first. Use `COALESCE(charttime, storetime)` for events missing a primary chart time to ensure timeline ordering is maintained. Keep source key construction deterministic for tables without a single row ID, for example `subject_id|hadm_id|stay_id|charttime|itemid|storetime` for `chartevents`.

Join only the approved dictionaries (`d_labitems`, `d_icd_diagnoses`, `d_icd_procedures`, `d_hcpcs`, `d_items`). If a source table is absent, return its name in `unavailable_sources` rather than inventing an empty clinical result.

- [ ] **Step 5: Run repository tests and a real-database smoke query**

Run: `pytest tests/test_clinical/test_repository.py -q`  
Expected: PASS. Then run a read-only smoke script against the configured `mimic_demo.db` for one subject selected by `SELECT subject_id FROM patients ORDER BY subject_id LIMIT 1`; print only counts and lineage table names, never clinical values.

- [ ] **Step 6: Commit**

```bash
git add src/clinical/availability.py src/clinical/repository.py tests/clinical_fixtures.py tests/test_clinical/test_repository.py
git commit -m "feat: add read-only clinical repository"
```

## Task 4: Retrieval service, scope checks and statuses

**Files:**
- Create: `src/clinical/service.py`
- Test: `tests/test_clinical/test_service.py`

**Interfaces:**
- `ClinicalRetrievalService(repository: ClinicalRepository, access_checker: AssignmentChecker, audit_sink: AuditSink)`.
- Public methods: `get_patient_overview(context, query)`, `get_encounter_timeline(context, query)`, `get_diagnoses_and_procedures(context, query)`, `get_laboratory_results(context, query)`, `get_microbiology_results(context, query)`, `get_icu_events(context, query)`, all returning `ClinicalResponse`.
- The service must call `access_checker.assert_access` before `repository.validate_scope`; a failed access check must produce a `DENIED` response only where the API policy explicitly serializes it, and must never call repository fetch methods.
- Extend `tests/test_clinical/conftest.py` with `FakeRepository` implementing every `ClinicalRepository` method, a `fake_repo` fixture exposing `fetch_calls`, and `assigned_service`/`fake_service` fixtures built from `FakeRepository`, `DemoAssignmentProvider` and `InMemoryAuditSink`.

- [ ] **Step 1: Write failing service tests**

```python
def test_service_denies_before_repository_fetch(fake_repo, audit_sink):
    service = ClinicalRetrievalService(fake_repo, DenyAllChecker(), audit_sink)
    context = AccessContext(user_id="doctor-1", role="DOCTOR", assigned_subject_ids=set(), trace_id="t1")
    result = service.get_laboratory_results(context, ClinicalQuery(subject_id=101))
    assert result.status == "DENIED"
    assert fake_repo.fetch_calls == []
    assert audit_sink.events[-1].result == "DENIED"


def test_service_marks_missing_source_partial(assigned_service):
    result = assigned_service.get_laboratory_results(
        allowed_context(), ClinicalQuery(subject_id=101)
    )
    assert result.status == "PARTIAL"
    assert "d_labitems" in " ".join(result.warnings)
```

The `FakeRepository.fetch_laboratory_results` fixture returns one `EvidenceRecord` plus `unavailable_sources=["d_labitems"]`; its other fetch methods return an empty `RepositoryFetch` and append their method name to `fetch_calls`.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest tests/test_clinical/test_service.py -q`  
Expected: FAIL because `ClinicalRetrievalService` does not exist.

- [ ] **Step 3: Implement service orchestration**

For each method: validate access, validate subject/encounter/ICU scope, call exactly one repository domain method, map `RepositoryFetch.unavailable_sources` to `PARTIAL` or `NOT_LOADED`, preserve empty results as `EMPTY`, attach the existing trace ID and write one audit event. Catch SQLite operational errors in the service boundary and map them to `ClinicalDatabaseUnavailable`; catch timeout errors and map them to `ClinicalQueryTimeout`. Do not include exception text containing SQL or values in the response.

- [ ] **Step 4: Run service and regression tests**

Run: `pytest tests/test_clinical/test_service.py tests/test_clinical/test_repository.py tests/test_api/test_routes.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/clinical/service.py tests/test_clinical/test_service.py
git commit -m "feat: add scoped clinical retrieval service"
```

## Task 5: LangChain clinical tools

**Files:**
- Create: `src/agents/tools/clinical_tools.py`
- Test: `tests/test_clinical/test_tools.py`

**Interfaces:**
- `build_clinical_tools(service: ClinicalRetrievalService, access_context: AccessContext) -> list[BaseTool]`.
- The factory returns tools named `get_patient_overview`, `get_encounter_timeline`, `get_diagnoses_and_procedures`, `get_laboratory_results`, `get_microbiology_results`, `get_icu_events`.
- Tool input schemas expose only `hadm_id`, `stay_id`, `from_time`, `to_time`, `limit`, `offset`; `subject_id` remains required in every tool input. `access_context` is bound by the factory and cannot be supplied by the model.
- Each invocation returns a JSON-serializable `ClinicalResponse` and never invokes the LLM.

- [ ] **Step 1: Write failing tool tests**

```python
def test_tool_factory_binds_context_and_exposes_safe_names(fake_service):
    context = allowed_context()
    tools = {tool.name: tool for tool in build_clinical_tools(fake_service, context)}
    assert set(tools) == {
        "get_patient_overview", "get_encounter_timeline",
        "get_diagnoses_and_procedures", "get_laboratory_results",
        "get_microbiology_results", "get_icu_events",
    }
    result = tools["get_laboratory_results"].invoke({"subject_id": 101, "limit": 1})
    assert result["trace_id"] == context.trace_id
    assert fake_service.last_context == context
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `pytest tests/test_clinical/test_tools.py -q`  
Expected: FAIL because the tool factory does not exist.

- [ ] **Step 3: Implement thin `StructuredTool` adapters**

Define one Pydantic args model shared by the six tools. Use a closure or `StructuredTool.from_function` to bind `access_context`; do not put authentication data in the model-visible arguments. Serialize the Pydantic response with `model_dump(mode="json")` so dates and nullable IDs are JSON safe.

- [ ] **Step 4: Run tool tests**

Run: `pytest tests/test_clinical/test_tools.py -q`  
Expected: PASS, including a test proving a caller cannot override the bound context.

- [ ] **Step 5: Commit**

```bash
git add src/agents/tools/clinical_tools.py tests/test_clinical/test_tools.py
git commit -m "feat: expose clinical retrieval tools"
```

## Task 6: FastAPI dependency wiring and REST routes

**Files:**
- Create: `src/api/dependencies.py`
- Create: `src/api/clinical_routes.py`
- Modify: `src/main.py`
- Test: `tests/test_api/test_clinical_routes.py`

**Interfaces:**
- `get_clinical_service() -> ClinicalRetrievalService` builds the repository from `settings.clinical_database_path` and the configured sinks.
- `get_access_context() -> AccessContext` must raise `ClinicalAuthNotConfigured` unless a real auth provider or explicitly allowed development/test provider exists.
- Each route maps query parameters into `ClinicalQuery` and calls one service method; routes must not contain SQL or domain joins.
- The test module defines `authenticated_client` by overriding `get_clinical_service` with `fake_service` and `get_access_context` with `allowed_context()`; it clears `app.dependency_overrides` in teardown.

- [ ] **Step 1: Write failing API tests**

```python
async def test_clinical_route_requires_auth(client):
    response = await client.get("/api/v1/clinical/patients/101/labs")
    assert response.status_code == 503


async def test_clinical_route_rejects_invalid_scope(authenticated_client):
    response = await authenticated_client.get(
        "/api/v1/clinical/patients/101/labs?hadm_id=999999"
    )
    assert response.status_code == 422


async def test_clinical_route_returns_lineage(authenticated_client):
    response = await authenticated_client.get(
        "/api/v1/clinical/patients/101/labs?limit=1"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["records"][0]["lineage"]["table"] == "labevents"
```

- [ ] **Step 2: Run API tests and verify failure**

Run: `pytest tests/test_api/test_clinical_routes.py -q`  
Expected: FAIL because the clinical router and dependency overrides do not exist.

- [ ] **Step 3: Implement dependency wiring and routes**

Create a separate `clinical_router`. Use FastAPI dependency overrides in tests to inject the mock service/context; do not make tests depend on a client-controlled user header. Map errors as follows: auth not configured `503`, access denied `403`, scope invalid `422`, database unavailable `503`, timeout `504`. Include a correlation/trace ID in every clinical response and error response.

Add to `src/main.py`:

```python
from src.api.clinical_routes import router as clinical_router

app.include_router(clinical_router, prefix="/api/v1")
```

- [ ] **Step 4: Run API and full regression tests**

Run: `pytest tests/test_api/test_clinical_routes.py tests/test_api/test_routes.py tests/test_agents/test_graph.py -q`  
Expected: PASS; `/api/v1/chat` continues to behave exactly as before.

- [ ] **Step 5: Commit**

```bash
git add src/api/dependencies.py src/api/clinical_routes.py src/main.py tests/test_api/test_clinical_routes.py
git commit -m "feat: add clinical retrieval API"
```

## Task 7: Hardening, documentation and final verification

**Files:**
- Modify: `README.md`
- Modify: `docs/guide/testing/writing-tests.md` only if the project testing guide needs the new commands
- Test: `tests/test_clinical/test_repository.py`, `tests/test_clinical/test_service.py`, `tests/test_api/test_clinical_routes.py`

- [ ] **Step 1: Add security regression tests**

Add tests that prove: a doctor assigned to subject 101 cannot retrieve subject 102; an assigned subject cannot query an unrelated `hadm_id`; an unrelated `stay_id` is rejected; a request with `limit=1001` is rejected; and a malformed filter cannot change the fixed SQL path.

- [ ] **Step 2: Add source integrity tests**

Compare returned lab `value`, `valuenum`, `valueuom`, `ref_range_lower`, `ref_range_upper` and `charttime` with the synthetic fixture rows. Assert that null `hadm_id`/`stay_id` remains null and that the response carries `source_row_key` without fabricating one from a missing ID.

- [ ] **Step 3: Add unavailable-source and failure tests**

Use a fixture that omits `d_labitems` to assert `PARTIAL` with an explicit warning. Inject a repository that raises a database error and assert `503` with no SQL/clinical value in the body. Inject a timeout and assert `504`.

- [ ] **Step 3b: Verify DB Indexes (Performance Hardening)**

Verify that `mimic_demo.db` has explicit indexes created for `subject_id`, `hadm_id`, and `stay_id` on large tables (e.g., `chartevents`, `labevents`) to prevent query timeouts due to full table scans. Document the indexing process if any indexes are missing.

- [ ] **Step 4: Run quality checks**

Run:

```bash
pytest -q
ruff check src tests
git diff --check
```

Expected: all tests pass, Ruff reports no errors, and `git diff --check` is clean. Run a smoke check against the configured `mimic_demo.db` that prints only record counts, statuses and source table names.

- [ ] **Step 5: Verify data safety and documentation**

Run:

```bash
git status --short
rg -n "\.csv\.gz|PHYSIONET|API_KEY|raw_value|prompt" src tests docs/superpowers
```

Review every match manually. Do not add raw MIMIC rows or secrets. Update README with environment configuration, route list, fail-closed auth behavior, and the command to run clinical tests. State clearly that retrieval is evidence-only and not a diagnosis or treatment recommendation.

- [ ] **Step 6: Commit final hardening**

```bash
git add README.md docs/guide/testing/writing-tests.md src tests
git commit -m "test: harden clinical retrieval backend"
```

## Self-review checklist

- Every design component has a task: contracts (1), access/audit (2), repository/availability (3), service (4), tools (5), API (6), hardening (7).
- Every public method name and response type used later is defined before its first use.
- No task enables unauthenticated clinical access or trusts a client-supplied identity in production.
- No task delegates SQL generation to an LLM.
- Lineage, numeric integrity, missing data, partial availability, authorization and audit behavior are covered by explicit tests.
- No unresolved markers, undefined cross-task fixtures, or inconsistent public names remain in the plan.
