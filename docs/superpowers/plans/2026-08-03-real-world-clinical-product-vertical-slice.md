# Real-World Clinical Product Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng release demo synthetic end-to-end cho bác sĩ, admin, data steward và safety/compliance; giữ nguyên API, quyền hạn, lineage và review workflow để chuyển sang dữ liệu bệnh viện sau này.

**Architecture:** Tích hợp clinical retrieval backend hiện có vào `main`, sau đó bổ sung summary evidence-first, claim/citation validation, review/version persistence và REST API. Frontend Next.js gọi duy nhất FastAPI; demo dùng synthetic SQLite và `DemoSessionProvider`/assignment provider, còn production thay bằng PostgreSQL, SSO/OIDC và assignment provider đáng tin cậy.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite synthetic fixture, PostgreSQL adapter đã có trong clinical branch, LangGraph/LangChain, Next.js + TypeScript, React Testing Library/Vitest, Playwright, Docker Compose, pytest, Ruff.

## Global Constraints

- Demo phải giữ nguyên API/schema của production.
- SQLite chỉ dành cho local/test; production chọn PostgreSQL rõ ràng, không fallback âm thầm.
- Không commit raw MIMIC rows, restricted excerpts, secret, token, prompt hoặc SQL parameter.
- Mọi clinical request phải qua server-side authorization và patient assignment.
- Agent chỉ tạo `DRAFT`; chỉ bác sĩ được phân công mới được `APPROVED`.
- Claim không có citation hợp lệ không được dùng trong bản approved.
- Conflict không được AI tự chọn nguồn đúng; phải hiển thị `UNRESOLVED` hoặc kết quả bác sĩ xác nhận.
- Log lỗi chỉ chứa trace/correlation ID và metadata cần thiết, không chứa raw clinical value.
- Mọi generate, edit, regenerate, reject, approve và export phải tạo audit event.
- Demo provider chỉ được dùng trong development/test và bị vô hiệu hóa khi `APP_ENV=production`.
- Mọi task kết thúc bằng focused tests, regression tests liên quan và một commit riêng.

---

## File map

| File | Trách nhiệm |
|---|---|
| `src/config.py` | Demo database path, summary settings và feature flags |
| `scripts/create_synthetic_demo.py` | Tạo database demo deterministic, không đọc raw MIMIC |
| `src/clinical/summary_schemas.py` | Claim, citation, conflict, draft và validation contracts |
| `src/clinical/summary_service.py` | Orchestrate retrieval → generation → validation |
| `src/clinical/summary_generator.py` | Generator protocol và deterministic demo generator |
| `src/clinical/claim_validator.py` | Kiểm tra citation, value/unit/time và unsupported claims |
| `src/clinical/summary_repository.py` | Lưu draft, version, review checklist và state transitions |
| `src/clinical/review.py` | Backend policy cho edit/reject/approve/export |
| `src/api/summary_routes.py` | Summary generate/read/edit/review/version/export routes |
| `src/api/admin_routes.py` | User, assignment và audit routes cho admin/compliance |
| `src/api/ops_routes.py` | Ingestion/source/system status cho data steward và DevOps |
| `tests/test_clinical/test_summary.py` | Generator, claim validation và summary orchestration |
| `tests/test_clinical/conftest.py` | Shared evidence, draft, access and repository fixtures |
| `tests/test_clinical/test_review.py` | State machine, checklist, assignment và audit policy |
| `tests/test_api/conftest.py` | Authenticated doctor/admin clients và summary fixtures |
| `tests/test_api/test_summary_routes.py` | Clinical summary HTTP contract |
| `tests/test_api/test_admin_routes.py` | Admin/compliance HTTP contract |
| `tests/test_api/test_ops_routes.py` | Data/ops status HTTP contract |
| `frontend/` | Next.js application và frontend tests |
| `frontend/e2e/doctor-flow.spec.ts` | Browser test cho doctor vertical slice |
| `README.md`, `docker-compose.yml`, `Makefile` | Demo setup, commands và deployment instructions |

## Task 1: Integrate the clinical backend and establish safe demo data

**Files:**
- Modify: `.env.example`, `README.md`, `docker-compose.yml`, `Makefile`
- Create: `scripts/create_synthetic_demo.py`, `tests/test_demo_data.py`
- Integrate: existing `feat/clinical-retrieval-backend` changes after review

**Interfaces:**
- `create_synthetic_demo_database(path: str | Path) -> Path` creates a deterministic SQLite database with subjects `101` and `102`, admissions, one ICU stay, diagnoses, procedures, labs, microbiology, medications and one intentional conflict.
- Demo configuration uses `CLINICAL_BACKEND=sqlite` and `CLINICAL_DATABASE_PATH=./data/synthetic_demo.db`.
- The demo adapter is the existing `SQLiteClinicalRepository`; the production adapter is the existing `PostgreSQLClinicalRepository`; both implement the shared clinical repository protocol.
- Existing `ClinicalRepository`, `ClinicalRetrievalService`, `AccessContext`, `DemoAssignmentProvider` and clinical routes remain the public backend contracts.

- [ ] **Step 1: Write the demo data safety test**

```python
def test_synthetic_demo_has_expected_domains_without_raw_mimic_files(tmp_path):
    db_path = tmp_path / "synthetic_demo.db"
    create_synthetic_demo_database(db_path)
    tables = set(sqlite3.connect(db_path).execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall())
    assert {"patients", "admissions", "labevents", "diagnoses_icd"}.issubset(
        {row[0] for row in tables}
    )
    assert sqlite3.connect(db_path).execute(
        "SELECT COUNT(*) FROM patients"
    ).fetchone()[0] == 2
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `pytest tests/test_demo_data.py::test_synthetic_demo_has_expected_domains_without_raw_mimic_files -q`

Expected: FAIL because the synthetic database factory does not exist.

- [ ] **Step 3: Implement the deterministic synthetic database**

Create only the columns consumed by the repository queries. Use synthetic IDs and values such as `subject_id=101`, `hadm_id=201`, `stay_id=301`, lab value `1.2`, and two medication evidence rows with different source statuses. Do not read from `mimic-iv-clinical-database-demo-2.2`, `mimic_demo.db`, CSV, CSV.GZ or environment credentials.

Add configuration and Make targets:

```make
demo-db:
	python scripts/create_synthetic_demo.py data/synthetic_demo.db

demo-test:
	pytest tests/test_clinical tests/test_api/test_clinical_routes.py -q
```

- [ ] **Step 4: Integrate and run the backend baseline**

Review the existing feature branch, then integrate it into `main` with:

```bash
git diff --stat main...feat/clinical-retrieval-backend
git merge --no-ff feat/clinical-retrieval-backend -m "merge: integrate clinical retrieval backend"
```

Run:

```bash
pytest -q
ruff check src tests scripts
python scripts/create_synthetic_demo.py data/synthetic_demo.db
```

Expected: existing tests and clinical backend tests pass; the app can point to `data/synthetic_demo.db` without raw-data ingestion.

- [ ] **Step 5: Commit the demo data and baseline configuration**

```bash
git add .env.example README.md docker-compose.yml Makefile scripts/create_synthetic_demo.py tests/test_demo_data.py
git commit -m "feat: add safe synthetic clinical demo baseline"
```

## Task 2: Evidence-first summary contracts and deterministic demo generation

**Files:**
- Create: `src/clinical/summary_schemas.py`, `src/clinical/summary_generator.py`, `src/clinical/claim_validator.py`, `src/clinical/summary_service.py`
- Create: `tests/test_clinical/test_summary.py`, `tests/test_clinical/conftest.py`

**Interfaces:**
- `Citation`: `citation_id: str`, `lineage: SourceLineage`, `supported_fields: list[str]`.
- `Claim`: `claim_id: str`, `section: str`, `text: str`, `citation_ids: list[str]`, `status: Literal["VALID", "INVALID", "UNSUPPORTED"]`.
- `Conflict`: `conflict_id: str`, `topic: str`, `evidence_ids: list[str]`, `status: Literal["UNRESOLVED", "RESOLVED"]`, `resolution_note: str | None`.
- `ClinicalSummaryDraft`: `summary_id: UUID`, `subject_id: int`, `hadm_id: int | None`, `stay_id: int | None`, `status: Literal["DRAFT", "NEEDS_REVISION", "REJECTED", "APPROVED", "EXPORTED"]`, `sections: dict[str, list[Claim]]`, `citations: list[Citation]`, `conflicts: list[Conflict]`, `limitations: list[str]`, `trace_id: str`.
- `SummaryGenerator.generate(evidence: list[EvidenceRecord]) -> ClinicalSummaryDraft`.
- `DeterministicDemoSummaryGenerator.generate(...)` creates summary sections only from supplied evidence and never calls an external LLM.
- `ClaimValidator.validate(draft: ClinicalSummaryDraft, evidence: list[EvidenceRecord]) -> ValidationReport`.
- `ValidationReport`: `valid: bool`, `errors: list[ValidationIssue]`, `warnings: list[str]`.
- `ValidationIssue`: `code: str`, `claim_id: str | None`, `message: str`.
- `ClinicalSummaryService.generate(context: AccessContext, query: ClinicalQuery) -> ClinicalSummaryDraft`.

- [ ] **Step 1: Create shared synthetic test fixtures**

Add `evidence`, `draft_with_claim(text, citation_ids)`, and `first_claim(draft, section)` fixtures/helpers to `tests/test_clinical/conftest.py`. The evidence fixture must use the existing synthetic lineage contract with a `labevents` record whose value is `1.2`, unit is `mg/dL`, and source key is `labevent_id=9001`.

- [ ] **Step 2: Write failing contract and validator tests**

```python
def test_validator_rejects_claim_without_citation(evidence):
    draft = draft_with_claim(text="Creatinine is 1.2", citation_ids=[])
    report = ClaimValidator().validate(draft, evidence)
    assert report.valid is False
    assert report.errors[0].code == "MISSING_CITATION"


def test_demo_generator_preserves_lab_value_and_lineage(evidence):
    draft = DeterministicDemoSummaryGenerator().generate(evidence)
    claim = first_claim(draft, section="Laboratory Trends")
    assert claim.citation_ids
    assert draft.citations[0].lineage.table == "labevents"
```

- [ ] **Step 3: Run focused tests and verify failure**

Run: `pytest tests/test_clinical/test_summary.py -q`

Expected: FAIL because summary contracts, generator and validator do not exist.

- [ ] **Step 4: Implement the contracts and deterministic generator**

Group evidence by domain, create only the supported sections `Clinical Overview`, `Active Problems`, `Current and Recent Medications`, `Key Timeline`, `Laboratory Trends`, `Conflicts and Missing Information`, and `Limitations`. Every generated claim must reference one or more exact evidence IDs. Preserve numeric value, unit, timestamp and source lineage without paraphrasing them into new clinical facts.

- [ ] **Step 5: Implement claim validation**

Reject a claim when its citation ID is absent, its lineage does not match supplied evidence, its numeric value/unit differs from the cited evidence, or its source table is unavailable. Return `ValidationReport(valid, errors, warnings)` and never raise raw SQL/provider exceptions to the API.

- [ ] **Step 6: Run focused and regression tests**

Run: `pytest tests/test_clinical/test_summary.py tests/test_clinical/test_repository.py tests/test_api/test_routes.py -q`

Expected: PASS; the existing `/api/v1/chat` and clinical retrieval contracts remain unchanged.

- [ ] **Step 7: Commit**

```bash
git add src/clinical/summary_schemas.py src/clinical/summary_generator.py src/clinical/claim_validator.py src/clinical/summary_service.py tests/test_clinical/test_summary.py
git commit -m "feat: add evidence-first clinical summary contracts"
```

## Task 3: Persist drafts, versions, checklist and review state

**Files:**
- Create: `src/clinical/summary_repository.py`, `src/clinical/review.py`
- Modify: `src/clinical/audit.py`
- Create: `tests/test_clinical/test_review.py`

**Interfaces:**
- `SummaryRepository.create_draft(draft, actor_id) -> SummaryVersion`.
- `SummaryRepository.update_draft(summary_id, actor_id, patch) -> SummaryVersion`.
- `SummaryRepository.list_versions(summary_id) -> list[SummaryVersion]`.
- `ReviewService.reject(summary_id, context, reason) -> SummaryVersion`.
- `ReviewService.approve(summary_id, context, checklist: ReviewChecklist) -> SummaryVersion`.
- `SummaryVersion`: `version_id: UUID`, `summary_id: UUID`, `version_number: int`, `status: str`, `actor_id: str`, `reason: str | None`, `created_at: datetime`.
- `ReviewChecklist(reviewed_summary: bool, checked_critical_evidence: bool, understands_ai_limitations: bool, confirms_edits: bool)`.
- `ReviewPolicyError` is a domain exception mapped to HTTP `422` for incomplete checklist, invalid citations or forbidden state transitions.
- Test fixtures `summary_repo`, `assigned_context`, `draft`, `context_for_subject(subject_id)`, and `complete_checklist()` are defined in `tests/test_clinical/conftest.py`.
- `approve` requires all checklist fields, valid citations, an assigned doctor context and no blocking validation error.

- [ ] **Step 1: Write failing state-transition tests**

```python
def test_unassigned_doctor_cannot_approve(summary_repo, assigned_context, draft):
    summary = summary_repo.create_draft(draft, actor_id="doctor-1")
    denied = context_for_subject(102)
    with pytest.raises(ClinicalAccessDenied):
        ReviewService(summary_repo).approve(summary.summary_id, denied, complete_checklist())


def test_approval_requires_complete_checklist(summary_repo, assigned_context, draft):
    summary = summary_repo.create_draft(draft, actor_id="doctor-1")
    with pytest.raises(ReviewPolicyError):
        ReviewService(summary_repo).approve(summary.summary_id, assigned_context, ReviewChecklist(
            reviewed_summary=True,
            checked_critical_evidence=False,
            understands_ai_limitations=True,
            confirms_edits=True,
        ))
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest tests/test_clinical/test_review.py -q`

Expected: FAIL because persistence and review policy are not implemented.

- [ ] **Step 3: Add the review persistence schema**

Create SQLite tables `summaries`, `summary_versions`, `summary_claims`, `summary_citations`, `summary_conflicts`, `review_checklists` and `audit_events`. Store the original AI draft separately from edited versions. Store only identifiers and evidence lineage in audit events; do not store raw clinical values in audit payloads.

- [ ] **Step 4: Implement state transitions and immutable version history**

Allow only `DRAFT → NEEDS_REVISION`, `DRAFT → REJECTED`, `DRAFT → APPROVED`, and `APPROVED → EXPORTED`. Reject edits to approved versions; create a new revision instead. Record actor, reason, timestamp and trace ID for every transition.

- [ ] **Step 5: Run focused and security tests**

Run: `pytest tests/test_clinical/test_review.py tests/test_clinical/test_access.py -q`

Expected: PASS, including assignment denial, incomplete checklist, invalid citation and immutable history tests.

- [ ] **Step 6: Commit**

```bash
git add src/clinical/summary_repository.py src/clinical/review.py src/clinical/audit.py tests/test_clinical/test_review.py
git commit -m "feat: add clinical summary review state machine"
```

## Task 4: Expose the doctor workflow through FastAPI

**Files:**
- Create: `src/api/summary_routes.py`, `src/api/review_routes.py`
- Create: `src/api/auth_routes.py`, `src/clinical/demo_auth.py`
- Modify: `src/main.py`, `src/api/dependencies.py`
- Create: `tests/test_api/test_auth.py`, `tests/test_api/test_summary_routes.py`, `tests/test_api/conftest.py`

**Interfaces:**
- `POST /api/v1/auth/demo-login` accepts `DemoLoginRequest(username, password)` only when `APP_ENV in {"development", "test"}` and sets a signed HTTP-only `demo_session` cookie.
- `DemoSessionProvider.authenticate(request: Request) -> AccessContext` verifies the signed cookie and rejects it when `APP_ENV=production`.
- `GET /api/v1/clinical/patients` returns only assigned patients.
- `POST /api/v1/clinical/patients/{subject_id}/summaries` starts deterministic demo generation and returns a `ClinicalSummaryDraft` with `DRAFT` status.
- `GET /api/v1/clinical/summaries/{summary_id}` returns draft, claims, citations, conflicts, limitations and review state.
- `PATCH /api/v1/clinical/summaries/{summary_id}` creates a new edited version and revalidates citations.
- `POST /api/v1/clinical/summaries/{summary_id}/reject` requires a non-empty reason.
- `POST /api/v1/clinical/summaries/{summary_id}/approve` requires `ReviewChecklist` and returns `APPROVED` only after backend validation.
- `GET /api/v1/clinical/summaries/{summary_id}/versions` returns immutable version metadata.
- `GET /api/v1/clinical/summaries/{summary_id}/export` returns a PDF only for `APPROVED`; otherwise returns a draft response with a `DRAFT — NOT FOR CLINICAL USE` watermark.
- Test fixtures `authenticated_client`, `admin_client` and `summary_id` are defined in `tests/test_api/conftest.py`; dependency overrides are cleared after every test.

- [ ] **Step 1: Write failing authentication and API tests**

```python
async def test_summary_generation_returns_citations(authenticated_client):
    response = await authenticated_client.post(
        "/api/v1/clinical/patients/101/summaries",
        json={"hadm_id": 201},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["sections"]
    assert body["citations"]


async def test_demo_login_is_not_available_in_production(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    response = await client.post("/api/v1/auth/demo-login", json={"username": "doctor-1", "password": "demo"})
    assert response.status_code == 503


async def test_approve_requires_review_checklist(authenticated_client, summary_id):
    response = await authenticated_client.post(
        f"/api/v1/clinical/summaries/{summary_id}/approve",
        json={"reviewed_summary": True, "checked_critical_evidence": False,
              "understands_ai_limitations": True, "confirms_edits": True},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest tests/test_api/test_summary_routes.py -q`

Expected: FAIL because summary and review routes are not registered.

- [ ] **Step 3: Implement dependency wiring and routes**

Construct `ClinicalSummaryService` and `ReviewService` through FastAPI dependencies. Use dependency overrides for tests. The route layer maps only HTTP input/output; all assignment checks, validation and persistence stay in services. Use `403` for access denial, `404` for unknown summary, `409` for invalid state transition, `422` for validation failure, `503` for unavailable backend and `504` for timeout.

- [ ] **Step 4: Add PDF export with explicit watermark policy**

Generate a minimal PDF containing de-identified IDs, version, status, summary sections, citations, conflicts, limitations, reviewer metadata and the safety disclaimer. Approved output has no draft watermark; every other output has `DRAFT — NOT FOR CLINICAL USE`. Do not include raw source rows beyond the citation fields required by the contract.

- [ ] **Step 5: Run API and regression tests**

Run: `pytest tests/test_api/test_summary_routes.py tests/test_api/test_clinical_routes.py tests/test_api/test_routes.py -q`

Expected: PASS; unassigned subjects remain denied and `/api/v1/chat` remains non-clinical.

- [ ] **Step 6: Commit**

```bash
git add src/api/summary_routes.py src/api/review_routes.py src/api/dependencies.py src/main.py tests/test_api/test_summary_routes.py
git commit -m "feat: expose clinical draft and review API"
```

## Task 5: Build the Next.js doctor vertical slice

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/next.config.ts`, `frontend/src/app/`, `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`, `frontend/src/components/`
- Create: `frontend/src/**/*.test.tsx`, `frontend/e2e/doctor-flow.spec.ts`
- Modify: `.env.example`, `docker-compose.yml`, `README.md`

**Interfaces:**
- `apiClient.listPatients() -> Promise<AssignedPatient[]>`.
- `apiClient.getPatientWorkspace(subjectId) -> Promise<PatientWorkspace>`.
- `apiClient.generateSummary(subjectId, scope) -> Promise<ClinicalSummaryDraft>`.
- `apiClient.updateSummary(summaryId, patch) -> Promise<ClinicalSummaryDraft>`.
- `apiClient.approveSummary(summaryId, checklist) -> Promise<ClinicalSummaryDraft>`.
- `AssignedPatient`: `subjectId`, `anchorAge`, `gender`, `admissionCount`, `icuStayCount`, `summaryStatus`.
- `PatientWorkspace`: `patient`, `availability`, `timeline`, `summary`, `warnings`, `limitations`.
- `frontend/src/test/fixtures.ts` exports `draftSummary` with one valid citation, one limitation and one unresolved conflict for component tests.
- The UI must render loading, empty, success, warning, error, denied, partial data, citation unavailable, draft and approved states.

- [ ] **Step 1: Write component tests for the safety-critical states**

```tsx
it("keeps approve disabled until the checklist is complete", async () => {
  render(<ReviewModal summary={draftSummary} />)
  expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled()
  await userEvent.click(screen.getByLabelText("I reviewed the summary"))
  await userEvent.click(screen.getByLabelText("I checked critical evidence"))
  await userEvent.click(screen.getByLabelText("I understand AI is decision support only"))
  await userEvent.click(screen.getByLabelText("I confirm my edits"))
  expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled()
})
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run: `npm --prefix frontend test -- --run`

Expected: FAIL because the frontend application and test runner do not exist.

- [ ] **Step 3: Scaffold the frontend and API client**

Use Next.js App Router and TypeScript. Configure `NEXT_PUBLIC_API_URL`, keep auth state in an HTTP-only session boundary when the real provider is added, and use a demo login adapter only under `APP_ENV=development`. Do not put clinical data in localStorage, URL query strings or analytics events.

- [ ] **Step 4: Implement the doctor dashboard**

Render assigned patients with de-identified `subject_id`, anchor age/sex, admission/ICU counts and summary status. Include search, empty state, permission error, session expiry and API unavailable state. The client never decides whether a patient is authorized; it only renders the server response.

- [ ] **Step 5: Implement the patient workspace**

Create tabs for Summary, Timeline, Medications, Lab Trends, Source Records, Conflicts and Review History. The summary view shows claim-level citation links, source panel, missing/partial data, conflicts, limitations and the safety disclaimer. Editing preserves citation tokens and exposes a revalidate action.

- [ ] **Step 6: Implement review and export actions**

Provide Save Draft, Request Regeneration, Reject and Approve actions. The approval modal shows checklist, citation errors, unresolved conflicts and reviewer identity. Disable Approve until the server has returned valid state and the checklist is complete. Export only follows the backend response.

- [ ] **Step 7: Add browser test for the complete demo flow**

The Playwright scenario logs in as `doctor-1`, opens assigned subject `101`, generates a draft, opens a citation, edits a section, completes the checklist, approves and verifies the approved status. It also attempts subject `102` and verifies the denied state.

- [ ] **Step 8: Run frontend quality checks and commit**

Run:

```bash
npm --prefix frontend test -- --run
npm --prefix frontend run build
npx --prefix frontend playwright test frontend/e2e/doctor-flow.spec.ts
```

Commit:

```bash
git add frontend .env.example docker-compose.yml README.md
git commit -m "feat: add doctor clinical review interface"
```

## Task 6: Add minimal admin, data steward and compliance surfaces

**Files:**
- Create: `src/api/admin_routes.py`, `src/api/ops_routes.py`
- Create: `tests/test_api/test_admin_routes.py`, `tests/test_api/test_ops_routes.py`
- Create: `frontend/src/app/admin/`, `frontend/src/app/operations/`, `frontend/src/components/AuditTable.tsx`

**Interfaces:**
- `GET /api/v1/admin/users` and `POST /api/v1/admin/users/{user_id}/assignments` are ADMIN-only.
- `DELETE /api/v1/admin/users/{user_id}/assignments/{subject_id}` revokes an assignment and records an audit event.
- `GET /api/v1/admin/audit` is ADMIN/compliance read-only and returns actor, action, subject reference, timestamp, result and trace ID.
- `GET /api/v1/ops/clinical-status` returns backend, database, loaded modules, ingestion/checksum status, LLM availability and latency summaries without clinical values.
- `GET /api/v1/ops/ingestion-runs` returns run ID, dataset/profile, checksum status, schema status, counts and errors without raw rows.

- [ ] **Step 1: Write failing role-boundary tests**

```python
async def test_doctor_cannot_manage_assignments(authenticated_client):
    response = await authenticated_client.post(
        "/api/v1/admin/users/doctor-2/assignments",
        json={"subject_id": 101},
    )
    assert response.status_code == 403


async def test_operations_status_contains_no_clinical_values(admin_client):
    response = await admin_client.get("/api/v1/ops/clinical-status")
    assert response.status_code == 200
    assert "raw_value" not in response.text
    assert "1.2" not in response.text
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest tests/test_api/test_admin_routes.py tests/test_api/test_ops_routes.py -q`

Expected: FAIL because admin and operations routers do not exist.

- [ ] **Step 3: Implement backend routes and audit filters**

Use server-side role checks. Admin operations may change assignments but may not mutate clinical content. Compliance audit responses expose only safe metadata. Operations routes aggregate availability, error and latency metadata; they never select clinical values.

- [ ] **Step 4: Implement the minimal operations UI**

Admin page: user list, role, active/locked state and assignment history. Compliance page: append-only audit table with filters by actor/action/result/time. Operations page: service cards for API, database, source profile, ingestion/checksum, LLM gateway and clinical tool availability. Every page has permission denied and unavailable states.

- [ ] **Step 5: Run role, API and frontend tests**

Run: `pytest tests/test_api/test_admin_routes.py tests/test_api/test_ops_routes.py tests/test_api/test_summary_routes.py -q` and `npm --prefix frontend test -- --run`.

Expected: PASS; doctors cannot access admin mutation routes and no operations response contains clinical values.

- [ ] **Step 6: Commit**

```bash
git add src/api/admin_routes.py src/api/ops_routes.py tests/test_api/test_admin_routes.py tests/test_api/test_ops_routes.py frontend/src/app/admin frontend/src/app/operations frontend/src/components/AuditTable.tsx
git commit -m "feat: add operational actor surfaces"
```

## Task 7: End-to-end demo gate, documentation and handoff

**Files:**
- Create: `frontend/e2e/admin-flow.spec.ts`, `frontend/e2e/ops-flow.spec.ts`, `scripts/run_demo_smoke.py`
- Modify: `README.md`, `docs/guide/setup/quick-start.md`, `docs/guide/testing/writing-tests.md`, `docker-compose.yml`, `Makefile`

- [ ] **Step 1: Add the safe smoke script**

`scripts/run_demo_smoke.py` starts or targets the configured local API, checks health, lists only assigned subject IDs/counts and statuses, performs one generation/review flow, and prints only status codes, counts, trace IDs and source table names. It must never print summary text, lab values, raw rows or secrets.

- [ ] **Step 2: Add end-to-end actor tests**

The admin scenario creates/revokes a demo assignment and verifies the doctor dashboard changes. The operations scenario verifies source availability and audit metadata. The doctor scenario from Task 5 verifies the approved summary flow and denied access.

- [ ] **Step 3: Document local demo setup**

README must contain:

```bash
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python scripts/create_synthetic_demo.py data/synthetic_demo.db
uvicorn src.main:app --reload --port 8000
npm --prefix frontend install
npm --prefix frontend run dev
```

Document the demo-only auth boundary, synthetic data guarantee, route list, actor accounts, approval disclaimer and the fact that production requires PostgreSQL, trusted SSO/assignment, patient-identity mapping and governance approval.

- [ ] **Step 4: Run the complete release gate**

Run:

```bash
pytest -q
ruff check src tests scripts
git diff --check
npm --prefix frontend test -- --run
npm --prefix frontend run build
npx --prefix frontend playwright test frontend/e2e
python scripts/run_demo_smoke.py
```

Expected: all tests pass, frontend builds, browser flows pass, smoke output contains no clinical values and the working tree is clean except for intentional release artifacts.

- [ ] **Step 5: Commit the demo release documentation**

```bash
git add README.md docs/guide/setup/quick-start.md docs/guide/testing/writing-tests.md docker-compose.yml Makefile frontend/e2e scripts/run_demo_smoke.py
git commit -m "test: gate synthetic clinical demo release"
```

## Production handoff after this plan

This plan ends at the synthetic demo gate. A separate production rollout plan must be approved before connecting real hospital data. Its first gates are PostgreSQL migration/index review, trusted SSO/OIDC and assignment integration, patient-identity mapping, ingestion checksum/schema/foreign-key validation, encrypted backup/restore, retention policy, incident response and clinical governance sign-off.

## Self-review checklist

- Spec actors are covered by Tasks 5–7: doctor, admin, data steward, safety/compliance and DevOps/IT.
- The end-to-end doctor problem is covered by Tasks 2–5: evidence retrieval, draft generation, citations, review and export.
- Server-side authorization is covered by Tasks 1, 3, 4 and 6.
- Missing/conflicting data and explicit unavailable states are covered by Tasks 2, 4, 5 and 6.
- Demo/production separation is covered by Tasks 1, 5 and 7.
- No task allows raw SQL, raw data logging, client-controlled authorization or unreviewed approval.
- Every task has named files, interfaces, failing tests, focused commands and a commit.
