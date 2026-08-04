# MIMIC-grounded clinical agent and demo backend

## Goal

Make the local backend run a complete evidence-grounded clinical demo using the MIMIC-IV demo folder, with all required retrieval tools, structured AI output, citations, and safe fallback behavior.

## Data architecture

The folder `mimic-iv-clinical-database-demo-2.2` is the source of truth. A setup command loads its `hosp/*.csv` and `icu/*.csv` files into `data/mimic_demo.db`, preserving source table names and identifiers. Runtime retrieval uses this SQLite database in read-only mode with the existing allow-list and timeout boundary; runtime requests never scan arbitrary CSV files.

The development configuration points `CLINICAL_DATABASE_PATH` at `data/mimic_demo.db` and `SUMMARY_DATABASE_PATH` at `data/clinical_summaries.db`. Demo doctor assignments come from `demo_subject_id.csv`, limited to a small configured subset for responsive UI startup. Test mode keeps its isolated fixture subject assignment.

## Tool and agent architecture

The clinical tool registry exposes access-bound tools for patient overview, encounter/timeline, diagnoses and procedures, laboratory results, microbiology, medications, ICU events, and patient metrics. Medication retrieval combines prescriptions/pharmacy evidence with eMAR and ICU input evidence and labels status only when the source supports it. The drug-interaction tool returns an explicit `NOT_LOADED` result because no approved interaction knowledge base exists in the MIMIC folder; it must not invent warnings.

The LangGraph flow is:

```text
authorize → retrieve all required domains → normalize/reconcile → medication status
→ structured generation → citation validation → safety guard → persist DRAFT
```

The generator receives only bounded evidence records and the requested scope. Structured output is parsed as `ClinicalSummaryDraft`, then every claim and conflict reference is validated against source lineage. Prompt, chain-of-thought, unsupported recommendations, diagnoses, treatment advice, and unrelated prose are never returned. If the configured LLM is unavailable or returns invalid output, the agent uses the deterministic evidence-only generator and records a limitation rather than failing the demo or fabricating content.

## API behavior

Existing clinical retrieval routes remain access-controlled. Add a medications route and expose the same domain through the tool registry. Summary generation must return `201` with a persisted `DRAFT`, citations, limitations, and any unresolved medication conflicts when MIMIC evidence is available. LLM failures must return a safe evidence-only draft when fallback is enabled; database/auth/access failures remain explicit `4xx/5xx` errors.

## Verification criteria

- The MIMIC loader creates a usable indexed SQLite database from the repository folder.
- Demo login assigns only subject IDs present in `demo_subject_id.csv`.
- Every required tool returns access-controlled, lineage-bearing records.
- Summary generation produces only validated claims with citations and no recommendations or unrelated text.
- The local metadata-only smoke test passes health, login, assigned subjects, evidence, summary generation, and reviewable draft checks.
- Existing backend and frontend tests remain green, with test-mode fixtures isolated from development MIMIC assignments.
