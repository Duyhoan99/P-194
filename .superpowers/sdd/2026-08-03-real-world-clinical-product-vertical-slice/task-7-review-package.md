# Task 7 Review Package

- Base: `b478b6f`
- Head: `bebff8a`
- Brief: `task-7-brief.md`
- Report: `task-7-report.md`

Review the full release diff:

```powershell
git diff --no-ext-diff -U3 b478b6f..bebff8a
```

Check the release gate and synthetic-only boundary. Release-blocking findings include:

1. smoke output, logs, e2e fixtures, docs or commands exposing raw clinical values, source rows, summary text, secrets, prompts or real hospital data;
2. smoke script making non-loopback calls, accepting unsafe user-controlled API targets, failing to clean up, or silently treating an unhealthy/failed workflow as success;
3. docs implying demo auth/SQLite can be used in production, missing PostgreSQL/trusted SSO/assignment/identity/governance prerequisites, or old duplicate docs retained;
4. full pytest/Ruff/frontend gate regressions, e2e specs that make unsafe authorization claims, or changes that break actor routes.

Run the release checks or inspect the report evidence. Return severity-ordered findings with file/line references, or `APPROVED` with evidence and environment limitations. Do not modify files.
