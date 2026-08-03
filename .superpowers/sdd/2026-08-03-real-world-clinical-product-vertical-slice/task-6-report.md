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
