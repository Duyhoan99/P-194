# Task 5 Review-Fix Report

## Fixed findings

- P1 pagination: the frontend now preserves each evidence response's `page.has_more` and `page.next_cursor`, exposes the normalized metadata in workspace types, marks any truncated response `PARTIAL`, adds a warning, and provides a `Reload workspace` path. A successful response with more pages is never represented as complete.
- P1 session expiry: 401 and authentication/session-related 503 responses clear signed-in state, assigned patients, denied state, and the active workspace, then render the explicit re-login screen. Regeneration, export, and other clinical action errors are surfaced in the workspace instead of being void-swallowed.
- P1 approval safety: approval is disabled when any `VALID` claim references a citation ID absent from the summary citation set, with the existing citation-validation error shown.
- P2 persisted status: the backend now exposes an assignment-checked `GET /api/v1/clinical/patients/{subject_id}/summaries/current` adapter. The client loads the server-owned current version/status; when no persisted summary exists it reports `UNAVAILABLE`, never inferred `NOT_STARTED`. A no-summary workspace offers `Generate draft`.
- P2 e2e configuration: Playwright defaults to real API mode, with mock interception enabled only by `PLAYWRIGHT_API_MODE=mock`. The default base URL is `http://localhost:3000`, matching the documented CORS origin; `PLAYWRIGHT_BASE_URL` remains configurable.

## Regression coverage

- API client tests cover page metadata/truncation, server-owned `APPROVED` status, and absent-summary `UNAVAILABLE` status.
- Doctor app tests cover 401 and authentication-related 503 expiry while asserting the old workspace is removed.
- Workspace tests cover reload, generation-without-summary, regeneration/export error surfacing, and pagination warnings.
- Review modal tests cover missing citations referenced by valid claims.
- Backend route tests cover current-summary status preservation and safe 404 for an absent summary.

## Verification

Commands run from this worktree on 2026-08-03:

| Command | Result |
| --- | --- |
| `npm.cmd --prefix frontend test -- --run` | PASS — 5 test files, 17 tests. |
| `npm.cmd --prefix frontend run build` | PASS — optimized Next.js production build completed. |
| `python -m compileall -q src tests` | PASS — Python sources compile. |
| `python -m pytest tests/test_api/test_summary_routes.py -q` | BLOCKED before collection — environment lacks `loguru` (`ModuleNotFoundError: No module named 'loguru'`). |
| Chromium check at `C:\Users\daohi\AppData\Local\ms-playwright\chromium_headless_shell-1234\chrome-headless-shell-win64\chrome-headless-shell.exe` | NOT PRESENT; Playwright was not run and no browser was installed. |

The prior Playwright limitation remains: install Chromium separately, then run the default real-API flow with the backend available:

```powershell
npx.cmd --prefix frontend playwright install chromium
npx.cmd --prefix frontend playwright test frontend/e2e/doctor-flow.spec.ts
```

Use `PLAYWRIGHT_API_MODE=mock` only for an explicit mock-mode local check.

Unrelated deletions of `docs/superpowers/plans/2026-08-03-clinical-retrieval-backend.md` and `docs/superpowers/specs/2026-08-03-clinical-retrieval-backend-design.md` were present in the worktree and are intentionally excluded from the fix commit.
