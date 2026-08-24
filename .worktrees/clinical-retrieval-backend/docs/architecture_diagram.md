# Architecture Diagram — P-194

Đây là sơ đồ tóm tắt cho kiến trúc MVP. Bản mô tả đầy đủ nằm tại [ARCHITECTURE.md](../ARCHITECTURE.md).

## System context

```mermaid
flowchart LR
    Doctor[Doctor] --> UI[Next.js UI]
    Admin[Admin] --> UI
    UI -->|HTTPS / REST| API[FastAPI]
    API --> Auth[RBAC + patient assignment]
    API --> Agent[LangGraph Agent]
    API --> AppDB[(PostgreSQL app DB)]
    Agent --> SQL[Scoped SQL retrieval tools]
    SQL --> MIMIC[(MIMIC-IV 3.1 hosp + icu)]
    Agent --> LLM[Long-context LLM]
    Agent --> Drug[Versioned drug tool]
    API --> PDF[Private PDF storage]
    Optional[(MIMIC-IV-Note / vector DB)] -. optional, NOT LOADED in MVP .-> Agent
```

## Agent flow

```mermaid
flowchart TD
    A[Authorize access] --> B[Plan retrieval]
    B --> C[Retrieve structured MIMIC rows]
    C --> D[Normalize events + preserve lineage]
    D --> E[Reconcile sources and detect conflicts]
    E --> F[Check medication status/tool result]
    F --> G[Generate claims]
    G --> H[Validate evidence, numbers and citations]
    H -->|Critical failure| X[Block draft and show limitation]
    H -->|Valid or partial| I[Safety guard]
    I --> J[Persist DRAFT]
    J --> K[Doctor review]
    K -->|Checklist + valid citations| L[APPROVED]
    K -->|Edit/reject/regenerate| J
```

## Data lineage

```mermaid
flowchart LR
    File[Restricted csv.gz] --> Ingest[Checksum + schema + FK validation]
    Ingest --> Event[Normalized ClinicalEvent]
    Event --> Claim[Clinical Claim]
    Claim --> Citation[Citation: dataset/version/module/table/row/time/value]
    Citation --> Source[Source panel]
```

Every claim shown to a doctor must resolve to a permitted source row. Missing or conflicting evidence remains visible and is never replaced by an LLM guess.

## Component decisions

| Component | MVP decision |
|---|---|
| Backend | FastAPI; all authorization is server-side |
| Agent | LangGraph nodes: authorize → retrieve → normalize → reconcile → claims → validate → cite → guard → draft |
| Structured data | MIMIC-IV 3.1 `hosp` and `icu`; raw files stay outside Git |
| Database | PostgreSQL target; SQLite only for local skeleton |
| Vector store | Disabled until a permitted text source is ingested |
| Export | Private object storage; only approved summaries are official PDFs |
