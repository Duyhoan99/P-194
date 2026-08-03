# Clinical Retrieval Backend — Design Spec

**Ngày:** 2026-08-03  
**Trạng thái:** Đã được xác nhận để lập kế hoạch triển khai  
**Phạm vi:** MVP backend, nhóm tool 1

## 1. Mục tiêu

Xây dựng lớp backend truy xuất bằng chứng lâm sàng có cấu trúc từ `mimic_demo.db`, phục vụ bác sĩ xem hồ sơ đã khử định danh. Mọi bản ghi phải truy nguyên được về bảng và khóa nguồn MIMIC-IV 3.1. Backend chỉ cung cấp bằng chứng; không tạo chẩn đoán, khuyến nghị điều trị, tóm tắt AI hay quyết định lâm sàng.

MVP bao phủ:

- bệnh nhân, lần nhập viện, chuyển khoa và dịch vụ;
- timeline encounter và ICU stay;
- chẩn đoán và thủ thuật được mã hóa;
- xét nghiệm và metadata từ điển xét nghiệm;
- vi sinh;
- sự kiện ICU: chart, datetime, input, output và procedure events.

## 2. Quyết định thiết kế

### 2.1. Kiến trúc retrieval theo miền nghiệp vụ

API và LangChain/LangGraph tools cùng gọi một `ClinicalRetrievalService`. Service gọi repository qua interface; SQL chỉ tồn tại trong repository, được tham số hóa và giới hạn bởi allow-list bảng/cột.

```text
HTTP request / LangGraph tool
          |
          v
AccessContext + assignment check
          |
          v
ClinicalRetrievalService
          |
          v
ClinicalRepository protocol
          |
          v
SQLite adapter (mimic_demo.db) -> PostgreSQL adapter sau này
```

Không chọn tool bám trực tiếp từng bảng vì sẽ lặp logic join và dễ làm mất citation. Không cho LLM sinh SQL vì không thể bảo đảm giới hạn bệnh nhân, bảng và trường trong môi trường lâm sàng.

### 2.2. Database adapter

MVP dùng SQLite adapter đọc file được cấu hình bằng environment variable. Service không phụ thuộc SQLite; adapter PostgreSQL có thể thay thế mà không đổi schema trả về, tool hoặc API. Không đưa CSV/CSV.GZ MIMIC thô, credential hoặc restricted excerpt vào repository.

### 2.3. Phân quyền fail-closed

Mọi truy vấn clinical yêu cầu `AccessContext` được tạo từ authentication middleware:

```text
user_id: str
role: DOCTOR | ADMIN
assigned_subject_ids: set[int]
trace_id: str
```

`subject_id` là bắt buộc. `hadm_id` và `stay_id`, nếu được truyền, phải thuộc đúng `subject_id`. Nếu user không được phân công, trả `403` và ghi audit event trước khi truy vấn dữ liệu.

Development/test có thể dùng `DemoAssignmentProvider` hoặc dependency override. Provider này phải bị vô hiệu hóa khi `APP_ENV=production`; không tin một user ID do client tự gửi để mở quyền.

## 3. Các module backend

```text
src/clinical/
├── access.py       # AccessContext, assignment checker
├── repository.py   # repository protocol và SQLite implementation
├── service.py      # retrieval theo miền nghiệp vụ
├── schemas.py      # request/response và lineage models
├── errors.py       # domain errors, HTTP mapping
└── availability.py # trạng thái bảng/module nguồn

src/agents/tools/clinical_tools.py
src/api/clinical_routes.py
```

`ClinicalRepository` chỉ trả các trường allow-list cần cho từng domain. `ClinicalRetrievalService` chịu trách nhiệm kiểm tra scope, giới hạn kết quả, sắp xếp, đóng gói lineage và phát cảnh báo `PARTIAL`/`NOT_LOADED`; repository không tự quyết định quyền người dùng.

## 4. Công cụ và API

Sáu tool dùng chung các tham số:

```text
subject_id: int, bắt buộc
hadm_id: int | null
stay_id: int | null
from_time: datetime | null
to_time: datetime | null
limit: int, mặc định 200, tối đa 1000
access_context: bắt buộc ở service boundary
```

| Tool | Nguồn chính | Mục đích |
|---|---|---|
| `get_patient_overview` | `patients`, `admissions` | demographic đã khử định danh, số lần nhập viện, encounter chính |
| `get_encounter_timeline` | `admissions`, `transfers`, `services`, `icustays` | các mốc nhập viện, chuyển khoa, dịch vụ và ICU |
| `get_diagnoses_and_procedures` | `diagnoses_icd`, `d_icd_diagnoses`, `procedures_icd`, `d_icd_procedures`, `hcpcsevents`, `d_hcpcs`, `procedureevents` | mã và mô tả nguồn, không diễn giải thành chẩn đoán mới |
| `get_laboratory_results` | `labevents`, `d_labitems` | label, itemid, value, numeric value, unit, reference range, flag, charttime |
| `get_microbiology_results` | `microbiologyevents` | specimen, test, organism, susceptibility và thời gian khi có |
| `get_icu_events` | `chartevents`, `datetimeevents`, `inputevents`, `outputevents`, `procedureevents`, `d_items`, `icustays` | sự kiện ICU có stay scope và metadata item |

REST routes tương ứng:

```text
GET /api/v1/clinical/patients/{subject_id}
GET /api/v1/clinical/patients/{subject_id}/timeline
GET /api/v1/clinical/patients/{subject_id}/diagnoses-procedures
GET /api/v1/clinical/patients/{subject_id}/labs
GET /api/v1/clinical/patients/{subject_id}/microbiology
GET /api/v1/clinical/patients/{subject_id}/icu-events
```

Endpoint không nhận SQL, tên bảng, tên cột hoặc điều kiện tùy ý từ client. Bộ lọc được giới hạn theo schema Pydantic; `limit` và khoảng thời gian được kiểm tra ở API và service.

## 5. Hợp đồng response và lineage

Response domain thống nhất:

```json
{
  "status": "SUCCESS",
  "records": [],
  "warnings": [],
  "limitations": [],
  "trace_id": "..."
}
```

`status` có thể là `SUCCESS`, `PARTIAL`, `EMPTY`, `DENIED` hoặc `NOT_LOADED`. Mỗi record có dạng:

```json
{
  "type": "lab",
  "data": {},
  "lineage": {
    "dataset": "MIMIC-IV",
    "version": "3.1",
    "module": "hosp",
    "table": "labevents",
    "source_row_key": "labevent_id=123",
    "subject_id": 1001,
    "hadm_id": 2001,
    "stay_id": null,
    "event_time": "2125-01-01T10:00:00"
  }
}
```

Lineage phải giữ nguyên `subject_id`, `hadm_id`/`stay_id` khi có, khóa bản ghi nguồn, module, bảng, version và thời gian. Với lab, `data` phải giữ nguyên giá trị, giá trị số, đơn vị, reference range, label, itemid và flag. Không tự đổi đơn vị hoặc bù khóa bị thiếu. Khi nhiều bảng hỗ trợ một record, lineage phải có nhiều source references thay vì làm mất nguồn phụ.

Các record không được phép trả trường nhận diện cá nhân ngoài phạm vi MIMIC đã khử định danh và allow-list của domain.

## 6. Trạng thái dữ liệu và lỗi

| Điều kiện | Kết quả |
|---|---|
| Phiên không hợp lệ | HTTP `401` |
| Không được phân công bệnh nhân | HTTP `403` + audit event |
| Bệnh nhân không tồn tại trong cohort được phép | HTTP `404` |
| Scope hoặc filter không hợp lệ | HTTP `422` |
| Bảng/module không khả dụng | `NOT_LOADED` hoặc `PARTIAL` |
| Database lỗi | HTTP `503` |
| Query timeout | HTTP `504` |
| Không có bản ghi phù hợp | `EMPTY`, không tạo dữ liệu thay thế |
| Citation/source row không còn truy cập được | warning rõ ràng, không giả lập lineage |

Lỗi client không trả SQL, stack trace, prompt hoặc raw clinical data. Audit event lưu `user_id`, action, subject/hadm/stay scope, timestamp, result và `trace_id`; không lưu giá trị xét nghiệm hoặc nội dung prompt. Mỗi lần truy xuất thành công, bị từ chối hoặc lỗi quyền đều phải có audit event phù hợp.

## 7. Kiểm thử và tiêu chí nghiệm thu

### 7.1. Unit/integration tests

- access được phép và access bị từ chối;
- isolation giữa các `subject_id`, `hadm_id` và `stay_id`;
- lineage đúng bảng, khóa dòng, thời gian, value và unit;
- giữ nguyên `NULL`, không tự suy diễn khóa hoặc giá trị;
- timeline sắp xếp theo thời gian nguồn;
- lọc thời gian, giới hạn và phân trang;
- `EMPTY`, `PARTIAL` và `NOT_LOADED`;
- chỉ trả trường thuộc allow-list;
- input không thể thực thi SQL tùy ý;
- database error/timeout không làm lộ dữ liệu;
- route trả đúng HTTP status và correlation/trace ID.

### 7.2. Acceptance criteria

- Không có truy cập trái phép thành công trong test.
- 100% record test có lineage hợp lệ.
- Giá trị xét nghiệm, đơn vị và thời gian trùng dữ liệu nguồn.
- Không có chẩn đoán hoặc sự kiện được tạo thêm bởi tool.
- Truy vấn dashboard thông thường trên `mimic_demo.db` đạt mục tiêu dưới 2 giây sau khi có index phù hợp.
- Không có dữ liệu MIMIC thô, credential hoặc restricted excerpt mới được thêm vào Git/AI log.

## 8. Ngoài phạm vi vòng này

Không triển khai trong design/implementation này:

- giao diện Next.js;
- authentication production đầy đủ;
- sinh clinical summary bằng LLM;
- citation validator cho claim;
- thuốc, drug interaction, PDF, review/approval;
- MIMIC-IV-Note, MIMIC-IV-ED, vector search;
- ingest CSV.GZ mới hoặc migration PostgreSQL production.

Các phần trên chỉ được nối sau khi retrieval backend đạt bộ test access, lineage và numeric integrity.

