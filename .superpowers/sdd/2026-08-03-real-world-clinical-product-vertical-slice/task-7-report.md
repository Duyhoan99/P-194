# Task 7 Release-Gate Report

## Delivered

- Added `scripts/run_demo_smoke.py`, a loopback-only standard-library smoke
  client. It verifies health, signed demo login, assigned synthetic subject
  metadata, laboratory source-table lineage, and a generated reviewable draft.
  Its formatter has a strict metadata allow-list: statuses/status codes,
  counts, synthetic subject IDs, trace IDs, and source-table names only.
- Added regression coverage proving the smoke formatter discards clinical
  values, raw records, summary text, and secret-like fields.
- Added admin and operations Playwright actor specifications. They retain real
  API mode as the default and provide explicit mock-mode UI-contract flows for
  assignment changes, doctor dashboard state, operational source posture, and
  append-only audit metadata.
- Moved `pytest_plugins` from `tests/test_api/conftest.py` to the top-level
  `tests/conftest.py`, resolving the pytest collection error under current
  pytest versions.
- Fixed summary persistence when different tables share a source-row key. The
  generator preserves ordinary source-key citations and deterministically
  disambiguates only collisions, preventing duplicate claim/citation storage
  keys without altering lineage.
- Updated README, setup/testing guides, Compose, and Make targets for the
  synthetic-only local demo, smoke command, actor accounts, route boundaries,
  and production prerequisites. Compose now includes a local frontend service.
- Applied safe Ruff-only cleanup to pre-existing utility scripts so the full
  `src tests scripts` lint gate passes.

## Verification

| Command | Result |
| --- | --- |
| `python -m pytest -q` | PASS — 169 passed, 1 skipped. |
| `python -m ruff check src tests scripts` | PASS. |
| `git diff --check` | PASS (Git emitted Windows line-ending warnings only). |
| `npm --prefix frontend test -- --run` | PASS — 6 files, 20 tests. |
| `npm --prefix frontend run build` | PASS — Next.js production build generated `/`, `/admin`, `/admin/audit`, and `/operations`. |
| `playwright test --list` from `frontend/` | PASS — 3 actor specs discovered. |
| Local synthetic API + `python scripts/run_demo_smoke.py` | PASS — health, login, assignment, lineage, draft generation, and review-state metadata completed without printing clinical values/raw rows/secrets. |

## Environment limitations

- Playwright was run in explicit mock mode because a Chromium executable exists
  only at revision `1223`, while this installed Playwright version requires
  revision `1234`. All three specs failed before test execution with the
  missing-executable error. No unrelated browser was substituted or installed.
- Docker is not installed in this environment, so `docker compose config` and
  an actual Compose launch could not be run. The Compose file was updated for
  the documented local backend/frontend profile but needs validation where
  Docker is available.

## Final-review remediation

- Removed all clinical fixture data and source-row keys from the admin E2E
  scenario. Its dashboard check now uses only the assigned de-identified
  subject ID and empty evidence responses.
- Added a shared operational-payload allow-list and unit coverage. Both admin
  and operations specs assert that protected HTTP responses and rendered
  operational pages contain none of the forbidden clinical field names.
- Real API mode is the executable default, never a skip: it logs in as the
  required demo actor and verifies real role denials plus assignment or
  operations/audit effects. An unavailable real server fails visibly.
- Mock mode is explicit (`PLAYWRIGHT_API_MODE=mock`) and role-aware: it starts
  unauthenticated, requires a recognized actor login, returns `403` for
  forbidden requests, and grants metadata only after the correct actor login.
- `playwright test --list` discovered and parsed all three actor specs. No
  browser flow was executed in this remediation because Playwright requires
  Chromium revision `1234`, while only `1223` is installed; launch would fail
  before test execution. No unrelated browser was substituted.

## Final-review verification

| Command | Result |
| --- | --- |
| `npm --prefix frontend test -- --run` | PASS — 7 files, 22 tests. |
| `npm --prefix frontend run build` | PASS — production build and TypeScript validation completed. |
| `python -m pytest -q` | PASS — 170 passed, 1 skipped. |
| `python -m ruff check src tests scripts` | PASS. |
| `git diff --check` | PASS (Windows line-ending warnings only). |
| `playwright test --list` from `frontend/` | PASS — 3 specs discovered/parsed; no browser flow executed because the required Chromium revision is unavailable. |

## Follow-up review remediation

- Corrected the explicit mock-mode admin scenario after its `/admin` safety
  check: it now returns to `/` before using the DoctorApp demo-login controls.
  The scenario can therefore continue with the doctor role and verify the
  assignment effect instead of attempting to find root-only controls on the
  admin route.
- Added a bounded Vitest regression that asserts this exact navigation order
  in the Playwright specification. It ran without requiring a browser binary.

## Follow-up review verification

| Command | Result |
| --- | --- |
| `npm --prefix frontend test -- --run` | PASS - 8 files, 23 tests. |
| `npm --prefix frontend run build` | PASS - production build and TypeScript validation completed. |
| `python -m pytest -q` | PASS - 170 passed, 1 skipped. |
| `python -m ruff check src tests scripts` | PASS. |
| `git diff --check` | PASS. |

Browser execution remains unperformed: the installed Chromium revision is
`1223`, while this Playwright project requires revision `1234`. The new
bounded regression covers the route-order defect without bypassing that
limitation.

## Data-safety review

- The smoke target rejects non-loopback URLs before making a request.
- No real hospital source was connected; the smoke run used only
  `data/synthetic_demo.db`.
- The safety scan matches are existing assertions, fixture names, or policy
  documentation; no raw MIMIC rows, credentials, prompt payloads, or secret
  values were added.
- The requested obsolete `clinical-retrieval-backend` design/plan pair remains
  deleted. The real-world clinical-product design and vertical-slice plan were
  verified present.
