# MIMIC-Grounded Clinical Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the backend and LangGraph clinical agent run a complete, citation-grounded demo over the MIMIC-IV demo folder without unrelated or unsupported output.

**Architecture:** Load the repository's MIMIC CSV modules into an indexed SQLite database and point development settings at that database. Extend the existing access-controlled repository/service/tool boundaries with medication and metric retrieval, then run a LangGraph retrieve/validate pipeline with structured LLM output and deterministic evidence-only fallback. Keep persistence and human review after validation.

**Tech Stack:** FastAPI, SQLite, pandas, LangGraph, LangChain structured output, Pydantic, pytest, synthetic/local MIMIC-IV demo CSVs.

## Global Constraints

- The folder `mimic-iv-clinical-database-demo-2.2` is the source of truth.
- Runtime retrieval uses `data/mimic_demo.db` in read-only mode; runtime requests do not scan arbitrary CSV files.
- Every clinical claim must cite a retrieved MIMIC source record; no diagnosis, treatment recommendation, or invented medication interaction may be emitted.
- The drug-interaction tool returns explicit `NOT_LOADED` metadata because no approved interaction knowledge base exists in the folder.
- Test mode keeps isolated fixture subject assignments; development mode uses IDs from `demo_subject_id.csv`.

---

### Task 1: Build and configure the MIMIC demo source

**Files:**
- Modify: `scripts/setup_db.py`
- Modify: `src/config.py`
- Modify: `src/clinical/operations.py`
- Modify: `.env.example`
- Test: `tests/test_demo_data.py`
- Test: `tests/test_api/test_auth.py`

**Interfaces:**
- `setup_mimic_demo_db(source_dir: Path | None = None, db_path: Path | None = None) -> Path` loads `hosp` and `icu` CSVs and creates indexes for subject/hadm/stay/time lookup.
- `OperationalStore` loads development doctor assignments from `demo_subject_id.csv`, capped by `MIMIC_DEMO_SUBJECT_LIMIT`; test mode retains subject `101` fixtures.

- [ ] **Step 1: Add a failing test for MIMIC source configuration and assignments**

Assert that development settings resolve to `data/mimic_demo.db`, that the first configured assignment IDs come from `demo_subject_id.csv`, and that test mode still exposes subject `101` to `doctor-1`.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_demo_data.py tests/test_api/test_auth.py -q`

Expected: FAIL because current development settings default to `mimic_demo.db` and operational assignments are hardcoded.

- [ ] **Step 3: Implement source loading and environment selection**

Use pandas chunk loading, preserve CSV table names, create indexes only for known clinical tables, and make the development default `data/mimic_demo.db`. Add `MIMIC_DEMO_SOURCE_DIR`, `MIMIC_DEMO_SUBJECTS_FILE`, and `MIMIC_DEMO_SUBJECT_LIMIT` settings. Never include raw credentials or CSV contents in logs.

- [ ] **Step 4: Run focused tests and rebuild the MIMIC database**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_demo_data.py tests/test_api/test_auth.py -q` and `\.venv\Scripts\python.exe scripts/setup_db.py`

Expected: tests pass and `data/mimic_demo.db` exists with the required allow-listed tables.

- [ ] **Step 5: Commit the data/config task**

```powershell
git add scripts/setup_db.py src/config.py src/clinical/operations.py .env.example tests/test_demo_data.py tests/test_api/test_auth.py
git commit -m "feat: configure MIMIC demo source and assignments"
```

### Task 2: Add complete retrieval and clinical tools

**Files:**
- Modify: `src/clinical/availability.py`
- Modify: `src/clinical/repository.py`
- Modify: `src/clinical/service.py`
- Modify: `src/agents/tools/clinical_tools.py`
- Modify: `src/api/clinical_routes.py`
- Test: `tests/test_clinical/test_repository.py`
- Test: `tests/test_clinical/test_service.py`
- Test: `tests/test_clinical/test_tools.py`
- Test: `tests/test_api/test_clinical_routes.py`

**Interfaces:**
- Add `fetch_medications(query, cursor_position=None) -> RepositoryFetch` and `get_medications(context, query) -> ClinicalResponse`.
- Add `build_clinical_tools(...)` entries named `get_medications`, `get_patient_metrics`, and `check_drug_interactions` alongside existing tools.
- Add `GET /api/v1/clinical/patients/{subject_id}/medications`.

- [ ] **Step 1: Write failing tests for medication retrieval and tool registration**

Use a small SQLite fixture containing `prescriptions`, `pharmacy`, `emar`, and `inputevents`; assert records preserve table lineage and status values (`PRESCRIBED`, `ADMINISTERED`, `DISCONTINUED`, `UNKNOWN_STATUS`). Assert the tool list contains all required tool names and the interaction tool returns `NOT_LOADED` without making clinical claims.

- [ ] **Step 2: Run tests and verify failure**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_clinical/test_repository.py tests/test_clinical/test_service.py tests/test_clinical/test_tools.py tests/test_api/test_clinical_routes.py -q`

Expected: FAIL because the medication service method, route, and tools do not exist.

- [ ] **Step 3: Implement allow-listed medication and metric retrieval**

Query only known columns from MIMIC tables, bind `subject_id`, `hadm_id`, `stay_id`, and time filters, normalize source statuses without merging independent evidence, and return explicit unavailable-source warnings when a table is absent. Keep all SQL parameterized and read-only.

- [ ] **Step 4: Run focused tests and verify they pass**

Run the Task 2 test command again. Expected: all focused repository/service/tool/route tests pass.

- [ ] **Step 5: Commit the tools task**

```powershell
git add src/clinical/availability.py src/clinical/repository.py src/clinical/service.py src/agents/tools/clinical_tools.py src/api/clinical_routes.py tests/test_clinical tests/test_api/test_clinical_routes.py
git commit -m "feat: add MIMIC medication and clinical tools"
```

### Task 3: Make the LangGraph agent safe and demo-reliable

**Files:**
- Modify: `src/clinical/agent.py`
- Modify: `src/clinical/summary_generator.py`
- Modify: `src/api/dependencies.py`
- Modify: `src/clinical/claim_validator.py`
- Modify: `src/services/llm.py`
- Test: `tests/test_clinical/test_agent.py`
- Test: `tests/test_api/test_agent_wiring.py`

**Interfaces:**
- `ClinicalAgent(..., fallback_generator: SummaryGenerator | None = None)` uses structured LLM output when available and deterministic evidence-only fallback when configured.
- `_SYSTEM_PROMPT` and validation prohibit chain-of-thought, recommendations, unsupported claims, and unrelated prose.

- [ ] **Step 1: Write failing tests for fallback and off-topic rejection**

Assert that a structured LLM exception returns a `DRAFT` with only evidence-derived claims plus a fallback limitation, and that a draft containing treatment advice or a citation not present in evidence raises `ReviewPolicyError`.

- [ ] **Step 2: Run tests and verify failure**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_clinical/test_agent.py tests/test_api/test_agent_wiring.py -q`

Expected: FAIL because the current agent propagates LLM failure and does not reject all off-topic claim text.

- [ ] **Step 3: Implement the safe graph behavior**

Keep retrieval and authorization server-owned, pass only serialized evidence to the model, validate every claim/citation/conflict, add the medication and interaction metadata to the evidence context, and use deterministic fallback only after recording a safe limitation. Never include the raw exception, prompt, or model reasoning in the API response.

- [ ] **Step 4: Run agent tests and verify they pass**

Run the Task 3 test command again. Expected: all agent wiring and safety tests pass.

- [ ] **Step 5: Commit the agent task**

```powershell
git add src/clinical/agent.py src/clinical/summary_generator.py src/api/dependencies.py src/clinical/claim_validator.py src/services/llm.py tests/test_clinical/test_agent.py tests/test_api/test_agent_wiring.py
git commit -m "feat: harden grounded clinical agent with fallback"
```

### Task 4: Validate end-to-end demo and documentation

**Files:**
- Modify: `scripts/run_demo_smoke.py`
- Modify: `README.md`
- Modify: `docs/guide/setup/quick-start.md`
- Test: `tests/test_demo_smoke.py`

- [ ] **Step 1: Extend smoke coverage**

Require health, MIMIC assignment, login, lab evidence, medication evidence, summary generation, citation metadata, and reviewable `DRAFT` status while continuing to print metadata only.

- [ ] **Step 2: Run all verification**

Run:

```powershell
\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix frontend test -- --run
npm.cmd --prefix frontend run build
```

Start the backend with the configured MIMIC database and run `\.venv\Scripts\python.exe scripts/run_demo_smoke.py`.

Expected: full backend/frontend tests, build, and metadata-only smoke all pass.

- [ ] **Step 3: Document the MIMIC setup and Agent behavior**

Document the one-time database build, environment variables, demo account, available tools, deterministic fallback limitation, and the fact that no interaction warning is emitted without an approved knowledge base.

- [ ] **Step 4: Review diff and commit**

Run `git diff --check`, review only intended files, preserve unrelated user changes, then commit:

```powershell
git add scripts/run_demo_smoke.py README.md docs/guide/setup/quick-start.md tests/test_demo_smoke.py
git commit -m "test: verify complete MIMIC grounded demo"
```
