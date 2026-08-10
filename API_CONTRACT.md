# Hợp đồng API — Trợ lý rà soát hồ sơ lâm sàng

Phiên bản hợp đồng: `1.0.0`  
Tiền tố API: `/api/v1`  
Nguồn thiết kế: [`Readme-Clinical.md`](Readme-Clinical.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`Diagram.md`](Diagram.md)

### Vai trò và quyền ưu tiên

File này là nguồn sự thật cuối cùng cho HTTP method/path, header, request/response, enum, error code và quy tắc tương thích. Phạm vi sản phẩm/acceptance vẫn theo `Readme-Clinical.md`; invariant, state và ranh giới component theo `ARCHITECTURE.md`; `Diagram.md` chỉ minh họa. Khi đổi public contract, phải cập nhật file này trước hoặc trong cùng change, sau đó đồng bộ bảng API trong hai tài liệu còn lại, diagram nếu luồng đổi, OpenAPI/type sinh ra và contract tests.

AI không được suy diễn trường bắt buộc từ ví dụ giao diện, tự thêm endpoint gần nghĩa, hoặc dùng tên rút gọn trong code. Base path là `/api/v1`, ngoại trừ `GET /health` được ghi rõ trong hợp đồng.

### Dataset và fixture contract

Contract tests và mock của cả ba thành viên phải lấy cùng ID/case từ `data/demo_mvp_v1/dataset_manifest.json@1.3.0` và `data/demo_mvp_v1/gold/`. Thành viên 1 ánh xạ FHIR/PDF/OCR sang schema HTTP và evidence packet; thành viên 2 không đọc file nguồn trực tiếp mà nhận `AgentRequest`; thành viên 3 không tự đặt response field mà sinh mock theo schema trong file này. `patient_id`, `document_id`, `claim/evidence ID`, lifecycle status và error code trong fixture phải khớp tuyệt đối giữa ba work package.

Tài liệu này là điểm thống nhất để ba thành viên phát triển song song:

| Thành viên | Phạm vi sở hữu | Giao diện bàn giao chính |
|---|---|---|
| 1 — Dữ liệu và máy chủ | Cơ sở dữ liệu, tiếp nhận dữ liệu, chuẩn hóa, dòng thời gian, quy tắc, lưu phiên bản rà soát | API HTTP, mô hình dữ liệu chuẩn, gói bằng chứng cho thành viên 2 |
| 2 — AI, an toàn và đánh giá | Truy xuất, LangGraph, tạo nội dung, kiểm chứng nhận định, chính sách bộ nhớ | `AgentRequest` và `AgentResult` nội bộ cho thành viên 1 |
| 3 — Sản phẩm, giao diện và triển khai | Đăng nhập, không gian bệnh nhân, giao diện bằng chứng, chỉnh sửa, biểu đồ, PDF, kiểm toán | Chỉ phụ thuộc hợp đồng HTTP và dữ liệu giả lập trong tài liệu này |

## 1. Quyết định đã chốt

1. `POST /api/v1/ingestions` là API nhập dữ liệu chính thức. Không triển khai thêm `/documents/import`.
2. Đầu vào lâm sàng chỉ gồm PDF có chữ, PDF scan/ảnh và FHIR R4 JSON Bundle.
3. Dữ liệu phát triển và kiểm thử dùng fixture FHIR hoặc JSON.
4. API sử dụng JSON, trừ tải tệp lên (`multipart/form-data`), xem trang tài liệu (ảnh) và tải PDF.
5. Xác thực bằng cookie phiên `HttpOnly`, `Secure`, `SameSite=Lax`. Giao diện không lưu mã phiên trong bộ nhớ trình duyệt.
6. `patient_id` lấy từ đường dẫn và phải được máy chủ kiểm tra quyền. Không lấy mã bệnh nhân từ câu hỏi gửi cho AI để phân quyền.
7. Mọi thay đổi bản rà soát phải gửi `expected_version`. Phiên bản sai trả `409 VERSION_CONFLICT`.
8. Bản rà soát chỉ được duyệt khi xác nhận của bác sĩ bằng `true`, bằng chứng hợp lệ, đúng phiên bản và dấu mốc dữ liệu còn hiện hành.
9. Bộ nhớ bệnh nhân và PDF chỉ được tạo từ đúng phiên bản đã duyệt.
10. Dữ kiện OCR có độ tin cậy thấp mang trạng thái `needs_verification`; AI không được dùng nó như sự thật trước khi bác sĩ xác minh.
11. Định dạng ngày giờ là ISO 8601 có múi giờ, ví dụ `2026-08-20T08:20:00+07:00`. Ngày dùng `YYYY-MM-DD`.
12. Các số nhận dạng là chuỗi mờ, không suy ra tenant hoặc bệnh nhân từ cấu trúc mã.
13. Không trả dấu vết công cụ, prompt, câu lệnh SQL, khóa bí mật hoặc toàn bộ ghi chú lâm sàng trong API công khai.

## 2. Quy ước HTTP chung

### 2.1. Header

| Header | Bắt buộc | Ý nghĩa |
|---|---:|---|
| `Content-Type: application/json` | Có với JSON | Kiểu nội dung yêu cầu |
| `Accept: application/json` | Khuyến nghị | Kiểu nội dung mong muốn |
| `X-Request-ID` | Không | Mã theo dõi do client tạo; máy chủ tạo nếu thiếu |
| `Idempotency-Key` | Có với nhập dữ liệu và xuất PDF | Chống tạo lặp khi gửi lại yêu cầu |
| `If-None-Match` | Không | Tái sử dụng dữ liệu đọc theo `ETag` |

Mọi phản hồi JSON thành công có header `X-Request-ID`. Phản hồi đọc có thể có `ETag`.

### 2.2. Phân trang

Yêu cầu:

```text
?page=1&page_size=20
```

Giới hạn: `page >= 1`, `1 <= page_size <= 100`.

Phản hồi:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

### 2.3. Lỗi chuẩn

```json
{
  "code": "VERSION_CONFLICT",
  "message": "Bản rà soát đã được cập nhật. Hãy tải lại trước khi lưu.",
  "request_id": "req_01J5Z8KX",
  "details": {
    "current_version": 4
  }
}
```

| Mã lỗi | HTTP | Khi sử dụng |
|---|---:|---|
| `VALIDATION_ERROR` | 422 | Nội dung yêu cầu sai cấu trúc |
| `AUTH_INVALID` | 401 | Đăng nhập hoặc phiên không hợp lệ |
| `AUTH_FORBIDDEN` | 403 | Thiếu vai trò hoặc quyền |
| `RESOURCE_NOT_FOUND` | 404 | Không tồn tại hoặc nằm ngoài phạm vi được phép |
| `PATIENT_SCOPE_DENIED` | 404 | Không được xem bệnh nhân; dùng 404 để tránh lộ sự tồn tại |
| `INVALID_TRANSITION` | 409 | Trạng thái hiện tại không cho phép hành động |
| `VERSION_CONFLICT` | 409 | `expected_version` đã cũ |
| `REVIEW_STALE` | 409 | Dữ liệu nguồn đã thay đổi |
| `EVIDENCE_REQUIRED` | 409 | Còn nhận định không đủ bằng chứng |
| `CONFIRMATION_REQUIRED` | 409 | Bác sĩ chưa xác nhận đã kiểm tra |
| `VERIFICATION_REQUIRED` | 409 | Còn dữ kiện bắt buộc xác minh |
| `EXPORT_NOT_ALLOWED` | 409 | Chưa duyệt, sai phiên bản hoặc đã lỗi thời |
| `DUPLICATE_REQUEST` | 409 | Khóa chống lặp được dùng với nội dung khác |
| `FILE_TOO_LARGE` | 413 | Tệp vượt giới hạn cấu hình |
| `UNSUPPORTED_FORMAT` | 415 | Kiểu tệp không được hỗ trợ |
| `RATE_LIMITED` | 429 | Vượt giới hạn tần suất |
| `LLM_UNAVAILABLE` | 503 | Dịch vụ mô hình ngôn ngữ không sẵn sàng |
| `AUDIT_UNAVAILABLE` | 503 | Không thể ghi kiểm toán; thao tác nhạy cảm bị chặn |
| `INTERNAL_ERROR` | 500 | Lỗi nội bộ đã được che chi tiết |

## 3. Kiểu dữ liệu dùng chung

### 3.1. Người dùng và bệnh nhân

```ts
type UserMe = {
  user_id: string;
  display_name: string;
  tenant_id: string;
  roles: Array<"clinician" | "administrator" | "auditor">;
  permissions: string[];
};

type PatientSummary = {
  patient_id: string;
  pseudonym: string;
  age: number | null;
  sex: "male" | "female" | "other" | "unknown";
  primary_condition: string | null;
  last_encounter_at: string | null;
  latest_data_watermark: string | null;
};
```

### 3.2. Trích dẫn và bằng chứng

```ts
type SourceReference = {
  source_type: "pdf" | "fhir" | "canonical_record" | "rule";
  source_record_id: string;
  source_time: string | null;
};

type DocumentCitation = {
  citation_id: string;
  source_type: "pdf";
  document_id: string;
  document_name: string;
  page_number: number;             // bắt đầu từ 1
  block_id: string | null;
  table_id: string | null;
  bbox: [number, number, number, number] | null;
  char_start: number | null;
  char_end: number | null;
  snippet: string;
  source_checksum: string;
  extraction_version: string;
  ocr_confidence: number | null;    // từ 0 đến 1
};

type FhirCitation = {
  citation_id: string;
  source_type: "fhir";
  document_id: string;
  resource_type: string;
  resource_id: string;
  json_pointer: string | null;
  snippet: string;
  source_checksum: string;
};

type RecordCitation = {
  citation_id: string;
  source_type: "canonical_record" | "rule";
  source_record_id: string;
  source_time: string | null;
  snippet: string;
  rule_version: string | null;
};

type Citation = DocumentCitation | FhirCitation | RecordCitation;

type VerifiedClaim = {
  claim_id: string;
  text: string;
  status: "verified" | "needs_verification" | "unsupported" | "invalid";
  confidence: "high" | "medium" | "low" | null;
  citations: Citation[];
  generator_version: string;
};
```

Quy tắc bắt buộc:

- Claim `verified` phải có ít nhất một citation.
- Claim `unsupported` và `invalid` không được đưa vào phần nội dung được duyệt như một sự thật.
- Citation PDF phải mở được đúng tài liệu, trang và vùng nguồn.
- API chỉ trả đoạn trích tối thiểu cần thiết, không trả toàn bộ tài liệu.

### 3.3. Bản rà soát

```ts
type ReviewStatus =
  | "generated"
  | "under_review"
  | "edited"
  | "approved"
  | "rejected"
  | "stale";

type ReviewSection = {
  section_code:
    | "patient_overview"
    | "active_conditions"
    | "current_medications"
    | "recent_results"
    | "changes_to_review"
    | "data_gaps";
  title: string;
  claims: VerifiedClaim[];
  clinician_text: string | null;
};

type ReviewResponse = {
  review_id: string;
  review_version_id: string;
  patient_id: string;
  status: ReviewStatus;
  version: number;
  generated_at: string;
  updated_at: string;
  approved_at: string | null;
  data_watermark: string;
  is_current_watermark: boolean;
  profile_versions: string[];
  coverage: {
    start_date: string | null;
    end_date: string | null;
    encounter_count: number;
  };
  sections: ReviewSection[];
  conflicts: ConflictFlag[];
  drug_interactions: DrugInteractionFlag[];
  data_quality_flags: DataQualityFlag[];
  disclaimer: string;
  clinician_confirmation: boolean | null;
  memory_version_used: number | null;
};
```

### 3.4. Dòng thời gian, xu hướng và cờ an toàn

```ts
type TimelineEvent = {
  event_id: string;
  event_type: "encounter" | "observation" | "medication" | "condition" | "allergy" | "note";
  occurred_at: string;
  title: string;
  summary: string;
  citations: Citation[];
};

type TrendPoint = {
  observed_at: string;
  value: number;
  unit: string;
  raw_value?: number;
  raw_unit?: string;
  calculation?: CalculationProvenance;
  reference_range: { low: number | null; high: number | null } | null;
  citations: Citation[];
};

type CalculationProvenance = {
  calculation_id: string;
  calculation_version: string;
  method: "unit_conversion" | "derived";
  source: string;
  input_evidence_ids: string[];
};

type ConflictFlag = {
  conflict_id: string;
  conflict_type: string;
  description: string;
  status: "open" | "reviewed" | "resolved";
  source_a: Citation[];
  source_b: Citation[];
};

type DrugInteractionFlag = {
  flag_id: string;
  ingredients: string[];
  severity: "low" | "moderate" | "high" | "unknown";
  description: string;
  rule_source: string;
  rule_version: string;
  status: "open" | "reviewed" | "not_applicable" | "superseded";
  citations: Citation[];
};

type DataQualityFlag = {
  flag_id: string;
  code: string;
  severity: "info" | "warning" | "blocking";
  message: string;
  status: "open" | "verified" | "dismissed";
  verification_item_id: string | null;
};
```

`TrendPoint.value/unit` luôn là giá trị canonical. Khi điểm dữ liệu được đổi đơn vị hoặc suy diễn, backend phải trả `raw_value/raw_unit` và `calculation`; công thức, hệ số và rounding tuân theo `ARCHITECTURE.md` mục 14.11.1. Điểm lấy nguyên giá trị nguồn có thể bỏ ba trường tùy chọn này. Frontend chỉ hiển thị kết quả và provenance, không tự chuyển đổi hoặc tính lại.

## 4. Hợp đồng API HTTP

### 4.1. Sức khỏe hệ thống

#### `GET /health`

Không yêu cầu đăng nhập.

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### 4.2. Xác thực

#### `POST /auth/login`

```json
{
  "email": "doctor@example.test",
  "password": "demo-password"
}
```

Trả `200 UserMe` và thiết lập cookie phiên. Thông báo đăng nhập thất bại luôn chung chung.

#### `POST /auth/logout`

Trả `204 No Content` và hủy phiên hiện tại.

#### `GET /auth/me`

Trả `200 UserMe`.

### 4.3. Bệnh nhân

#### `GET /patients`

Quyền: `patient.list`.

Tham số: `search`, `page`, `page_size`.

```json
{
  "items": [
    {
      "patient_id": "pat_01J5Z9",
      "pseudonym": "BN-001",
      "age": 58,
      "sex": "female",
      "primary_condition": "Đái tháo đường típ 2",
      "last_encounter_at": "2026-08-20T08:00:00+07:00",
      "latest_data_watermark": "wm_01J5ZA"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

### 4.4. Tiếp nhận và xử lý dữ liệu

#### `POST /ingestions`

Quyền: `clinical.import`. Header bắt buộc: `Idempotency-Key`.

`multipart/form-data`:

| Trường | Kiểu | Bắt buộc | Ghi chú |
|---|---|---:|---|
| `file` | tệp | Có | PDF hoặc FHIR R4 JSON Bundle |
| `patient_id` | chuỗi | Không | Bắt buộc nếu nguồn không chứa định danh ánh xạ được |
| `format` | `auto`, `pdf`, `fhir_r4` | Không | Mặc định `auto`; máy chủ vẫn kiểm tra byte và MIME |

Trả `202`:

```json
{
  "batch_id": "ing_01J5ZB",
  "status": "received",
  "format": "pdf",
  "source_document_id": "doc_01J5ZC",
  "source_checksum": "sha256:...",
  "received_at": "2026-08-20T08:15:00+07:00",
  "counts": {
    "accepted": 0,
    "quarantined": 0,
    "needs_verification": 0
  },
  "errors": []
}
```

Trạng thái batch: `received`, `validating`, `processing`, `completed`, `completed_with_warnings`, `failed`.

#### `GET /ingestions/{batch_id}`

Quyền: `ingestion.read`. Trả cùng cấu trúc batch, bổ sung:

```json
{
  "completed_at": "2026-08-20T08:16:00+07:00",
  "data_watermark": "wm_01J5ZD",
  "counts": {
    "accepted": 126,
    "quarantined": 2,
    "needs_verification": 3
  },
  "errors": [
    {
      "code": "OCR_LOW_CONFIDENCE",
      "message": "Có ba vùng cần bác sĩ xác minh.",
      "item_id": "ver_01J5ZE"
    }
  ]
}
```

#### `POST /patients/{patient_id}/process`

Quyền: `patient.process`.

```json
{
  "profile_versions": ["type_2_diabetes@1.0.0", "ckd@1.0.0"]
}
```

Trả `202` với `process_id`, `status` và `data_watermark`. Gửi lại cùng bệnh nhân và watermark không tạo dữ liệu dẫn xuất trùng lặp.

### 4.5. Xác minh OCR

#### `GET /patients/{patient_id}/verification-items`

Quyền: `clinical.read`. Tham số `status=pending|verified|dismissed`, `page`, `page_size`.

```json
{
  "items": [
    {
      "verification_item_id": "ver_01J5ZE",
      "document_id": "doc_01J5ZC",
      "page_number": 2,
      "block_id": "block_17",
      "bbox": [112.4, 281.0, 463.8, 318.2],
      "extracted_text": "HbA1c 8.7 %",
      "corrected_text": null,
      "confidence": 0.71,
      "status": "pending",
      "engine": "paddleocr",
      "engine_version": "3.0.0"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

#### `PATCH /verification-items/{verification_item_id}`

Quyền: `clinical.verify`.

```json
{
  "decision": "verified",
  "corrected_text": "HbA1c 8,7%",
  "expected_version": 1
}
```

`decision` nhận `verified` hoặc `dismissed`. Trả item đã cập nhật và watermark mới. Watermark mới làm các review hiện hành chuyển sang `stale`.

#### `GET /documents/{document_id}/pages/{page_number}`

Quyền: `clinical.read`. Trả `image/png` mặc định. Có thể dùng `Accept: application/json` để lấy metadata block:

```json
{
  "document_id": "doc_01J5ZC",
  "page_number": 2,
  "image_url": "/api/v1/documents/doc_01J5ZC/pages/2?representation=image",
  "width": 2480,
  "height": 3508,
  "blocks": []
}
```

Máy chủ kiểm tra bệnh nhân từ quan hệ của `document_id`; client không gửi `patient_id` thay thế.

### 4.6. Dữ liệu lâm sàng tương tác

#### `GET /patients/{patient_id}/timeline`

Tham số: `date_from`, `date_to`, `event_type`, `page`, `page_size`.

```json
{
  "items": [],
  "data_watermark": "wm_01J5ZD",
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

#### `GET /patients/{patient_id}/trends`

Tham số bắt buộc `code`; tùy chọn `date_from`, `date_to`.

```json
{
  "code": "4548-4",
  "display": "HbA1c",
  "unit": "%",
  "points": [],
  "profile_version": "type_2_diabetes@1.0.0",
  "data_watermark": "wm_01J5ZD"
}
```

#### `GET /patients/{patient_id}/drug-interactions`

Tham số `status`. Trả `items: DrugInteractionFlag[]` và `data_watermark`.

### 4.7. Tạo và đọc bản rà soát

#### `POST /patients/{patient_id}/reviews/generate`

Quyền: `review.generate`.

```json
{
  "profile_versions": ["type_2_diabetes@1.0.0", "ckd@1.0.0"],
  "language": "vi"
}
```

Trả `201 ReviewResponse`. Tác vụ MVP có thể chạy đồng bộ; nếu chuyển sang nền, phải trả `202` cùng `operation_id`, không tự thay đổi hình dạng `ReviewResponse`.

#### `GET /patients/{patient_id}/review`

Quyền: `review.read`. Không có tham số thì trả phiên bản hiện tại. Có thể dùng `?version=3` hoặc `?review_version_id=rv_...`.

Nếu chưa có review, trả `404 RESOURCE_NOT_FOUND`.

### 4.8. Hỏi hồ sơ bệnh án

#### `POST /patients/{patient_id}/ask`

Quyền: `ask.create`.

```json
{
  "question": "HbA1c thay đổi như thế nào trong sáu tháng gần đây?",
  "lookback": {
    "value": 6,
    "unit": "month"
  }
}
```

Trả `200`:

```json
{
  "status": "answered",
  "answer": "HbA1c tăng từ 7,5% lên 8,7% trong dữ liệu được cung cấp.",
  "confidence": "high",
  "citations": [],
  "data_watermark": "wm_01J5ZD"
}
```

`status` nhận `answered`, `not_found`, `conflicting`, `not_allowed`. Khi không đủ bằng chứng, `answer` phải nói rõ không tìm thấy hoặc không thể kết luận; không trả lỗi HTTP chỉ vì không tìm thấy câu trả lời.

### 4.9. Bằng chứng và phản hồi

#### `GET /claims/{claim_id}/evidence`

Quyền: `evidence.read`.

```json
{
  "claim_id": "clm_01J5ZF",
  "claim_text": "HbA1c tăng từ 7,5% lên 8,7%.",
  "claim_status": "verified",
  "evidence": []
}
```

#### `POST /claims/{claim_id}/feedback`

Quyền: `feedback.create`.

```json
{
  "rating": "incorrect",
  "comment": "Ngày của kết quả đầu tiên chưa đúng."
}
```

`rating`: `correct`, `incorrect`, `irrelevant`. Trả `201` với `feedback_id`, `created_at`. Phản hồi là tín hiệu đánh giá, không tự động huấn luyện mô hình.

### 4.10. Chỉnh sửa và vòng đời rà soát

#### `PATCH /reviews/{review_id}`

Quyền: `review.edit`.

```json
{
  "expected_version": 1,
  "sections": [
    {
      "section_code": "changes_to_review",
      "clinician_text": "Nội dung đã được bác sĩ hiệu chỉnh."
    }
  ],
  "edit_reason": "Làm rõ diễn biến xét nghiệm"
}
```

Trả `200 ReviewResponse` với `version` tăng một và `review_version_id` mới. Phiên bản cũ bất biến.

#### `POST /reviews/{review_id}/approve`

Quyền: `review.approve`.

```json
{
  "review_version_id": "rv_01J5ZG",
  "expected_version": 2,
  "clinician_confirmation": true
}
```

Trả `200 ReviewResponse` có `status=approved`. Trong cùng giao dịch, máy chủ:

1. Khóa logic bản rà soát.
2. Kiểm tra quyền và phạm vi bệnh nhân.
3. Kiểm tra phiên bản và watermark.
4. Kiểm tra xác nhận và bằng chứng.
5. Ghi phê duyệt bất biến.
6. Tạo phiên bản bộ nhớ bệnh nhân.
7. Ghi sự kiện kiểm toán.

#### `POST /reviews/{review_id}/reject`

```json
{
  "review_version_id": "rv_01J5ZG",
  "expected_version": 2,
  "reason": "Bằng chứng chưa đủ rõ."
}
```

`reason` bắt buộc, dài từ 3 đến 1000 ký tự. Trả `200 ReviewResponse` có `status=rejected`; không tạo bộ nhớ hoặc PDF.

#### `GET /reviews/{review_id}/versions`

Trả danh sách:

```json
{
  "items": [
    {
      "review_version_id": "rv_01J5ZG",
      "version": 2,
      "author_id": "usr_01J5ZH",
      "status": "approved",
      "created_at": "2026-08-20T08:30:00+07:00",
      "checksum": "sha256:..."
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

### 4.11. Bộ nhớ bệnh nhân

#### `GET /patients/{patient_id}/memory`

Quyền: `memory.read`. Tham số tùy chọn `version`.

```json
{
  "memory_version_id": "memv_01J5ZJ",
  "version": 3,
  "patient_id": "pat_01J5Z9",
  "source_review_version_id": "rv_01J5ZG",
  "items": [
    {
      "item_id": "mem_01J5ZK",
      "category": "current_medication",
      "text": "Metformin 1.000 mg theo hồ sơ đã duyệt.",
      "citations": []
    }
  ],
  "approved_by": "usr_01J5ZH",
  "approved_at": "2026-08-20T08:30:00+07:00"
}
```

Không có memory đã duyệt trả `404`. Không lấy bản nháp làm ngữ cảnh memory.

### 4.12. Xuất PDF

#### `GET /reviews/{review_id}/export.pdf?review_version_id={id}`

Quyền: `review.export`. Header `Idempotency-Key` được khuyến nghị.

Điều kiện: phiên bản yêu cầu phải `approved`, đúng review và chưa `stale`. Máy chủ tự dựng nội dung; client không gửi HTML hoặc nội dung PDF.

Trả `200 application/pdf` cùng các header:

```text
Content-Disposition: attachment; filename="clinical-review-20260820.pdf"
X-Content-Checksum: sha256:...
X-Review-Version-ID: rv_01J5ZG
```

Tên tệp không chứa tên hoặc mã định danh nhạy cảm của bệnh nhân.

### 4.13. Nhật ký kiểm toán

#### `GET /admin/audit-logs`

Quyền: `audit.read`.

Tham số: `date_from`, `date_to`, `actor_id`, `action`, `outcome`, `patient_ref`, `page`, `page_size`.

```json
{
  "items": [
    {
      "audit_id": "aud_01J5ZM",
      "actor_id": "usr_01J5ZH",
      "action": "review.approve",
      "patient_ref": "ptref_7a91",
      "resource_type": "review",
      "resource_id": "rev_01J5ZN",
      "outcome": "success",
      "timestamp": "2026-08-20T08:30:00+07:00",
      "request_id": "req_01J5Z8K",
      "metadata": {}
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

Không trả raw PHI, raw prompt, nội dung PDF, cookie, token hoặc khóa API. Việc xem audit cũng phải tạo audit event.

## 5. Hợp đồng nội bộ giữa Máy chủ và AI

Đây là ranh giới để thành viên 1 và thành viên 2 làm độc lập. AI không được tự truy vấn cơ sở dữ liệu và không nhận tenant hoặc patient từ văn bản do mô hình tạo.

### 5.1. Yêu cầu tạo review

```ts
type AgentRequest = {
  request_id: string;
  task_type: "review_generation" | "ask_chart";
  tenant_id: string;               // do máy chủ gắn, không do client tự quyết
  patient_id: string;              // đã kiểm tra scope
  user_id: string;
  data_watermark: string;
  profile_versions: string[];
  approved_memory: object | null;
  structured_facts: object[];
  note_evidence: EvidenceItem[];
  question?: string;
};

type EvidenceItem = {
  evidence_id: string;
  fact_type: string;
  normalized_value: unknown;
  source_value: unknown;
  source_time: string | null;
  verification_status: "verified" | "needs_verification";
  citations: Citation[];
};
```

Máy chủ chỉ đưa `needs_verification` vào gói bằng chứng để hiển thị cảnh báo hoặc mâu thuẫn; không đưa vào danh sách fact đã xác minh.

### 5.2. Kết quả AI

```ts
type AgentResult = {
  task_type: "review_generation" | "ask_chart";
  status: "answered" | "not_found" | "conflicting" | "not_allowed" | "error";
  data_watermark: string;
  sections?: ReviewSection[];
  answer?: string;
  confidence?: "high" | "medium" | "low" | null;
  claims: VerifiedClaim[];
  citations: Citation[];
  errors: Array<{ code: string; message: string }>;
};
```

Điều kiện nghiệm thu giao diện nội bộ:

- `AgentResult.data_watermark` phải bằng watermark của yêu cầu.
- Mỗi claim `verified` có citation hợp lệ thuộc đúng patient.
- Trạng thái `unsupported` hoặc `invalid` không xuất hiện trong phần factual công khai.
- `ask_chart` không tạo review, memory hoặc PDF.
- Kết quả công khai không chứa prompt, trace, tên tool hoặc nội dung suy luận nội bộ.

## 6. Ma trận endpoint và người phụ trách

| Nhóm API | Thành viên triển khai | Thành viên cung cấp dữ liệu/logic | Thành viên sử dụng |
|---|---|---|---|
| Xác thực, bệnh nhân | 1 | 1 | 3 |
| Tiếp nhận, xử lý, OCR | 1 | 1 | 3 |
| Timeline, trends, tương tác thuốc | 1 | 1; thành viên 2 kiểm tra logic lâm sàng | 3 |
| Tạo review | 1 | 2 qua `AgentRequest/AgentResult` | 3 |
| Ask the Chart | 1 định tuyến HTTP | 2 | 3 |
| Evidence và citation | 1 cấp nguồn | 2 kiểm chứng | 3 hiển thị |
| Edit, approve, reject, version | 1 | 2 kiểm tra trạng thái bằng chứng | 3 |
| Memory | 1 lưu projection | 2 định nghĩa whitelist/chính sách | 3 |
| PDF và audit | 1 tạo dữ liệu/API | 2 kiểm safety fields | 3 giao diện/triển khai |

## 7. Mock để ba người làm song song

Thành viên 3 có thể dựng Mock Service Worker hoặc mock route từ schema trong tài liệu và ID/case của `data/demo_mvp_v1/`; không tạo một tập bệnh nhân song song. Quy ước độ trễ giả lập:

| API | Độ trễ mock | Trường hợp cần mô phỏng |
|---|---:|---|
| Đọc danh sách/timeline/trend | 100–300 ms | rỗng, thành công, 401, 404 |
| Generate review | 800–1500 ms | thành công, 503, review có `needs_verification` |
| Ask | 500–1200 ms | đủ bốn trạng thái trả lời |
| Edit | 200–400 ms | thành công và `409 VERSION_CONFLICT` |
| Approve | 300–600 ms | thành công, stale, thiếu xác nhận, thiếu bằng chứng |
| Export PDF | 300–800 ms | thành công và `EXPORT_NOT_ALLOWED` |

Thành viên 1 tạo kiểm thử hợp đồng từ cùng schema. Thành viên 2 tạo fixture `AgentRequest` và snapshot `AgentResult`, không cần chạy HTTP hoặc cơ sở dữ liệu khi phát triển graph.

## 8. Các luồng nghiệm thu bắt buộc

### 8.1. Luồng thành công toàn phần

```text
Đăng nhập
→ lấy danh sách bệnh nhân
→ nhập PDF/FHIR
→ theo dõi ingestion
→ xác minh OCR nếu có
→ xử lý bệnh nhân
→ tạo review
→ mở citation đúng trang/vùng
→ chỉnh sửa với expected_version
→ xác nhận và duyệt
→ đọc memory mới
→ xuất đúng PDF đã duyệt
→ xem audit
```

### 8.2. Luồng an toàn

1. Truy cập dữ liệu bệnh nhân khác trả 404 và không lộ resource.
2. Claim không citation không thể được duyệt.
3. OCR confidence thấp không trở thành fact trước xác minh.
4. Hai client cùng sửa: client thứ hai nhận `409 VERSION_CONFLICT`.
5. Có dữ liệu nguồn mới: review cũ chuyển `stale`, approve/export trả `409 REVIEW_STALE`.
6. Reject không tạo memory hoặc PDF.
7. Ask không đủ bằng chứng trả `not_found` hoặc `conflicting`, không bịa câu trả lời.
8. Memory và PDF tham chiếu đúng `source_review_version_id` đã duyệt.
9. Mọi lần xem PHI, evidence, hỏi, sửa, duyệt, từ chối và xuất đều có audit.

## 9. Quy tắc thay đổi hợp đồng

1. Không đổi tên trường hoặc endpoint đã chốt trực tiếp trong mã mà không cập nhật file này.
2. Thêm trường không bắt buộc là thay đổi tương thích; client phải bỏ qua trường chưa biết.
3. Xóa trường, đổi kiểu, đổi ý nghĩa hoặc thêm giá trị enum có thể phá client phải tăng phiên bản hợp đồng.
4. Backend xuất OpenAPI từ FastAPI; giao diện sinh TypeScript type từ OpenAPI hoặc kiểm tra type tương đương.
5. Kiểm thử CI tối thiểu gồm: schema thành công, schema lỗi, quyền, patient isolation, phiên bản xung đột, stale guard, approved-only memory/PDF và citation bắt buộc.
6. Khi tài liệu khác mâu thuẫn với file này về API, file này là nguồn sự thật cho triển khai; thay đổi thiết kế phải sửa hợp đồng trước.
