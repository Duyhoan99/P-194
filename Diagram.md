# Clinical Review Copilot — Architecture Diagrams

Ba sơ đồ dưới đây mô tả kiến trúc MVP gồm cả P0 và P1. Các nguyên tắc xuyên suốt là `patient-first`, `evidence-first`, `deterministic-first`, dữ liệu nguồn bất biến và `human-in-the-loop`.

## 1. System Overview Diagram

Sơ đồ này thể hiện luồng tổng thể từ nhập hồ sơ đến tạo bằng chứng, sinh bản nháp, bác sĩ duyệt và chỉ sau đó mới tạo patient memory hoặc PDF bàn giao.

```mermaid
flowchart TD
    subgraph Actors["Người dùng"]
        direction TB
        Clinician["Bác sĩ: nhập hồ sơ, xem nguồn, hỏi, sửa và duyệt"]
        Admin["Quản trị viên / Auditor: quản lý quyền và xem audit metadata"]
    end

    subgraph Inputs["Định dạng đầu vào"]
        direction TB
        PdfText["PDF có text"]
        PdfScan["PDF scan / ảnh"]
        Fhir["FHIR R4 JSON Bundle"]
        Csv["CSV synthetic: seed, fixture, evaluation"]
    end

    subgraph Frontend["Frontend — Next.js"]
        direction TB
        Login["Đăng nhập"]
        Workspace["Patient Review Workspace"]
        Upload["Upload và import hồ sơ"]
        OcrReview["OCR Verification UI: xem vùng nguồn, sửa và xác nhận"]
        ReviewUI["Evidence Drawer, Ask the Chart và Review Editor"]
    end

    subgraph Backend["Backend — FastAPI Clinical Services"]
        direction TB
        Api["API Guard: session, RBAC, tenant và patient scope"]
        Ingestion["Ingestion Orchestrator: validate MIME/schema, checksum và provenance"]
        FormatRouter{"Source Adapter Router"}
        PdfAdapter["PDF Adapter: PyMuPDF/pdfplumber, layout, bảng và local OCR"]
        FhirAdapter["FHIR Adapter: validate Bundle và map resource"]
        CsvAdapter["CSV Adapter: chỉ fixture/seed synthetic"]
        Canonical["Canonical Patient Model: normalize ngày, đơn vị, thuốc và nguồn"]
        Rules["Deterministic Engine: timeline, trend, conflict, data gap và drug interaction"]
        ReviewService["Review Service: version, lifecycle, watermark và optimistic locking"]
        ApprovalGate{"Approval Gate: confirmation + evidence + version + current watermark"}
        ApprovedReview["Approved Review Version: khóa nội dung, actor và thời điểm duyệt"]
        Memory["Patient Memory Service: approved-only projection"]
        PdfExport["PDF Exporter: server-side từ approved version"]
        Audit["Audit Service: PHI access, evidence, ask, edit, approve và export"]
    end

    subgraph Intelligence["AI và Evidence Layer"]
        direction TB
        Agent["LangGraph Orchestrator: scoped tools, không truy vấn DB tự do"]
        Retrieval["Patient-scoped Retrieval: SQL + keyword/vector search"]
        Evidence["Evidence Assembler: facts + source_id + trang/block/resource"]
        Llm["Approved LLM Endpoint"]
        Verifier["Fact Verifier: số, ngày, đơn vị, phủ định và citation"]
        OutputRoute{"Loại đầu ra"}
        AskResult["Ask response: answer/status/citations hoặc abstain"]
    end

    subgraph Storage["Private Data Stores"]
        direction TB
        Raw["Object Storage: raw source bất biến + approved export có version/checksum"]
        Pg["PostgreSQL: canonical records, derived facts, review, memory và audit"]
        Vector["Chroma: note/PDF chunks kèm tenant_id, patient_id và provenance"]
    end

    Clinician -->|"(1) đăng nhập"| Login
    Admin -->|"(1) đăng nhập"| Login
    Login -->|"(2) tạo phiên an toàn"| Api
    Api -->|"(3) phiên và dữ liệu đã authorize"| Workspace

    PdfText -->|"(4) chọn file"| Upload
    PdfScan -->|"(4) chọn file"| Upload
    Fhir -->|"(4) chọn file"| Upload
    Csv -->|"(4) seed/evaluation"| Upload
    Upload -->|"(5) upload kèm patient_id"| Api
    Api -->|"(6) import đã authorize"| Ingestion
    Ingestion -->|"(7) lưu nguyên bản trước khi xử lý"| Raw
    Ingestion -->|"(8) phát hiện định dạng"| FormatRouter
    FormatRouter -->|"(9a) PDF text/scan"| PdfAdapter
    FormatRouter -->|"(9b) FHIR R4"| FhirAdapter
    FormatRouter -->|"(9c) CSV synthetic"| CsvAdapter

    PdfAdapter -->|"(10a) extraction đủ tin cậy + provenance"| Canonical
    PdfAdapter -->|"(10b) OCR/table low-confidence → needs_verification"| OcrReview
    OcrReview -->|"(11) clinician sửa/xác nhận"| Api
    Api -->|"(12) dữ liệu extraction đã xác minh"| Canonical
    FhirAdapter -->|"(10) resource hợp lệ"| Canonical
    CsvAdapter -->|"(10) fixture hợp lệ"| Canonical
    Canonical -->|"(13) records có provenance"| Pg
    Canonical -->|"(14) note/PDF chunks đã khóa patient scope"| Vector
    Pg -->|"(15) dữ liệu cấu trúc"| Rules
    Rules -->|"(16) derived facts có rule/profile version"| Pg

    Workspace -->|"(17) Generate Review hoặc Ask the Chart"| Api
    Api -->|"(18) task đã authorize"| Agent
    Agent -->|"(19) scoped evidence request"| Retrieval
    Pg -->|"(20a) structured facts + derived facts"| Retrieval
    Vector -->|"(20b) note/PDF evidence đã lọc patient trước rerank"| Retrieval
    Retrieval -->|"(21) evidence candidates"| Evidence
    Evidence -->|"(22) evidence packet có citation"| Agent
    Agent -->|"(23) evidence-grounded prompt"| Llm
    Llm -->|"(24) structured draft claims"| Verifier
    Verifier -->|"(25) supported claims hoặc abstention"| OutputRoute
    OutputRoute -->|"(26a) Ask the Chart"| AskResult
    OutputRoute -->|"(26b) Clinical Review"| ReviewService
    AskResult -->|"(27a) answer + citations"| ReviewUI
    ReviewService -->|"(27b) generated review + citations"| ReviewUI

    ReviewUI -->|"(28) mở nguồn, sửa, xác nhận, approve/reject"| Api
    Api -->|"(29) review command + expected_version"| ReviewService
    ReviewService -->|"(30) yêu cầu approve"| ApprovalGate
    ApprovalGate -->|"(31a) pass → approved"| ApprovedReview
    ApprovalGate -->|"(31b) stale/conflict/fail → chặn duyệt và xuất"| ReviewUI
    ApprovedReview -->|"(32) persist trạng thái/version"| Pg
    ApprovedReview -->|"(33a) project approved content"| Memory
    ApprovedReview -->|"(33b) render approved content"| PdfExport
    Memory -->|"(34) memory version mới"| Pg
    PdfExport -->|"(34) approved PDF + checksum"| Raw
    Memory -->|"(35) approved memory"| ReviewUI
    PdfExport -->|"(35) PDF bàn giao"| ReviewUI

    Api -->|"Mọi hành động lâm sàng"| Audit
    Audit -->|"Audit event tối thiểu, không lưu raw PHI/prompt"| Pg
```

## 2. Agent Flow Diagram

Sơ đồ này tách rõ `review_generation` và `ask_chart`. Ask the Chart kết thúc bằng câu trả lời có citation hoặc abstain; chỉ review mới đi vào quy trình bác sĩ duyệt.

```mermaid
flowchart TD
    Start["Yêu cầu: review_generation hoặc ask_chart"]

    subgraph Access["1. Access and Scope Guard"]
        direction TB
        Validate["Validate session, role, tenant_id và patient_id"]
        Deny["Deny + audit: không có quyền hoặc sai patient scope"]
        TaskType{"Task type?"}
    end

    subgraph Context["2. Context and Evidence Routing"]
        direction TB
        ReviewContext["Review context: deterministic facts, verified notes, approved memory và data watermark"]
        AskPolicy{"Câu hỏi có thuộc phạm vi lịch sử hồ sơ?"}
        QueryRoute{"Question route"}
        Structured["retrieve_structured: timeline, labs, medications và rule flags"]
        Notes["retrieve_notes: lexical + vector, patient-filter trước rerank"]
        Hybrid["retrieve_both: structured + notes"]
        NotAllowed["not_allowed: từ chối khuyến nghị điều trị/quyết định lâm sàng"]
        EvidenceGate["Evidence Gate: loại unsupported và needs_verification chưa được clinician xác nhận"]
    end

    subgraph Reasoning["3. Grounded Generation and Verification"]
        direction TB
        Generate["LLM generate_grounded từ evidence packet"]
        Verify["verify_claims: số, ngày, đơn vị, phủ định, source và citation"]
        Supported{"Evidence đủ hỗ trợ claim?"}
        Abstain["Abstain / not_found / conflicting: nêu rõ không đủ bằng chứng"]
        Finalize["finalize_public: chỉ answer/review, status và citations; bỏ prompt/tool trace"]
        PublicType{"Kết quả của task nào?"}
    end

    subgraph AskOutput["4A. Ask the Chart Output"]
        direction TB
        Answer["Trả answer + status + citations"]
        AskAudit["Audit ask và evidence view; không tạo review/memory/PDF"]
    end

    subgraph ReviewFlow["4B. Human-in-the-loop Review Lifecycle"]
        direction TB
        Generated["generated: persist draft + evidence + data_watermark"]
        UnderReview["under_review: clinician mở editor và evidence"]
        Edited["edited: lưu version mới bằng expected_version"]
        Decision{"Clinician approve hay reject?"}
        Reject["rejected: lưu feedback; không tạo memory/PDF"]
        ApproveGate{"Approve gate: clinician_confirmation + evidence pass + version khớp + watermark hiện tại"}
        Blocked["409 / validation error: giữ review để sửa hoặc tải version mới"]
        Stale["stale: chặn approve/export; phải regenerate và review lại"]
        Approved["approved: khóa đúng review_version_id và actor/time"]
        Memory["Tạo patient memory version từ approved content"]
        Export["Cho phép server render PDF từ approved_review_version_id"]
    end

    Start -->|"(1) request"| Validate
    Validate -->|"Không đạt"| Deny
    Validate -->|"Đạt"| TaskType

    TaskType -->|"(2R) review_generation"| ReviewContext
    ReviewContext -->|"(3R) context có provenance"| EvidenceGate

    TaskType -->|"(2A) ask_chart"| AskPolicy
    AskPolicy -->|"Không"| NotAllowed
    AskPolicy -->|"Có"| QueryRoute
    QueryRoute -->|"(3A) structured"| Structured
    QueryRoute -->|"(3B) notes"| Notes
    QueryRoute -->|"(3C) hybrid"| Hybrid
    Structured --> EvidenceGate
    Notes --> EvidenceGate
    Hybrid --> EvidenceGate
    NotAllowed --> Abstain

    EvidenceGate -->|"(4) evidence packet"| Generate
    Generate -->|"(5) draft claims"| Verify
    Verify -->|"(6) verification results"| Supported
    Supported -->|"Không"| Abstain
    Supported -->|"Có"| Finalize
    Abstain --> Finalize
    Finalize -->|"(7) public output"| PublicType

    PublicType -->|"ask_chart"| Answer
    Answer --> AskAudit

    PublicType -->|"review_generation"| Generated
    Generated -->|"(8) clinician mở review"| UnderReview
    UnderReview -->|"(9a) chỉnh sửa"| Edited
    Edited -->|"(9b) lưu tiếp"| Edited
    UnderReview -->|"(9c) không chỉnh sửa"| Decision
    Edited -->|"(9c) hoàn tất chỉnh sửa"| Decision
    Decision -->|"Reject"| Reject
    Decision -->|"Approve"| ApproveGate
    ApproveGate -->|"Version conflict hoặc thiếu confirmation/evidence"| Blocked
    Blocked -->|"Sửa hoặc reload đúng version"| UnderReview
    ApproveGate -->|"Watermark thay đổi"| Stale
    ApproveGate -->|"Pass"| Approved
    Approved -->|"(10a) approved-only"| Memory
    Approved -->|"(10b) approved-only"| Export
    Approved -->|"Có dữ liệu nguồn mới sau duyệt"| Stale
    Stale -->|"(11) regenerate"| Start
```

## 3. Deployment Diagram

Sơ đồ deployment giữ đúng network boundary: chỉ reverse proxy public. OCR chạy cục bộ trong backend ở MVP để PDF/ảnh không bị gửi sang dịch vụ OCR bên ngoài.

```mermaid
flowchart TD
    Users["Browser trên thiết bị demo"]

    subgraph PublicZone["Public Zone"]
        direction TB
        Proxy["HTTPS Reverse Proxy: TLS termination, CORS allowlist và rate limit"]
    end

    subgraph PrivateNetwork["Private Application Network"]
        direction TB
        Frontend["Next.js Frontend Container"]
        Backend["FastAPI Backend Container: API, clinical services và LangGraph"]
        LocalOcr["Local OCR Runtime: page render + PaddleOCR/VietOCR/Tesseract"]
        Postgres["PostgreSQL Service: auth, canonical data, reviews, memory và audit"]
        Chroma["Chroma Persistent Volume: patient-scoped note/PDF embeddings"]
        RawStorage["Raw/PDF Storage: immutable sources và approved exports"]
    end

    subgraph ExternalServices["Approved External Services"]
        direction TB
        LlmApi["Approved LLM API qua TLS: chỉ nhận evidence tối thiểu được phép"]
    end

    subgraph Delivery["CI/CD"]
        direction TB
        Git["Git Repository"]
        CI["GitHub Actions: lint, test, security scan và image build"]
        Registry["Private Container Registry"]
    end

    Users -->|"(1) HTTPS"| Proxy
    Proxy -->|"(2a) / → web UI"| Frontend
    Proxy -->|"(2b) /api → authenticated API"| Backend
    Backend -->|"(3) PDF scan/image pages; không rời private network"| LocalOcr
    LocalOcr -->|"(4) text, word bbox, confidence và engine version"| Backend
    Backend -->|"(5) transactions đã khóa tenant/patient"| Postgres
    Backend -->|"(6) filtered vector retrieval"| Chroma
    Backend -->|"(7) raw source/checksum và approved PDF"| RawStorage
    Backend -->|"(8) evidence-grounded request qua TLS"| LlmApi
    LlmApi -->|"(9) structured draft; không được tự quyết định lâm sàng"| Backend

    Git -->|"(10) push / pull request"| CI
    CI -->|"(11) test pass → signed/versioned images"| Registry
    Registry -->|"(12a) deploy frontend image"| Frontend
    Registry -->|"(12b) deploy backend image"| Backend
```

### Deployment assumptions của MVP

- Chỉ `HTTPS Reverse Proxy` có cổng public; frontend, backend, PostgreSQL, Chroma và raw storage đều ở private network.
- Browser gọi `/` và `/api` qua cùng reverse proxy; frontend container không truy cập trực tiếp database, vector store hoặc LLM.
- OCR P1 chạy cục bộ trong backend. Nếu sau này tách OCR/ingestion thành worker riêng, phải bổ sung durable job queue/broker thay vì vẽ worker đứng một mình.
- Backend chỉ gửi evidence tối thiểu, được phép và đã khóa patient scope tới LLM endpoint qua TLS.
- PDF export được render phía server từ đúng `approved_review_version_id`; client không gửi nội dung tùy ý để xuất.

## Các invariant được ba diagram bảo vệ

| ID | Invariant |
|---|---|
| INV-01 | Mọi truy cập lâm sàng đều qua Auth/RBAC và tenant/patient scope trước khi xử lý. |
| INV-02 | Raw PDF/FHIR/CSV được lưu bất biến cùng checksum trước khi parse/normalize. |
| INV-03 | PDF, FHIR và CSV đi qua adapter riêng; CSV chỉ dùng synthetic fixture/seed. |
| INV-04 | OCR/table low-confidence mang `needs_verification` và không trở thành verified fact trước khi clinician xác nhận. |
| INV-05 | Timeline, trend, conflict, data gap và drug interaction chạy bằng deterministic code/rule trước LLM. |
| INV-06 | Retrieval lọc tenant/patient trước rerank; citation quay lại đúng file/trang/block hoặc FHIR resource. |
| INV-07 | Ask the Chart trả answer/citation/abstain và audit, không đi vào quy trình approve. |
| INV-08 | Review phải qua lifecycle, evidence gate, clinician confirmation, version check và current watermark. |
| INV-09 | Review `stale`, version conflict hoặc unsupported claim bị chặn approve/export. |
| INV-10 | Patient memory và PDF chỉ được tạo từ đúng approved review version. |
| INV-11 | Chỉ reverse proxy public; OCR và kho dữ liệu bệnh nhân ở private network. |
| INV-12 | PHI access, evidence view, ask, edit, approve/reject, memory và export đều được audit. |
