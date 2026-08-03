# Task 7 Release-Gate Plan

## Scope and safety boundary

Exercise only the local synthetic demo. The smoke script consumes HTTP
responses but emits a fixed allow-list of metadata: status code/status, record
or subject counts, assigned synthetic subject IDs, trace IDs, and lineage
source-table names. It never prints response bodies, summary text, clinical
values, raw records, cookies, request headers, or configuration.

## Delivery sequence

1. Repair pytest collection by moving the shared clinical fixture plugin to
   the top-level conftest; prove the smoke formatter starts red.
2. Implement the standard-library smoke client for health, doctor login,
   assigned-subject metadata, source-table metadata, and summary generation
   plus safe review-state metadata.
3. Add Playwright admin and operations scenarios. They use the real API by
   default and optional explicit mock mode, matching the existing doctor
   scenario; each checks only operational/assignment metadata.
4. Document the exact synthetic-only local setup, actor accounts, supported
   routes, smoke/release commands, and production prerequisites.
5. Run backend, Ruff, diff, frontend, browser, and smoke verification;
   capture any unavailable service/browser limitation in `task-7-report.md`.
6. Commit all release-gate artifacts together, including the requested
   deletion of the obsolete clinical-retrieval-backend plan/design pair while
   retaining the real-world clinical-product pair.
