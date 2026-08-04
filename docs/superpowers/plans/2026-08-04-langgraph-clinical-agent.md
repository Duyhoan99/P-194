# LangGraph Clinical Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the deterministic summary generator in the local demo path with a LangGraph agent that calls the configured OpenAI LLM, receives only access-checked clinical evidence, and returns a validated `ClinicalSummaryDraft`.

**Architecture:** The existing `ClinicalSummaryService` remains the authorization and persistence boundary. A focused LangGraph graph retrieves the six existing clinical evidence domains, formats a bounded context, invokes `ChatOpenAI.with_structured_output(ClinicalSummaryDraft)`, validates every claim citation against retrieved evidence, and finalizes only server-owned identifiers/status/trace fields. LLM or validation failures raise a mapped 503/422-style clinical error and the repository is never called.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, LangGraph, LangChain OpenAI structured output, existing SQLite synthetic retrieval and citation validator, pytest.

## Global Constraints

- Local demo only; use synthetic SQLite data and the existing server-side assignment/auth boundary.
- No production deployment, SSO/OIDC, PostgreSQL migration, real patient data, RAG corpus ingestion, or clinical decision logic.
- Every clinical claim must retain at least one citation that exists in retrieved evidence.
- The generated draft must remain `DRAFT` until the existing clinician review/approval workflow changes it.
- Do not log prompts, raw clinical evidence, API keys, or generated clinical text.
- Existing deterministic tests remain deterministic by injecting the current generator or selecting the deterministic backend explicitly.

---

### Task 1: Define the agent graph contract and failing tests

**Files:**
- Create: `src/clinical/agent.py`
- Create: `tests/test_clinical/test_agent.py`
- Modify: `src/clinical/errors.py` if a dedicated agent-unavailable error is needed by the tests

**Interfaces:**
- `ClinicalAgent.generate(context: AccessContext, query: ClinicalQuery) -> ClinicalSummaryDraft`
- `ClinicalAgentGraph` accepts an injected `SummaryGenerator`-compatible LLM caller and an existing `ClinicalRetrievalService`.
- The graph state contains `context`, `query`, `responses`, `evidence`, `draft`, and safe validation metadata; it never stores prompt text in audit output.

- [ ] **Step 1: Write failing tests** for successful structured generation, server-bound fields, citation rejection, and LLM failure.
- [ ] **Step 2: Run `..\.venv\Scripts\python.exe -m pytest tests/test_clinical/test_agent.py -q` and confirm the failures are caused by the missing agent contract.
- [ ] **Step 3: Add the smallest typed graph/state interfaces and error types needed for the tests to import.
- [ ] **Step 4: Run the focused test again and confirm only behavior assertions remain failing.

### Task 2: Implement evidence tools/context and structured LLM generation

**Files:**
- Modify: `src/clinical/agent.py`
- Modify: `src/services/llm.py`
- Test: `tests/test_clinical/test_agent.py`

**Interfaces:**
- Six graph retrieval tool nodes call the existing access-aware service methods: overview, timeline, diagnoses/procedures, labs, microbiology, and ICU events.
- `build_agent_context(evidence: list[EvidenceRecord]) -> str` returns bounded JSON-safe evidence context with lineage identifiers and supported fields.
- `get_structured_llm() -> Runnable` returns `get_llm().with_structured_output(ClinicalSummaryDraft)`.

- [ ] **Step 1: Add a fake structured LLM in the test that returns a valid draft assembled from the supplied evidence.
- [ ] **Step 2: Run the focused test and verify it fails because the graph does not yet invoke the fake model.
- [ ] **Step 3: Implement a LangGraph `StateGraph` with retrieve, generate, validate, and finalize nodes; compile it once per agent instance.
- [ ] **Step 4: Bind the structured schema to the LLM and pass an explicit system instruction forbidding unsupported claims, diagnoses, treatment recommendations, and fabricated citations.
- [ ] **Step 5: Use the graph output as a Pydantic object, not free-form text or JSON parsing.
- [ ] **Step 6: Run the focused agent tests and verify the success path passes.

### Task 3: Enforce citation/schema safety and bind server-owned fields

**Files:**
- Modify: `src/clinical/agent.py`
- Modify: `src/clinical/claim_validator.py` only if the existing validator lacks a required check
- Test: `tests/test_clinical/test_agent.py`

- [ ] **Step 1: Add failing tests for a missing citation, a citation not present in evidence, an invalid claim status, and an LLM draft attempting to change subject/scope/status/trace fields.
- [ ] **Step 2: Run the focused tests and confirm each fails for the intended validation reason.
- [ ] **Step 3: Validate the LLM draft with `ClinicalSummaryDraft` and `ClaimValidator` against the retrieved evidence.
- [ ] **Step 4: Require every clinical claim to have a valid citation; reject invalid/unsupported claims rather than silently persisting them.
- [ ] **Step 5: Replace LLM-controlled `summary_id`, `subject_id`, `hadm_id`, `stay_id`, `status`, and `trace_id` with values from the authenticated request/query and deterministic server logic.
- [ ] **Step 6: Run all clinical agent tests and confirm invalid output never reaches persistence.

### Task 4: Wire the agent into summary generation without breaking deterministic tests

**Files:**
- Modify: `src/config.py`
- Modify: `src/clinical/summary_service.py`
- Modify: `src/api/dependencies.py`
- Modify: `src/api/clinical_routes.py` or its existing error-handler module for safe 503 mapping
- Modify: `.env.example`
- Test: `tests/test_api/test_summary_routes.py`
- Test: `tests/test_api/conftest.py` only where dependency injection is required

- [ ] **Step 1: Add failing API tests proving the LangGraph backend is selected only when `SUMMARY_AGENT_BACKEND=langgraph`, that a fake agent draft is persisted as `DRAFT`, and that agent failure returns a safe 503 with no draft row.
- [ ] **Step 2: Run the focused API tests and verify the new selection/error assertions fail.
- [ ] **Step 3: Add `summary_agent_backend: Literal["deterministic", "langgraph"] = "deterministic"` and preserve deterministic behavior for existing tests.
- [ ] **Step 4: Build the configured generator/agent in dependencies with injected retrieval service and audit sink; do not instantiate an LLM during module import.
- [ ] **Step 5: Map provider/network/structured-output failures to the existing safe clinical error response without leaking prompts, raw evidence, or secrets.
- [ ] **Step 6: Run the focused API tests and then the complete Python test suite.

### Task 5: Enable and verify the real local demo path

**Files:**
- Modify: `.env.example` with non-secret local settings only
- Optional Create: `scripts/run_agent_smoke.py` if the existing smoke script cannot safely verify agent metadata
- Test: `tests/test_clinical/test_agent.py`

- [ ] **Step 1: Add a metadata-only smoke assertion for the selected backend, draft status, citation count, and trace ID; never print summary text or evidence values.
- [ ] **Step 2: Run the smoke assertion with `SUMMARY_AGENT_BACKEND=langgraph`, `APP_ENV=development`, the synthetic database, and a configured local LLM key.
- [ ] **Step 3: Start/restart the API with the same environment and verify the doctor flow reaches a persisted `DRAFT` generated by the real agent.
- [ ] **Step 4: Run frontend unit tests and record the existing E2E data-contract mismatch separately; do not alter production scope to make the demo depend on unapproved infrastructure.
- [ ] **Step 5: Run `ruff check src tests scripts` and `python -m pytest -q`; report real-LLM availability separately from deterministic test results.

## Verification Checklist

- [ ] Graph calls the real configured LLM only in the explicit `langgraph` backend.
- [ ] Retrieval remains access-aware and server-owned.
- [ ] Structured output is validated by Pydantic and citation validator before persistence.
- [ ] Invalid output and provider failures fail closed with safe metadata-only errors.
- [ ] Existing review/approve/export flow remains unchanged and only accepts `DRAFT` output from the agent.
- [ ] No raw clinical text, prompt, secret, or API response is written to logs.
