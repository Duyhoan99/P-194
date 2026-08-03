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
