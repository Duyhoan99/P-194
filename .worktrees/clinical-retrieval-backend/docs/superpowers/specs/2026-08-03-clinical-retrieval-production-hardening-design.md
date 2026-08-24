# Clinical Retrieval Production Hardening Design

**Date:** 2026-08-03  
**Status:** Design approved; implementation pending review of this document  
**Scope:** Make the existing clinical retrieval backend safe to evolve from local MIMIC-IV development to a production deployment backed by an approved hospital data source.

## 1. Safety boundary

MIMIC-IV 3.1 remains the development and synthetic-integration profile. It is de-identified research data and must not be presented as a live patient record or used as the production clinical source. Production requires an approved source profile, a trusted patient-identity mapping, access governance, audit retention, backup/recovery, and clinical safety review.

The application remains evidence-only. It does not diagnose, recommend treatment, synthesize unverified facts, or allow an LLM to generate SQL. If identity, authorization, source availability, lineage, or data freshness cannot be verified, the request fails closed or returns an explicit limitation.

## 2. Runtime architecture

```text
Verified identity / hospital IdP
             |
             v
      AuthProvider + AssignmentProvider
             |
             v
HTTP / tool -> ClinicalRetrievalService -> ClinicalRepository
                                             |             |
                               SQLite read-only       PostgreSQL read-only
                                local/test only        production adapter
```

The repository protocol and clinical response models remain shared. SQLite is retained for local development and synthetic fixtures. Production selects a PostgreSQL adapter through configuration; the service must not silently fall back from PostgreSQL to SQLite.

Database migrations and indexes are an operational/setup responsibility. The application opens the production database with a read-only database role and never creates tables or indexes at startup.

## 3. Configuration and source profiles

Add explicit settings for:

- `clinical_backend`: `sqlite` or `postgresql`, with no implicit environment-based default in production;
- backend-specific connection settings supplied through secrets, not committed files;
- `clinical_source_dataset`, `clinical_source_version`, and a source profile identifier;
- maximum page size, maximum cursor age, query timeout, and optional maximum time-window width;
- a production auth provider name and assignment provider name.

The MIMIC profile may require `dataset=MIMIC-IV` and `version=3.1`. `SourceLineage` must validate against the active source profile rather than hard-code MIMIC for every future adapter. The response must include the active source profile and a data-as-of/freshness limitation when the source supplies one.

No patient count, subject ID, encounter ID, or fixture size is hard-coded. Synthetic IDs such as `101` are test data only.

## 4. Authentication and authorization

Introduce protocols for a trusted `AuthProvider` and `AssignmentProvider`:

- `AuthProvider` derives `user_id`, role/permissions, tenant or facility scope, and trace ID from a verified token or trusted upstream identity;
- `AssignmentProvider` checks subject and encounter/stay scope server-side, with deny-by-default behavior;
- client-supplied identity, role, assignment lists, and patient identifiers are never accepted as authorization evidence;
- the demo provider is available only through test/development dependency injection and raises configuration errors in production;
- production startup or readiness fails when the required provider is absent or misconfigured.

Authorization must happen before patient-existence or clinical-data queries. The API may return a generic `403` to avoid revealing whether an unauthorized subject exists. Audit events record scope and outcome only; they never include values, notes, prompts, SQL, or access tokens.

## 5. Pagination and ordering

Use bounded cursor/keyset pagination as the public contract. `page_size` is bounded per request but there is no artificial total-patient or total-record limit.

The cursor is opaque, authenticated, expires, and is bound to the subject, hadm/stay scope, time filters, source profile, endpoint, and ordering version. A modified, expired, or cross-query cursor returns `422` without querying clinical tables.

Every event query defines a typed deterministic order using:

1. effective event time, descending, with explicit `NULL` behavior;
2. source table/domain discriminator;
3. native numeric or text source key columns, not the rendered `source_row_key` string.

For records whose primary time is missing, the same effective time (for example `COALESCE(charttime, storetime)`) is used consistently in filtering, ordering, cursor encoding, and lineage. Composite domains define one global order before applying the page boundary; they do not independently apply `LIMIT` and then merge incomplete pages.

Offset may remain as an internal compatibility option only with a strict maximum and must not be the default production pagination strategy.

## 6. Database and performance

The production PostgreSQL adapter uses parameterized, allow-listed queries, a read-only role, statement timeouts, cancellation on request disconnect, bounded result materialization, and connection-pool limits. Queries must be scoped by subject first and must validate hadm/stay ownership before retrieving clinical rows.

Indexes are created and versioned outside the application. They must match actual predicates and ordering, generally as composite indexes such as `(subject_id, hadm_id, effective_time, source_key)` where the table supports those columns; separate single-column indexes are not assumed to solve the query. The setup check records `EXPLAIN`/query-plan evidence and a benchmark on a volume representative of production. A two-second MIMIC-demo target is not treated as a universal clinical SLA.

The SQLite adapter keeps the same contract for tests, uses read-only mode, and has no production-only behavior hidden in test fixtures.

## 7. Failure and clinical-safety behavior

- missing or stale source: `PARTIAL`/`NOT_LOADED` with explicit limitations;
- invalid or unverifiable lineage: do not return the record;
- auth not configured: `503`/readiness failure, never an open endpoint;
- denied access: `403` with no existence leak where policy requires it;
- invalid scope/filter/cursor: `422` before clinical fetch;
- database unavailable: `503` with a safe message;
- timeout/cancellation: `504` or request cancellation, with no partial response presented as complete;
- empty result: `EMPTY`, never fabricated data.

Every response and error has a trace ID. Observability may record counts, latency, source status, and query shape identifiers, but not clinical values or raw SQL parameters.

## 8. Test and rollout requirements

Add synthetic tests covering multiple subjects, encounters, stays, equal timestamps, null times, cursor tampering/reuse/expiry, page boundaries across multiple source tables, timezone conversion, access isolation, provider absence, query cancellation, database errors, and allow-list enforcement. Use generated synthetic rows to test volume; never copy MIMIC rows into fixtures.

Add contract tests for both SQLite and PostgreSQL repository adapters. PostgreSQL integration tests run only against an explicitly provisioned test database and are skipped with a clear reason when unavailable; they must never use production credentials.

Before clinical use, require a staged rollout with migration verification, backup/restore test, access-review sign-off, audit-retention policy, monitoring, representative performance testing, and clinician/data-owner acceptance. The application is not declared production-ready merely because unit tests pass.

## 9. Non-goals

This change does not invent a hospital authentication integration, patient-identity mapping, production database credentials, clinical governance policy, or treatment/diagnosis generation. Those must be supplied and approved by the deploying organization. The code provides strict interfaces and safe failure behavior until they exist.
