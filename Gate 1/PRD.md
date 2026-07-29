# 1. Thông tin sản phẩm

Tên sản phẩm: AI Agent hỗ trợ tóm tắt hồ sơ lâm sàng đa nguồn cho bác sĩ

Phiên bản tài liệu: 1.0

Giai đoạn: Thiết kế và xây dựng MVP

Người dùng chính: Bác sĩ điều trị

Dữ liệu: Hồ sơ đã khử định danh hoặc mô phỏng theo JSON/FHIR-like

# 2. Tổng quan

## 2.1. Bài toán

Hồ sơ bệnh nhân có thể trải dài qua nhiều lần khám, nhập viện, kết quả xét nghiệm, chẩn đoán hình ảnh, đơn thuốc và ghi chú lâm sàng. Bác sĩ phải đọc và đối chiếu thủ công trước mỗi lượt khám, dẫn đến mất thời gian và có nguy cơ bỏ sót thông tin.

## 2.2. Mục tiêu sản phẩm

Giảm tối thiểu 50% thời gian đọc lại hồ sơ cũ trong thử nghiệm.

Tạo tóm tắt lâm sàng có cấu trúc và có thể truy nguồn.

Phát hiện dữ liệu thiếu, mâu thuẫn và các cảnh báo thuốc dựa trên tool.

Buộc bác sĩ rà soát và phê duyệt trước khi sử dụng kết quả.

Không để AI tạo chẩn đoán hoặc điều trị mới.

## 2.3. Nguyên tắc thiết kế

Evidence first: truy xuất và chuẩn hóa bằng chứng trước khi sinh nội dung.

Claim-level citation: citation gắn với từng nhận định, không chỉ cuối đoạn.

Human authority: bác sĩ là người quyết định cuối cùng.

Least privilege: chỉ truy cập dữ liệu cần thiết và được phân quyền.

Uncertainty visible: dữ liệu thiếu hoặc mâu thuẫn phải được hiển thị rõ.

Auditability: mọi truy cập và thay đổi quan trọng phải có log.

# 3. Phạm vi sản phẩm

## 3.1. In Scope — MVP

Đăng nhập và phân quyền Bác sĩ/Quản trị viên.

Danh sách bệnh nhân được phân công.

Nhập hoặc chọn hồ sơ mô phỏng.

Truy xuất encounter, diagnosis, laboratory, medication và clinical note.

Sinh tóm tắt lâm sàng có cấu trúc.

Gắn citation cho mọi claim lâm sàng.

Panel nguồn hiển thị đúng bản ghi/tài liệu hỗ trợ.

Đánh dấu dữ liệu thiếu, bất nhất hoặc không đủ bằng chứng.

Bác sĩ chỉnh sửa, yêu cầu tạo lại, từ chối hoặc phê duyệt.

Lưu phiên bản và audit log.

Xuất PDF cho bản đã được phê duyệt.

## 3.2. Advanced Scope

Timeline tương tác.

Biểu đồ xu hướng xét nghiệm.

Kiểm tra tương tác thuốc qua cơ sở tri thức chuyên biệt.

Phát hiện mâu thuẫn tự động giữa các nguồn.

Memory theo bệnh nhân dưới dạng trạng thái đã kiểm chứng.

So sánh phiên bản tóm tắt giữa các lần khám.

Dashboard quản trị và giám sát chất lượng agent.

## 3.3. Out of Scope

Tự chẩn đoán bệnh mới.

Đề xuất hoặc thay đổi điều trị.

Kê đơn thuốc.

Tư vấn trực tiếp cho bệnh nhân.

Tự động ghi đè hồ sơ EHR chính thức.

LLM tự suy đoán tương tác thuốc.

Sử dụng dữ liệu bệnh nhân thật trong phiên bản demo.

Kết luận nguồn nào đúng khi dữ liệu mâu thuẫn mà không có bác sĩ xác nhận.

# 4. Người dùng và quyền hạn

## 4.1. Bác sĩ điều trị

Mục tiêu

Hiểu nhanh diễn biến bệnh nhân.

Kiểm tra nguồn của từng nhận định.

Xác định xu hướng và thông tin bất nhất.

Chỉnh sửa và phê duyệt bản tóm tắt.

Quyền

Chỉ xem bệnh nhân được phân công.

Tạo và rà soát bản tóm tắt.

Xem tài liệu nguồn.

Chỉnh sửa, từ chối và phê duyệt.

Xuất PDF bản đã duyệt.

## 4.2. Quản trị viên

Mục tiêu

Quản lý tài khoản và vai trò.

Phân công bác sĩ với bệnh nhân.

Xem audit log và trạng thái hệ thống.

Giới hạn

Không được chỉnh sửa nội dung lâm sàng thay cho bác sĩ, trừ khi đồng thời có vai trò bác sĩ hợp lệ.

# 5. User Stories

ID

User story

Ưu tiên

### US-01

Là bác sĩ, tôi muốn xem danh sách bệnh nhân được phân công để không truy cập nhầm hồ sơ.

Must

### US-02

Là bác sĩ, tôi muốn sinh tóm tắt từ nhiều nguồn để giảm thời gian đọc hồ sơ.

Must

### US-03

Là bác sĩ, tôi muốn bấm citation để xem đúng bằng chứng nguồn.

Must

### US-04

Là bác sĩ, tôi muốn thấy dữ liệu thiếu hoặc mâu thuẫn để không hiểu nhầm kết quả.

Must

### US-05

Là bác sĩ, tôi muốn chỉnh sửa và duyệt trước khi lưu hoặc xuất PDF.

Must

### US-06

Là bác sĩ, tôi muốn xem xu hướng xét nghiệm theo thời gian.

Should

### US-07

Là bác sĩ, tôi muốn xem cảnh báo tương tác thuốc có nguồn từ tool.

Should

### US-08

Là quản trị viên, tôi muốn quản lý người dùng và phân quyền bệnh nhân.

Must

### US-09

Là quản trị viên, tôi muốn xem audit log truy cập hồ sơ.

Must

### US-10

Là bác sĩ, tôi muốn xem lịch sử phiên bản và biết ai đã thay đổi nội dung.

Should

# 6. Yêu cầu chức năng

### FR-01 — Authentication

Hệ thống cho phép đăng nhập bằng tài khoản hợp lệ.

Hỗ trợ vai trò DOCTOR và ADMIN.

Session hết hạn sau thời gian không hoạt động.

Đăng nhập thất bại nhiều lần phải được ghi log và có thể khóa tạm thời.

### FR-02 — Authorization

Bác sĩ chỉ được xem bệnh nhân được phân công.

API phải xác minh quyền ở phía server, không chỉ dựa trên giao diện.

Yêu cầu trái phép trả về 403 Forbidden và tạo audit event.

### FR-03 — Patient Workspace

Hiển thị thông tin định danh mô phỏng, encounter gần nhất và trạng thái tóm tắt.

Cho phép chuyển giữa Summary, Timeline, Medications, Lab Trends, Documents và Review History.

### FR-04 — Data Ingestion

Nhận dữ liệu JSON/FHIR-like hoặc dữ liệu đã chuẩn hóa từ pipeline.

Mỗi bản ghi phải có source_id, source_type, thời gian và encounter liên quan.

Dữ liệu lỗi schema phải bị từ chối và ghi lý do.

### FR-05 — Retrieval

Agent phải truy xuất tối thiểu:

Encounter và timeline.

Chẩn đoán/bệnh nền.

Kết quả xét nghiệm.

Thuốc kê, thuốc đã dùng và thuốc lúc xuất viện nếu có.

Clinical notes và radiology reports liên quan.

### FR-06 — Structured Clinical Summary

Bản tóm tắt gồm:

Clinical Overview.

Active Problems.

Past Medical History.

Current and Recent Medications.

Key Timeline.

Laboratory Trends.

Imaging and Procedures.

Conflicts and Missing Information.

Safety Alerts.

Limitations.

### FR-07 — Claim-Level Citation

Mỗi câu chứa dữ kiện lâm sàng phải có ít nhất một citation.

Citation trỏ tới bản ghi hoặc đoạn tài liệu cụ thể.

Citation phải chứa source ID, loại nguồn, thời gian và excerpt/value hỗ trợ.

Không được tạo claim nếu validator không tìm thấy bằng chứng.

### FR-08 — Source Viewer

Khi bác sĩ chọn citation, hệ thống hiển thị:

Tên/loại tài liệu.

Ngày giờ.

Encounter ID.

Bản ghi hoặc đoạn văn gốc được highlight.

Giá trị, đơn vị và reference range với xét nghiệm.

Liên kết quay lại claim tương ứng.

### FR-09 — Numeric Integrity

Giá trị, đơn vị và thời điểm phải giữ nguyên từ nguồn.

Không tự quy đổi đơn vị nếu không có quy tắc chuẩn hóa được kiểm chứng.

Khi hai nguồn dùng đơn vị khác nhau, hệ thống phải hiển thị cảnh báo.

### FR-10 — Conflict Detection

Phát hiện các nhận định không nhất quán giữa hai hoặc nhiều nguồn.

Hiển thị song song các bằng chứng.

Không tự chọn nguồn đúng khi chưa có quy tắc xác định.

Cho phép bác sĩ đánh dấu RESOLVED hoặc UNRESOLVED và ghi chú.

### FR-11 — Medication Status

Hệ thống phải phân biệt:

REPORTED_HOME_MEDICATION

PRESCRIBED

ADMINISTERED

DISCONTINUED

DISCHARGE_MEDICATION

UNKNOWN_STATUS

Không được gom mọi bản ghi thành “thuốc đang dùng”.

### FR-12 — Drug Interaction Tool

Tên thuốc phải được chuẩn hóa trước khi gọi tool.

Cảnh báo chỉ được sinh từ kết quả tool có version/provenance.

LLM chỉ diễn giải, không tự suy đoán tương tác.

Khi tool không khả dụng, hiển thị “Chưa kiểm tra được tương tác thuốc”.

### FR-13 — Human Review

Bản do agent tạo có trạng thái DRAFT.

Bác sĩ có thể chỉnh sửa, thêm nhận xét hoặc yêu cầu tạo lại.

Hệ thống lưu riêng bản AI ban đầu và bản bác sĩ chỉnh sửa.

### FR-14 — Approval

Trước khi phê duyệt, bác sĩ phải xác nhận:

Đã rà soát bản tóm tắt.

Đã kiểm tra các nguồn quan trọng.

Hiểu rằng nội dung AI chỉ mang tính hỗ trợ.

Chỉ bác sĩ được phân quyền mới có thể phê duyệt.

### FR-15 — Versioning

Mỗi phiên bản lưu:

version_id

summary_id

Người tạo/chỉnh sửa

Thời gian

Nội dung thay đổi

Trạng thái

Lý do từ chối hoặc tạo lại

### FR-16 — PDF Export

Chỉ bản APPROVED mới được xuất bản giao chính thức.

PDF phải có disclaimer, thời gian tạo, người duyệt và danh sách nguồn.

Bản chưa duyệt chỉ được xuất với watermark DRAFT.

### FR-17 — Audit Log

Ghi tối thiểu:

Đăng nhập/đăng xuất.

Xem hồ sơ bệnh nhân.

Tạo tóm tắt.

Mở nguồn.

Chỉnh sửa.

Từ chối/phê duyệt.

Xuất PDF.

Thay đổi phân quyền.

# 7. Vòng đời bản tóm tắt

PROCESSING
   ↓
DRAFT
   ↓
UNDER_REVIEW
   ├──→ REVISION_REQUIRED ──→ PROCESSING
   └──→ APPROVED ──→ EXPORTED

Quy tắc

PROCESSING: agent đang thực thi.

DRAFT: đã tạo nhưng chưa được bác sĩ rà soát.

UNDER_REVIEW: bác sĩ đang kiểm tra/chỉnh sửa.

REVISION_REQUIRED: bị từ chối hoặc yêu cầu sinh lại.

APPROVED: đã được bác sĩ xác nhận.

EXPORTED: bản được xuất PDF.

# 8. Agent Workflow

## 8.1. LangGraph nodes

authorize_access
→ plan_retrieval
→ retrieve_structured_data
→ retrieve_clinical_notes
→ normalize_events
→ reconcile_sources
→ check_medications
→ generate_claims
→ validate_claims
→ attach_citations
→ safety_guard
→ persist_draft
→ human_review

## 8.2. Nguyên tắc thực thi

Xác minh user và quyền bệnh nhân.

Xác định câu hỏi/tác vụ tóm tắt.

Lập kế hoạch nguồn cần lấy.

Truy vấn dữ liệu cấu trúc.

Hybrid search clinical notes.

Chuẩn hóa thành clinical events.

Đối chiếu dữ liệu và phát hiện mâu thuẫn.

Sinh các claim độc lập.

Kiểm tra từng claim với evidence.

Loại bỏ hoặc hạ mức chắc chắn của claim không đủ nguồn.

Gắn citation.

Lưu bản DRAFT.

Chuyển bác sĩ rà soát.

## 8.3. Không được hiển thị

Chain-of-thought nội bộ.

Prompt hệ thống.

Thông tin kỹ thuật có thể làm lộ bí mật hoặc dữ liệu ngoài quyền truy cập.

# 9. Dữ liệu và kiến trúc

## 9.1. Nguồn dữ liệu dự kiến

MIMIC-IV: encounter, diagnosis, procedure, laboratory, medication.

MIMIC-IV-Note: discharge summary, radiology report.

MIMIC-IV-ED: triage, vital signs, ED medications.

Drug knowledge base: kiểm tra tương tác thuốc.

Có thể chuyển đổi sang mô hình JSON/FHIR-like cho demo.

## 9.2. Core entities

Entity

Trường chính

Patient

patient_id, demographics, assigned_doctors

Encounter

encounter_id, patient_id, type, start_time, end_time

ClinicalEvent

event_id, encounter_id, event_type, event_time, value, unit

ClinicalDocument

document_id, type, created_at, content, source

MedicationEvent

drug, dose, route, status, time, source

Summary

summary_id, patient_id, status, version

Claim

claim_id, text, confidence, section

Citation

citation_id, claim_id, source_id, excerpt/value

Conflict

conflict_id, sources, status, doctor_note

AuditEvent

actor, action, patient_id, timestamp, result

## 9.3. Tech stack

Agent orchestration: LangGraph.

LLM: mô hình hỗ trợ ngữ cảnh dài, cấu hình không dùng dữ liệu để huấn luyện.

RAG: vector DB kết hợp keyword/metadata search.

Backend: FastAPI.

Frontend: Next.js.

Database: PostgreSQL.

Object store: tài liệu và PDF.

Deployment: Docker; cloud hoặc môi trường nội bộ phù hợp.

Observability: trace agent, lỗi, latency và citation validation; không ghi PHI vào log công khai.

# 10. Acceptance Criteria

### AC-01 — Citation Coverage

Given bản tóm tắt đã được tạoWhen một câu chứa thông tin về bệnh, thuốc, xét nghiệm hoặc lần khámThen câu đó phải có ít nhất một citation hợp lệ.

### AC-02 — Unsupported Claim

Given không tìm thấy nguồn hỗ trợWhen agent chuẩn bị tạo nhận địnhThen agent phải bỏ nhận định hoặc ghi “Không đủ dữ liệu để kết luận”.

### AC-03 — Source Accuracy

Given bác sĩ chọn citationWhen source panel mởThen hệ thống hiển thị đúng tài liệu/bản ghi, thời gian và đoạn hỗ trợ claim.

### AC-04 — Numeric Consistency

Given claim chứa giá trị xét nghiệmWhen so sánh với nguồnThen giá trị, đơn vị và thời điểm phải trùng khớp.

### AC-05 — No New Diagnosis

Given hồ sơ không chứa chẩn đoán xác địnhWhen agent sinh tóm tắtThen agent không được trình bày chẩn đoán đó như một kết luận.

### AC-06 — HITL Required

Given bản tóm tắt chưa được bác sĩ xác nhậnWhen bác sĩ chưa hoàn thành checklist rà soátThen nút Approve phải bị vô hiệu hóa.

### AC-07 — Permission Enforcement

Given bác sĩ không được phân công bệnh nhânWhen yêu cầu mở hồ sơThen hệ thống trả về Access Denied và ghi audit event.

### AC-08 — Conflict Handling

Given có hai nguồn mâu thuẫnWhen agent tạo tóm tắtThen cả hai nguồn được hiển thị và trạng thái mặc định là UNRESOLVED.

### AC-09 — Drug Interaction Failure

Given drug interaction tool không phản hồiWhen agent hoàn tất tóm tắtThen không được bịa cảnh báo và phải hiển thị giới hạn.

### AC-10 — PDF Approval

Given summary chưa ở trạng thái APPROVEDWhen người dùng xuất PDFThen hệ thống chặn bản chính thức hoặc thêm watermark DRAFT.

# 11. Yêu cầu phi chức năng

## 11.1. Security & Privacy

Mã hóa dữ liệu khi truyền và khi lưu.

RBAC và kiểm tra patient assignment phía server.

Không ghi PHI vào AI development log công khai.

Audit log bất biến ở cấp ứng dụng.

Không đưa dữ liệu ngoài phạm vi được phép vào prompt.

Secrets lưu bằng environment variables/secret manager.

Tài khoản demo sử dụng dữ liệu mô phỏng hoặc đã khử định danh.

## 11.2. Reliability

Không lưu bản tóm tắt nếu citation validation thất bại nghiêm trọng.

Có retry giới hạn cho lỗi tạm thời của LLM/vector DB.

Có timeout và thông báo lỗi rõ ràng.

Mọi lần tạo tóm tắt có trace ID nội bộ.

## 11.3. Performance Targets

Dashboard dữ liệu đã lập chỉ mục: mục tiêu dưới 2 giây.

Mở source panel: mục tiêu dưới 2 giây.

Sinh bản tóm tắt MVP: mục tiêu dưới 60 giây.

Các mục tiêu sẽ được điều chỉnh sau benchmark thực tế.

## 11.4. Usability & Accessibility

Citation mở trong một thao tác.

Không chỉ dùng màu để biểu thị cảnh báo.

Hiển thị rõ DRAFT, APPROVED và disclaimer.

Có trạng thái loading, empty, warning và error.

Giao diện ưu tiên desktop/tablet cho bác sĩ.

# 12. Chỉ số đánh giá

Nhóm

Chỉ số

Mục tiêu MVP

Groundedness

Citation coverage

100% câu lâm sàng

Groundedness

Citation correctness

≥ 95% trên tập kiểm thử

Safety

Unsupported serious clinical claims

0

Numeric

Value/unit/time consistency

≥ 99%

Timeline

Ordering accuracy

≥ 95%

Extraction

Medication status accuracy

≥ 90%

HITL

Summary approved by a doctor

100% trước sử dụng

UX

Giảm thời gian đọc hồ sơ

≥ 50% trong thử nghiệm

Security

Unauthorized access accepted

0

# 13. Rủi ro và biện pháp

Rủi ro

Biện pháp

AI bịa dữ kiện

Claim-level validation và citation bắt buộc

Dữ liệu thiếu

Hiển thị “Không đủ dữ liệu”

Dữ liệu mâu thuẫn

Hiển thị song song, chuyển bác sĩ quyết định

Nhầm “thuốc đang dùng”

Phân loại trạng thái medication event

Cảnh báo thuốc sai

Chỉ dùng kết quả từ tool chuyên biệt

Sai số/đơn vị

Numeric integrity validator

Truy cập sai hồ sơ

RBAC, patient assignment, audit log

Bác sĩ phụ thuộc AI

Disclaimer và HITL bắt buộc

Rò rỉ PHI qua log

Tách audit log nội bộ khỏi AI development log

Dữ liệu MIMIC không đủ ngoại trú

Nêu rõ giới hạn và bổ sung hồ sơ mô phỏng

# 14. Definition of Done cho MVP

Đăng nhập và phân quyền hoạt động.

Bác sĩ chỉ xem được bệnh nhân được phân công.

Có ít nhất một hồ sơ mô phỏng đa nguồn hoàn chỉnh.

Agent tạo được summary theo cấu trúc yêu cầu.

100% claim lâm sàng trong test set có citation.

Click citation mở đúng nguồn.

Dữ liệu thiếu/mâu thuẫn được hiển thị.

Bác sĩ chỉnh sửa và phê duyệt được.

Lưu version history và audit log.

Xuất được PDF có disclaimer.

Có test cho hallucination, permission và numeric consistency.

Deploy bằng Docker và có hướng dẫn chạy.