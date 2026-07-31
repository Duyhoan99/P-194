1. Thông tin sản phẩm

Tên sản phẩm: AI Agent hỗ trợ tóm tắt hồ sơ lâm sàng đa nguồn cho bác sĩ

Phiên bản tài liệu: 1.0

Giai đoạn: Thiết kế và xây dựng MVP

Người dùng chính: Bác sĩ điều trị

Dữ liệu: MIMIC-IV 3.1 đã khử định danh, gồm module hosp và icu; dữ liệu mock chỉ dùng cho test hoặc demo giao diện

2. Tổng quan

2.1. Bài toán

Hồ sơ bệnh nhân có thể trải dài qua nhiều lần khám, nhập viện, kết quả xét nghiệm, chẩn đoán hình ảnh, đơn thuốc và ghi chú lâm sàng. Bác sĩ phải đọc và đối chiếu thủ công trước mỗi lượt khám, dẫn đến mất thời gian và có nguy cơ bỏ sót thông tin.

2.2. Mục tiêu sản phẩm

Giảm tối thiểu 50% thời gian đọc lại hồ sơ cũ trong thử nghiệm.

Tạo tóm tắt lâm sàng có cấu trúc và có thể truy nguồn.

Phát hiện dữ liệu thiếu, mâu thuẫn và các cảnh báo thuốc dựa trên tool.

Buộc bác sĩ rà soát và phê duyệt trước khi sử dụng kết quả.

Không để AI tạo chẩn đoán hoặc điều trị mới.

2.3. Nguyên tắc thiết kế

Evidence first: truy xuất và chuẩn hóa bằng chứng trước khi sinh nội dung.

Claim-level citation: citation gắn với từng nhận định, không chỉ cuối đoạn.

Human authority: bác sĩ là người quyết định cuối cùng.

Least privilege: chỉ truy cập dữ liệu cần thiết và được phân quyền.

Uncertainty visible: dữ liệu thiếu hoặc mâu thuẫn phải được hiển thị rõ.

Auditability: mọi truy cập và thay đổi quan trọng phải có log.

3. Phạm vi sản phẩm

3.1. In Scope — MVP

Đăng nhập và phân quyền Bác sĩ/Quản trị viên.

Danh sách bệnh nhân được phân công.

Nạp một cohort đã chọn từ các file CSV nén của MIMIC-IV 3.1 và chọn bệnh nhân theo subject_id.

Truy xuất encounter, diagnosis, laboratory, microbiology, medication, procedure, transfer và ICU events từ các bảng hiện có.

Clinical notes và radiology reports chỉ được hỗ trợ sau khi tích hợp thêm MIMIC-IV-Note.

Sinh tóm tắt lâm sàng có cấu trúc.

Gắn citation cho mọi claim lâm sàng.

Panel nguồn hiển thị đúng bảng và bản ghi MIMIC hỗ trợ, kèm lineage tới subject_id, hadm_id, stay_id, thời gian, mã mục, giá trị và đơn vị.

Đánh dấu dữ liệu thiếu, bất nhất hoặc không đủ bằng chứng.

Bác sĩ chỉnh sửa, yêu cầu tạo lại, từ chối hoặc phê duyệt.

Lưu phiên bản và audit log.

Xuất PDF cho bản đã được phê duyệt.

3.2. Advanced Scope

Timeline tương tác.

Biểu đồ xu hướng xét nghiệm.

Kiểm tra tương tác thuốc qua cơ sở tri thức chuyên biệt.

Phát hiện mâu thuẫn tự động giữa các nguồn.

Memory theo bệnh nhân dưới dạng trạng thái đã kiểm chứng.

So sánh phiên bản tóm tắt giữa các lần khám.

Dashboard quản trị và giám sát chất lượng agent.

Tích hợp MIMIC-IV-Note để RAG trên discharge summaries và radiology reports.

Tích hợp MIMIC-IV-ED để bổ sung triage, ED vitals và medication reconciliation.

Chuyển đổi một phần dữ liệu sang FHIR-like resources khi cần kiểm thử interoperability.

3.3. Out of Scope

Tự chẩn đoán bệnh mới.

Đề xuất hoặc thay đổi điều trị.

Kê đơn thuốc.

Tư vấn trực tiếp cho bệnh nhân.

Tự động ghi đè hồ sơ EHR chính thức.

LLM tự suy đoán tương tác thuốc.

Sử dụng dữ liệu có thể nhận diện trong phiên bản demo; chỉ dùng MIMIC-IV đã khử định danh hoặc dữ liệu mock.

Kết luận nguồn nào đúng khi dữ liệu mâu thuẫn mà không có bác sĩ xác nhận.

Tuyên bố đã xử lý clinical notes, radiology reports hoặc ED medication reconciliation khi chưa tích hợp MIMIC-IV-Note/MIMIC-IV-ED.

Đưa các file MIMIC-IV thô, trích đoạn dữ liệu restricted hoặc thông tin truy cập PhysioNet lên GitHub/AI log công khai.

4. Người dùng và quyền hạn

4.1. Bác sĩ điều trị

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

4.2. Quản trị viên

Mục tiêu

Quản lý tài khoản và vai trò.

Phân công bác sĩ với bệnh nhân.

Xem audit log và trạng thái hệ thống.

Giới hạn

Không được chỉnh sửa nội dung lâm sàng thay cho bác sĩ, trừ khi đồng thời có vai trò bác sĩ hợp lệ.

5. User Stories

ID

User story

Ưu tiên

US-01

Là bác sĩ, tôi muốn xem danh sách bệnh nhân được phân công để không truy cập nhầm hồ sơ.

Must

US-02

Là bác sĩ, tôi muốn sinh tóm tắt từ nhiều nguồn để giảm thời gian đọc hồ sơ.

Must

US-03

Là bác sĩ, tôi muốn bấm citation để xem đúng bằng chứng nguồn.

Must

US-04

Là bác sĩ, tôi muốn thấy dữ liệu thiếu hoặc mâu thuẫn để không hiểu nhầm kết quả.

Must

US-05

Là bác sĩ, tôi muốn chỉnh sửa và duyệt trước khi lưu hoặc xuất PDF.

Must

US-06

Là bác sĩ, tôi muốn xem xu hướng xét nghiệm theo thời gian.

Should

US-07

Là bác sĩ, tôi muốn xem cảnh báo tương tác thuốc có nguồn từ tool.

Should

US-08

Là quản trị viên, tôi muốn quản lý người dùng và phân quyền bệnh nhân.

Must

US-09

Là quản trị viên, tôi muốn xem audit log truy cập hồ sơ.

Must

US-10

Là bác sĩ, tôi muốn xem lịch sử phiên bản và biết ai đã thay đổi nội dung.

Should

6. Yêu cầu chức năng

FR-01 — Authentication

Hệ thống cho phép đăng nhập bằng tài khoản hợp lệ.

Hỗ trợ vai trò DOCTOR và ADMIN.

Session hết hạn sau thời gian không hoạt động.

Đăng nhập thất bại nhiều lần phải được ghi log và có thể khóa tạm thời.

FR-02 — Authorization

Bác sĩ chỉ được xem bệnh nhân được phân công.

API phải xác minh quyền ở phía server, không chỉ dựa trên giao diện.

Yêu cầu trái phép trả về 403 Forbidden và tạo audit event.

FR-03 — Patient Workspace

Hiển thị định danh đã khử danh tính theo subject_id, anchor_age, giới tính, số lần nhập viện, hadm_id đang chọn, ICU stay_id nếu có và trạng thái tóm tắt.

Không hiển thị tên, địa chỉ hoặc thông tin nhận diện cá nhân.

Cho phép chuyển giữa Summary, Timeline, Medications, Lab Trends, Source Records, Conflicts và Review History.

Hiển thị trạng thái dữ liệu khả dụng cho từng bệnh nhân: admissions, diagnoses, labs, medications, microbiology, procedures và ICU events.

FR-04 — Data Ingestion

Nhận các file csv.gz của MIMIC-IV 3.1 từ thư mục dữ liệu cục bộ được cấu hình bằng environment variable; không lưu file dữ liệu thô trong repository.

Kiểm tra checksum SHA-256 trước khi nạp nếu file checksum được cung cấp.

Nạp dữ liệu qua staging layer, sau đó chuẩn hóa sang các bảng/clinical events phục vụ ứng dụng.

Bảo toàn khóa nguồn: subject_id, hadm_id, stay_id, itemid, emar_id và các sequence ID liên quan.

Mỗi bản ghi chuẩn hóa phải có source_dataset, source_version, source_module, source_table, định danh nguồn, thời gian và encounter liên quan.

Dữ liệu lỗi schema, sai checksum hoặc vi phạm khóa ngoại phải bị từ chối và ghi lý do.

Pipeline có thể xuất JSON/FHIR-like nội bộ cho API, nhưng dữ liệu gốc vẫn được truy nguồn tới hàng MIMIC tương ứng.

FR-05 — Retrieval

Agent phải truy xuất tối thiểu:

Bệnh nhân và lần nhập viện từ patients, admissions, transfers.

Chẩn đoán/bệnh nền từ diagnoses_icd kết hợp d_icd_diagnoses.

Thủ thuật từ procedures_icd, hcpcsevents và ICU procedureevents khi có.

Kết quả xét nghiệm từ labevents kết hợp d_labitems.

Vi sinh từ microbiologyevents.

Thuốc được kê/cấp/thực hiện từ prescriptions, pharmacy, emar, emar_detail, inputevents khi phù hợp.

Chỉ số nền như huyết áp, chiều cao, cân nặng, BMI và eGFR từ omr khi có.

ICU stay và theo dõi ICU từ icustays, chartevents, datetimeevents, inputevents, outputevents.

Clinical notes và radiology reports không phải nguồn bắt buộc của MVP hiện tại; chỉ truy xuất khi MIMIC-IV-Note được tích hợp.

FR-06 — Structured Clinical Summary

Bản tóm tắt gồm:

Clinical Overview.

Active Problems.

Past Medical History.

Current and Recent Medications.

Key Timeline.

Laboratory Trends.

Procedures and Available Coded Events; radiology report dạng văn bản chỉ xuất hiện khi có MIMIC-IV-Note.

Conflicts and Missing Information.

Safety Alerts.

Limitations.

FR-07 — Claim-Level Citation

Mỗi câu chứa dữ kiện lâm sàng phải có ít nhất một citation.

Citation trỏ tới bản ghi MIMIC cụ thể hoặc đoạn tài liệu cụ thể nếu nguồn văn bản được tích hợp.

Citation phải chứa tối thiểu: dataset MIMIC-IV, version 3.1, module, table, subject_id, hadm_id/stay_id khi có, định danh hàng, thời gian và excerpt/value hỗ trợ.

Citation xét nghiệm phải giữ itemid, label, value, unit, reference range và charttime khi có.

Citation thuốc phải chỉ rõ nguồn là prescriptions, pharmacy, emar, emar_detail hoặc inputevents.

Không được tạo claim nếu validator không tìm thấy bằng chứng hoặc không thể xác định lineage tới bản ghi nguồn.

FR-08 — Source Viewer

Khi bác sĩ chọn citation, hệ thống hiển thị:

Dataset/version, module và tên bảng nguồn.

subject_id, hadm_id, stay_id khi có.

Định danh bản ghi như itemid, emar_id, sequence number hoặc khóa nguồn tương ứng.

Ngày giờ sự kiện.

Bản ghi cấu trúc gốc; đoạn văn được highlight chỉ khi nguồn clinical note đã được tích hợp.

Giá trị, đơn vị, label và reference range với xét nghiệm.

Liên kết quay lại claim tương ứng.

Cảnh báo rõ khi module hoặc bản ghi nguồn chưa được nạp.

FR-09 — Numeric Integrity

Giá trị, đơn vị và thời điểm phải giữ nguyên từ nguồn.

Không tự quy đổi đơn vị nếu không có quy tắc chuẩn hóa được kiểm chứng.

Khi hai nguồn dùng đơn vị khác nhau, hệ thống phải hiển thị cảnh báo.

FR-10 — Conflict Detection

Phát hiện các nhận định không nhất quán giữa hai hoặc nhiều nguồn.

Hiển thị song song các bằng chứng.

Không tự chọn nguồn đúng khi chưa có quy tắc xác định.

Cho phép bác sĩ đánh dấu RESOLVED hoặc UNRESOLVED và ghi chú.

FR-11 — Medication Status

Hệ thống phải phân biệt theo bằng chứng hiện có:

PRESCRIBED: có trong prescriptions/pharmacy.

ADMINISTERED: có bằng chứng trong emar/emar_detail hoặc ICU inputevents.

DISCONTINUED: nguồn có trạng thái/thời điểm ngừng phù hợp.

UNKNOWN_STATUS: không đủ dữ liệu để xác định trạng thái hiện tại.

REPORTED_HOME_MEDICATION và medication reconciliation chỉ được thêm khi tích hợp MIMIC-IV-ED. DISCHARGE_MEDICATION chỉ được dùng khi có nguồn đáng tin cậy xác nhận, ví dụ nguồn note/đơn xuất viện được tích hợp sau này.

Không được gom mọi bản ghi thành “thuốc đang dùng”.

FR-12 — Drug Interaction Tool

Tên thuốc phải được chuẩn hóa trước khi gọi tool.

Cảnh báo chỉ được sinh từ kết quả tool có version/provenance.

LLM chỉ diễn giải, không tự suy đoán tương tác.

Khi tool không khả dụng, hiển thị “Chưa kiểm tra được tương tác thuốc”.

FR-13 — Human Review

Bản do agent tạo có trạng thái DRAFT.

Bác sĩ có thể chỉnh sửa, thêm nhận xét hoặc yêu cầu tạo lại.

Hệ thống lưu riêng bản AI ban đầu và bản bác sĩ chỉnh sửa.

FR-14 — Approval

Trước khi phê duyệt, bác sĩ phải xác nhận:

Đã rà soát bản tóm tắt.

Đã kiểm tra các nguồn quan trọng.

Hiểu rằng nội dung AI chỉ mang tính hỗ trợ.

Chỉ bác sĩ được phân quyền mới có thể phê duyệt.

FR-15 — Versioning

Mỗi phiên bản lưu:

version_id

summary_id

Người tạo/chỉnh sửa

Thời gian

Nội dung thay đổi

Trạng thái

Lý do từ chối hoặc tạo lại

FR-16 — PDF Export

Chỉ bản APPROVED mới được xuất bản giao chính thức.

PDF phải có disclaimer, thời gian tạo, người duyệt và danh sách nguồn.

Bản chưa duyệt chỉ được xuất với watermark DRAFT.

FR-17 — Audit Log

Ghi tối thiểu:

Đăng nhập/đăng xuất.

Xem hồ sơ bệnh nhân.

Tạo tóm tắt.

Mở nguồn.

Chỉnh sửa.

Từ chối/phê duyệt.

Xuất PDF.

Thay đổi phân quyền.

7. Vòng đời bản tóm tắt

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

8. Agent Workflow

8.1. LangGraph nodes

authorize_access
→ plan_retrieval
→ retrieve_mimic_structured_data
→ retrieve_optional_text_sources
→ normalize_events
→ reconcile_sources
→ check_medications
→ generate_claims
→ validate_claims
→ attach_citations
→ safety_guard
→ persist_draft
→ human_review

8.2. Nguyên tắc thực thi

Xác minh user và quyền bệnh nhân.

Xác định câu hỏi/tác vụ tóm tắt.

Lập kế hoạch nguồn cần lấy.

Truy vấn các bảng MIMIC-IV 3.1 theo subject_id, hadm_id và stay_id.

Chỉ chạy hybrid search khi có nguồn văn bản được cấp phép và đã tích hợp; nếu không, node này phải được bỏ qua.

Chuẩn hóa thành clinical events nhưng vẫn giữ đầy đủ lineage tới hàng nguồn.

Đối chiếu dữ liệu và phát hiện mâu thuẫn.

Sinh các claim độc lập.

Kiểm tra từng claim với evidence.

Loại bỏ hoặc hạ mức chắc chắn của claim không đủ nguồn.

Gắn citation.

Lưu bản DRAFT.

Chuyển bác sĩ rà soát.

8.3. Không được hiển thị

Chain-of-thought nội bộ.

Prompt hệ thống.

Thông tin kỹ thuật có thể làm lộ bí mật hoặc dữ liệu ngoài quyền truy cập.

9. Dữ liệu và kiến trúc

9.1. Nguồn dữ liệu hiện có

MIMIC-IV 3.1 — hosp: patients, admissions, transfers, services, diagnoses_icd, d_icd_diagnoses, procedures_icd, d_icd_procedures, hcpcsevents, d_hcpcs, drgcodes, labevents, d_labitems, microbiologyevents, prescriptions, pharmacy, emar, emar_detail, poe, poe_detail, omr, provider.

MIMIC-IV 3.1 — icu: icustays, chartevents, d_items, datetimeevents, inputevents, outputevents, procedureevents, ingredientevents, caregiver.

Drug knowledge base: nguồn độc lập hoặc mock database có version/provenance để kiểm tra tương tác thuốc.

Chưa có trong bộ hiện tại: MIMIC-IV-Note và MIMIC-IV-ED. Hai nguồn này được xem là tích hợp nâng cao, không phải dependency của MVP.

Có thể chuyển đổi một phần dữ liệu đã chuẩn hóa sang JSON/FHIR-like cho API hoặc demo; không thay đổi lineage tới dữ liệu MIMIC nguồn.

9.1.1. Mapping tính năng với bảng MIMIC-IV 3.1

Nhu cầu sản phẩm

Bảng nguồn chính

Thông tin bệnh nhân

hosp.patients

Các lần nhập viện

hosp.admissions

Di chuyển giữa khoa/phòng

hosp.transfers, hosp.services

Chẩn đoán

hosp.diagnoses_icd, hosp.d_icd_diagnoses

Thủ thuật

hosp.procedures_icd, hosp.d_icd_procedures, hosp.hcpcsevents, icu.procedureevents

Xét nghiệm

hosp.labevents, hosp.d_labitems

Vi sinh

hosp.microbiologyevents

Thuốc được kê/cấp

hosp.prescriptions, hosp.pharmacy

Thuốc được thực hiện

hosp.emar, hosp.emar_detail, icu.inputevents

Chỉ số OMR

hosp.omr

ICU stay

icu.icustays

Theo dõi ICU

icu.chartevents, icu.datetimeevents, icu.d_items

Dịch vào/ra

icu.inputevents, icu.outputevents, icu.ingredientevents

9.1.2. Khóa liên kết và lineage

subject_id: định danh bệnh nhân đã khử danh tính, liên kết xuyên suốt các lần nhập viện.

hadm_id: định danh một lần nhập viện; có thể NULL ở một số loại sự kiện.

stay_id: định danh một ICU stay.

itemid: liên kết sự kiện xét nghiệm/ICU với bảng từ điển tương ứng.

Các sequence ID như emar_id, poe_id, pharmacy_id và sequence number phải được bảo toàn để truy nguồn.

MIMIC-IV 3.1 đã sửa itemid trong d_labitems/labevents để nhất quán với v2.2 và loại bỏ hai subject_id không tồn tại trong patients. Pipeline vẫn phải kiểm tra khóa ngoại và không được giả định mọi hadm_id đều khác NULL.

9.1.3. Cohort MVP

MVP không cần nạp toàn bộ dữ liệu vào luồng demo. Cohort đề xuất gồm 20–50 bệnh nhân:

Có ít nhất hai lần nhập viện hoặc một lần nhập viện kèm ICU stay.

Có diagnosis.

Có tối thiểu năm kết quả xét nghiệm và ít nhất một xét nghiệm lặp lại để vẽ xu hướng.

Có dữ liệu thuốc từ prescriptions, emar hoặc inputevents.

Ưu tiên hồ sơ có dữ liệu thiếu, đơn vị không đồng nhất hoặc trạng thái thuốc khó xác định để kiểm thử guardrails.

Tiêu chí cohort phải được lưu thành script có thể tái lập; không commit dữ liệu kết quả chứa hàng MIMIC thô lên repository.

9.1.4. Data quality và versioning

Gắn dataset_version = 3.1 vào mọi bản ghi đã chuẩn hóa.

Không tự xóa giá trị bất thường nếu chưa có quy tắc; giữ riêng raw_value và normalized_value.

Kiểm tra thiếu đơn vị, thay đổi reference range và dữ liệu trùng lặp.

Khi nâng phiên bản, đặc biệt kiểm tra lại các bảng từng thay đổi trong v3.1: d_labitems, diagnoses_icd, drgcodes, labevents, microbiologyevents, omr, transfers, icustays.

Lưu hash/checksum của file đầu vào và phiên bản pipeline để tái lập kết quả.

9.2. Core entities

Entity

Trường chính

Patient

patient_id nội bộ, subject_id, demographics, assigned_doctors

Encounter

encounter_id nội bộ, hadm_id, subject_id, type, start_time, end_time

ICUStay

stay_id nội bộ, stay_id, hadm_id, subject_id, intime, outtime

ClinicalEvent

event_id, subject_id, hadm_id, stay_id, source_table, source_row_key, event_type, event_time, raw_value, normalized_value, unit

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

9.3. Tech stack

Agent orchestration: LangGraph.

LLM: mô hình hỗ trợ ngữ cảnh dài, cấu hình không dùng dữ liệu để huấn luyện.

RAG: vector DB kết hợp keyword/metadata search chỉ khi tích hợp nguồn văn bản được cấp phép; MVP hiện tại ưu tiên SQL/tool retrieval trên dữ liệu cấu trúc.

Backend: FastAPI.

Frontend: Next.js.

Database: PostgreSQL.

Object store: PDF và tài liệu mở rộng; không dùng object store công khai để lưu file MIMIC thô.

Deployment: Docker; cloud hoặc môi trường nội bộ phù hợp.

Observability: trace agent, lỗi, latency và citation validation; không ghi PHI vào log công khai.

10. Acceptance Criteria

AC-01 — Citation Coverage

Given bản tóm tắt đã được tạoWhen một câu chứa thông tin về bệnh, thuốc, xét nghiệm hoặc lần khámThen câu đó phải có ít nhất một citation hợp lệ.

AC-02 — Unsupported Claim

Given không tìm thấy nguồn hỗ trợWhen agent chuẩn bị tạo nhận địnhThen agent phải bỏ nhận định hoặc ghi “Không đủ dữ liệu để kết luận”.

AC-03 — Source Accuracy

Given bác sĩ chọn citationWhen source panel mởThen hệ thống hiển thị đúng tài liệu/bản ghi, thời gian và đoạn hỗ trợ claim.

AC-04 — Numeric Consistency

Given claim chứa giá trị xét nghiệmWhen so sánh với nguồnThen giá trị, đơn vị và thời điểm phải trùng khớp.

AC-05 — No New Diagnosis

Given hồ sơ không chứa chẩn đoán xác địnhWhen agent sinh tóm tắtThen agent không được trình bày chẩn đoán đó như một kết luận.

AC-06 — HITL Required

Given bản tóm tắt chưa được bác sĩ xác nhậnWhen bác sĩ chưa hoàn thành checklist rà soátThen nút Approve phải bị vô hiệu hóa.

AC-07 — Permission Enforcement

Given bác sĩ không được phân công bệnh nhânWhen yêu cầu mở hồ sơThen hệ thống trả về Access Denied và ghi audit event.

AC-08 — Conflict Handling

Given có hai nguồn mâu thuẫnWhen agent tạo tóm tắtThen cả hai nguồn được hiển thị và trạng thái mặc định là UNRESOLVED.

AC-09 — Drug Interaction Failure

Given drug interaction tool không phản hồiWhen agent hoàn tất tóm tắtThen không được bịa cảnh báo và phải hiển thị giới hạn.

AC-10 — PDF Approval

Given summary chưa ở trạng thái APPROVEDWhen người dùng xuất PDFThen hệ thống chặn bản chính thức hoặc thêm watermark DRAFT.

AC-11 — MIMIC Source Lineage

Given một claim được sinh từ dữ liệu MIMIC-IV 3.1When citation được mởThen hệ thống phải hiển thị đúng module, bảng, subject_id, hadm_id/stay_id, định danh bản ghi và giá trị/thời gian hỗ trợ.

AC-12 — Unsupported Dataset Module

Given bộ dữ liệu hiện tại không có MIMIC-IV-Note hoặc MIMIC-IV-EDWhen agent lập kế hoạch truy xuấtThen agent không được gọi nguồn không tồn tại và UI phải hiển thị module đó là NOT LOADED thay vì bịa dữ liệu.

11. Yêu cầu phi chức năng

11.1. Security & Privacy

Mã hóa dữ liệu khi truyền và khi lưu.

RBAC và kiểm tra patient assignment phía server.

Không ghi dữ liệu MIMIC, trích đoạn restricted data hoặc thông tin truy cập PhysioNet vào AI development log công khai.

Không commit file csv.gz, bản trích dữ liệu MIMIC hoặc credential vào GitHub.

Không cố gắng tái định danh cá nhân hoặc tổ chức trong dữ liệu.

Không chia sẻ quyền truy cập PhysioNet restricted data cho người khác.

Duy trì bảo mật vật lý/điện tử và sử dụng dữ liệu đúng mục đích nghiên cứu hợp pháp.

Audit log bất biến ở cấp ứng dụng.

Không đưa dữ liệu ngoài phạm vi được phép vào prompt.

Secrets và đường dẫn dữ liệu lưu bằng environment variables/secret manager.

Tài khoản demo sử dụng MIMIC-IV đã khử định danh hoặc dữ liệu mock.

11.2. Reliability

Không lưu bản tóm tắt nếu citation validation thất bại nghiêm trọng.

Xác minh checksum đầu vào và schema trước khi ingestion.

Kiểm tra ràng buộc subject_id với patients; ghi nhận các hàng có hadm_id/stay_id thiếu thay vì tự suy diễn.

Có retry giới hạn cho lỗi tạm thời của LLM/vector DB.

Có timeout và thông báo lỗi rõ ràng.

Mọi lần tạo tóm tắt có trace ID nội bộ, dataset version và pipeline version.

11.3. Performance Targets

Dashboard dữ liệu đã lập chỉ mục: mục tiêu dưới 2 giây.

Mở source panel: mục tiêu dưới 2 giây.

Sinh bản tóm tắt MVP: mục tiêu dưới 60 giây.

Các mục tiêu sẽ được điều chỉnh sau benchmark thực tế.

11.4. Usability & Accessibility

Citation mở trong một thao tác.

Không chỉ dùng màu để biểu thị cảnh báo.

Hiển thị rõ DRAFT, APPROVED và disclaimer.

Có trạng thái loading, empty, warning và error.

Giao diện ưu tiên desktop/tablet cho bác sĩ.

12. Chỉ số đánh giá

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

13. Rủi ro và biện pháp

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

Dữ liệu MIMIC không đủ ngoại trú/clinical notes

Nêu rõ giới hạn; chỉ bổ sung MIMIC-IV-Note/MIMIC-IV-ED khi có quyền và đã tích hợp

Vi phạm giấy phép PhysioNet

Không chia sẻ quyền truy cập; không commit dữ liệu; kiểm soát storage, log và prompt

Sai lineage sau ETL

Bảo toàn khóa nguồn, checksum, dataset version và kiểm thử foreign key

Giả định sai về thuốc hiện tại

Chỉ hiển thị trạng thái được nguồn hỗ trợ; dùng UNKNOWN_STATUS khi chưa đủ bằng chứng

14. Definition of Done cho MVP

Đăng nhập và phân quyền hoạt động.

Bác sĩ chỉ xem được bệnh nhân được phân công.

Ingestion được một cohort MIMIC-IV 3.1 có thể tái lập từ script.

Checksum/schema/khóa liên kết quan trọng được kiểm tra.

Không có file MIMIC thô hoặc credential trong GitHub/AI log.

Agent tạo được summary theo cấu trúc yêu cầu từ dữ liệu hosp/icu hiện có.

100% claim lâm sàng trong test set có citation.

Click citation mở đúng module, bảng và bản ghi MIMIC nguồn.

Dữ liệu thiếu/mâu thuẫn được hiển thị.

Bác sĩ chỉnh sửa và phê duyệt được.

Lưu version history và audit log.

Xuất được PDF có disclaimer.

Có test cho hallucination, permission và numeric consistency.

Deploy bằng Docker và có hướng dẫn chạy.