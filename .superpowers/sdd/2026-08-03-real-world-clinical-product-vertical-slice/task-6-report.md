# Task 6 Report — Operational actor surfaces

## Delivered

- Added server-owned operational metadata and role-safe API routes:
  - `GET /api/v1/admin/users`, `POST /api/v1/admin/users/{user_id}/assignments`, and `DELETE /api/v1/admin/users/{user_id}/assignments/{subject_id}` require `ADMIN`.
  - `GET /api/v1/admin/audit` is read-only for `ADMIN` and `COMPLIANCE`.
  - `GET /api/v1/ops/clinical-status` and `GET /api/v1/ops/ingestion-runs` are available only to `ADMIN` and `DATA_STEWARD`.
- Extended only the trusted, signed demo-session role model with `DATA_STEWARD` and `COMPLIANCE`; no client role, identity, or assignment headers are read by production code.
- Assignment changes update the development/test assignment registry, reject unknown/non-doctor targets, and write scope-only assignment audit events. Admin and operations state is disabled through the dependency in production.
- Audit responses contain only actor, action, de-identified subject reference, timestamp, result, and trace ID. Operations responses return configuration/posture metadata and never query or render clinical records.
- Added `/admin`, `/admin/audit`, and `/operations` Next.js pages, plus the filterable `AuditTable`. Each includes loading, permission-denied, and unavailable states.

## Test-first evidence

- Backend role-boundary tests were added before routes. Their initial run failed as intended: 6 failures, each `404 Not Found` because the admin/operations routers did not exist.
- The `AuditTable` test was added before the component. Its initial run failed as intended because `@/components/AuditTable` could not be resolved.

## Verification

| Command | Result |
| --- | --- |
| `python.exe -m pytest tests/test_api/test_admin_routes.py tests/test_api/test_ops_routes.py tests/test_api/test_summary_routes.py -q` | PASS — 25 passed. |
| `python.exe -m ruff check` on Task 6 backend/test files | PASS — all checks passed. |
| `npm.cmd --prefix frontend test -- --run` | PASS — 6 files, 20 tests. |
| `npm.cmd --prefix frontend run build` | PASS — Next.js production build and type validation completed; `/admin`, `/admin/audit`, and `/operations` were generated. |
| `git diff --check` | PASS — no whitespace errors. |

## Environment notes

- `loguru` is available in `C:\Users\daohi\OneDrive\Máy tính\github\P-194\.venv` (`import loguru` succeeded); there is no missing-Loguru limitation for this task.
- Chromium is present at `C:\Users\daohi\AppData\Local\ms-playwright\chromium_headless_shell-1223\chrome-headless-shell-win64\chrome-headless-shell.exe`. Playwright was not run because Task 6 requested bounded frontend unit/build verification and this task does not alter the doctor browser scenario.
- The pre-existing deletions of `docs/superpowers/plans/2026-08-03-clinical-retrieval-backend.md` and `docs/superpowers/specs/2026-08-03-clinical-retrieval-backend-design.md` remain intentionally excluded.
- A full `pytest -q` collection remains blocked by the existing non-top-level `pytest_plugins` declaration in `tests/test_api/conftest.py`; this review-fix task ran the requested focused API suites instead.

## Review remediation

- Demo sessions now sign only a server-recognized user identity and expiry. On every development/test request, `DemoSessionProvider` reads the current role and assignment scope from the locked operational registry; `doctor-2` is enabled. Admin grants and revocations therefore affect the next signed doctor request and `GET /api/v1/clinical/patients` without accepting identity, role, or assignment headers. Production remains fail-closed.
- Assignment change and its required scope-only audit event run under one lock. An audit-write failure rolls back the assignment and history, then returns a safe `503`.
- Clinical retrieval, summary generation, and review services now compose structured logging with the compliance registry in development/test, so `/api/v1/admin/audit` shows their safe metadata alongside assignment events. It excludes clinical values, prompts, SQL, secrets, and request headers.
- Fixed Ruff I001 import ordering in `src/main.py`.

## Review-fix regressions

- Initial regression run failed as intended: `doctor-2` login returned `503`; an audit-write failure returned `500` after changing the assignment; and compliance did not receive `GENERATE_CLINICAL_SUMMARY` or `APPROVE_CLINICAL_SUMMARY` events.
- Focused backend verification after the fixes: `tests/test_api/test_admin_routes.py`, `test_ops_routes.py`, `test_summary_routes.py`, and `test_auth.py` passed 31 tests.

## Audit time-filter remediation

- `GET /api/v1/admin/audit` now parses `from_time` and `to_time` at the route boundary, accepts only timezone-aware ISO timestamps, and normalizes accepted values to UTC before comparing them with UTC audit timestamps. Timezone-naive and malformed inputs return the existing safe `422` domain response with a trace ID; their raw query value is not echoed.
- The regression initially reproduced both failures: a naive `from_time` returned `500` after comparing naive and UTC-aware datetimes, while malformed `to_time` returned FastAPI's `422` without a trace ID. The focused two-case regression now passes.
