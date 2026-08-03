1. Mục tiêu thiết kế

Giao diện giúp bác sĩ:

Tìm đúng bệnh nhân được phân công.

Sinh tóm tắt từ hồ sơ đa nguồn.

Kiểm tra nguồn của từng nhận định.

Nhận biết dữ liệu thiếu hoặc mâu thuẫn.

Chỉnh sửa và phê duyệt theo quy trình Human-in-the-loop.

Xem timeline, xu hướng xét nghiệm và xuất bản đã duyệt.

Nguyên tắc: AI chỉ hỗ trợ rà soát. Giao diện không được khiến người dùng hiểu bản DRAFT là kết luận y khoa đã được xác nhận.

2. Sitemap

Doctor
├── Login
├── Dashboard
└── Patient Workspace
    ├── Clinical Summary
    ├── Timeline
    ├── Medications
    ├── Lab Analytics
    ├── Source Records
    ├── Conflicts
    └── Review History

Administrator
├── Admin Dashboard
├── User Management
├── Patient Assignment
├── Audit Log
└── System Status

3. Main UI Flow

flowchart TD
    A[Login] --> B{Authentication successful?}
    B -- No --> C[Show error / account locked]
    B -- Yes --> D[Doctor Dashboard]
    D --> E[Select assigned patient]
    E --> F{Authorized?}
    F -- No --> G[Access denied + audit log]
    F -- Yes --> H[Patient Workspace]
    H --> V[Check data availability and select hadm_id/stay_id]
    V --> I[Generate Summary]
    I --> J[Agent Processing]
    J --> K{Validation result}
    K -- Critical citation failure --> L[Block draft + show retry]
    K -- Partial/missing data --> M[Draft + limitations]
    K -- Valid --> N[Draft Summary]
    M --> O[Doctor Review]
    N --> O
    O --> P{Doctor action}
    P -- Edit --> Q[Save edited draft]
    P -- Request regeneration --> J
    P -- Reject --> R[Revision Required]
    P -- Approve --> S{Review checklist complete?}
    S -- No --> O
    S -- Yes --> T[Approved Summary]
    T --> U[Export PDF]

4. Flow theo vai trò

4.1. Doctor Flow

Login
→ Dashboard
→ Chọn bệnh nhân theo `subject_id`
→ Chọn toàn bộ lịch sử hoặc một `hadm_id`/`stay_id`
→ Xem dữ liệu khả dụng trong Patient Workspace
→ Generate Summary
→ Theo dõi trạng thái xử lý
→ Kiểm tra từng citation
→ Xem conflict/missing data
→ Chỉnh sửa hoặc yêu cầu tạo lại
→ Hoàn thành review checklist
→ Approve
→ Xuất PDF

4.2. Admin Flow

Login
→ Admin Dashboard
→ Quản lý tài khoản
→ Gán bác sĩ cho bệnh nhân
→ Kiểm tra audit log
→ Theo dõi lỗi hệ thống

5. Screen 1 — Login

Mục tiêu

Xác thực người dùng và thông báo đây là hệ thống chứa dữ liệu nhạy cảm.

Components

Logo và tên sản phẩm.

Email/Username.

Password.

Nút Sign In.

Thông báo “Chỉ dành cho người dùng được phân quyền”.

Cảnh báo không sử dụng trên thiết bị công cộng.

Link trợ giúp/khôi phục tài khoản nếu triển khai.

States

Default.

Loading.

Invalid credentials.

Account locked.

Session expired.

Service unavailable.

Low-fidelity wireframe

┌──────────────────────────────────────────────┐
│              CLINICAL SUMMARY AI             │
│  Hệ thống hỗ trợ rà soát hồ sơ cho bác sĩ   │
│                                              │
│  Email / Username                            │
│  ┌────────────────────────────────────────┐  │
│  │                                        │  │
│  └────────────────────────────────────────┘  │
│  Password                                    │
│  ┌────────────────────────────────────────┐  │
│  │ ••••••••                               │  │
│  └────────────────────────────────────────┘  │
│                                              │
│            [      SIGN IN      ]             │
│                                              │
│  Chỉ dành cho người dùng được phân quyền.   │
└──────────────────────────────────────────────┘

6. Screen 2 — Doctor Dashboard

Mục tiêu

Giúp bác sĩ nhanh chóng mở đúng bệnh nhân và biết trạng thái tóm tắt.

Header

Tên bác sĩ.

Vai trò/khoa.

Notification.

Logout.

Main content

Thanh tìm kiếm theo subject_id đã khử danh tính.

Danh sách bệnh nhân được phân công.

Bộ lọc theo trạng thái, số lần nhập viện, có/không ICU stay và mức độ đầy đủ dữ liệu.

Hiển thị anchor_age, giới tính, số admissions và số ICU stays thay cho tên bệnh nhân.

Ngày cập nhật gần nhất.

Trạng thái:

NOT_GENERATED

PROCESSING

DRAFT

UNDER_REVIEW

REVISION_REQUIRED

APPROVED

Actions

Open Patient

Generate Summary

Continue Review

Low-fidelity wireframe

┌────────────────────────────────────────────────────────────────┐
│ Clinical Summary AI      Dr. Nguyen | Cardiology | Logout      │
├────────────────────────────────────────────────────────────────┤
│ Search patient: [________________________] [Search]             │
│ Filter: [All status ▼] [All units ▼]                           │
├────────────────────────────────────────────────────────────────┤
│ subject_id │ Age/Sex │ Admissions/ICU │ Summary status │ Action  │
│ 10000032   │ 52/F    │ 3 / 1          │ DRAFT          │ Review  │
│ 10001217   │ 68/M    │ 2 / 0          │ APPROVED       │ Open    │
│ 10002428   │ 41/F    │ 1 / 1          │ NOT GENERATED  │ Generate│
└────────────────────────────────────────────────────────────────┘

Empty/Error states

Không có bệnh nhân được phân công.

Không tìm thấy kết quả.

Không đủ quyền.

API không phản hồi.

7. Screen 3 — Patient Workspace

Mục tiêu

Đây là màn hình trung tâm để đọc summary, kiểm tra nguồn và thực hiện HITL.

Header

subject_id.

anchor_age và giới tính đã khử danh tính.

Tổng số admissions.

hadm_id đang chọn và stay_id nếu có ICU stay.

Trạng thái dữ liệu khả dụng theo module.

Trạng thái summary.

Thời gian cập nhật.

Nút Generate/Regenerate.

Left navigation

Clinical Summary.

Timeline.

Medications.

Lab Trends.

Source Records.

Conflicts.

Review History.

Main summary panel

Các section:

Clinical Overview.

Active Problems.

Past Medical History.

Current and Recent Medications.

Key Timeline.

Laboratory Trends.

Procedures and Available Coded Events; radiology report chỉ hiển thị khi tích hợp MIMIC-IV-Note.

Conflicts and Missing Information.

Safety Alerts.

Limitations.

Mỗi claim có citation [1], [2]...

Right source panel

Dataset MIMIC-IV, version 3.1.

Module hosp hoặc icu.

Source table.

subject_id, hadm_id, stay_id khi có.

Định danh bản ghi: itemid, emar_id, sequence number hoặc khóa tương ứng.

Date/time.

Structured value, unit, label và reference range khi có.

Excerpt/highlight chỉ xuất hiện nếu nguồn clinical note được tích hợp sau này.

Nút Open source record.

Nút quay lại claim.

Bottom actions

Edit Summary

Request Regeneration

Reject

Confirm Review

Approve

Export PDF

Low-fidelity wireframe

┌──────────────────────────────────────────────────────────────────────────────┐
│ subject_id 10000032 | hadm_id 22595853 | 52/F | DRAFT   [Regenerate]       │
│ ⚠ AI-generated summary — physician review required                         │
├──────────────┬──────────────────────────────────────┬────────────────────────┤
│ Summary      │ CLINICAL OVERVIEW                    │ SOURCE EVIDENCE        │
│ Timeline     │                                      │ MIMIC-IV 3.1 / hosp    │
│ Medications  │ Creatinine increased across         │ Table: labevents       │
│ Lab Trends   │ three measurements. [1][2][3]        │ itemid: 50912          │
│ Source Rec.  │                                      │ Value: 1.8 mg/dL       │
│ Conflicts    │ ACTIVE PROBLEMS                      │ charttime: ...         │
│ History      │ - ICD-coded condition... [4]         │ subject_id: 10000032   │
│              │ - ICU stay recorded... [5]           │ hadm_id: 22595853      │
│              │                                      │ [Open source record]   │
│              │ MEDICATION HISTORY                   │                        │
│              │ - Metoprolol, PRESCRIBED... [6]      │                        │
├──────────────┴──────────────────────────────────────┴────────────────────────┤
│ [Edit] [Request Regeneration] [Reject] [Confirm Review] [Approve] [Export] │
└──────────────────────────────────────────────────────────────────────────────┘

Data Availability Panel

Hiển thị trước khi Generate Summary:

MIMIC-IV 3.1 data availability
✓ patients / admissions / transfers
✓ diagnoses / procedures
✓ laboratory / microbiology
✓ prescriptions / eMAR
✓ ICU events
✕ MIMIC-IV-Note — NOT LOADED
✕ MIMIC-IV-ED — NOT LOADED

Các module không được nạp phải hiển thị NOT LOADED; giao diện không được tạo nội dung thay thế.

Visual rules

DRAFT: nhãn nổi bật, không dùng màu xanh hoàn thành.

Cảnh báo nghiêm trọng: biểu tượng + chữ, không chỉ dùng màu.

Claim không chắc chắn phải có nhãn Insufficient evidence hoặc Conflicting.

Source panel không được che mất disclaimer.

8. Screen 4 — Agent Processing

Mục tiêu

Cho bác sĩ biết tiến trình cấp cao mà không hiển thị chain-of-thought.

Progress steps

Xác minh quyền truy cập.

Truy xuất timeline.

Truy xuất xét nghiệm và thuốc.

Truy xuất các bảng hosp/icu và kiểm tra module tùy chọn.

Đối chiếu nguồn.

Kiểm tra tương tác thuốc.

Tạo summary claims.

Xác minh citation.

Lưu bản nháp.

Actions

Cancel

Return to patient

Low-fidelity wireframe

┌───────────────────────────────────────────────┐
│ Generating clinical summary                   │
│                                               │
│ ✓ Access verified                             │
│ ✓ Timeline retrieved                          │
│ ✓ Laboratory data retrieved                   │
│ … Reconciling conflicting sources             │
│ ○ Validating citations                        │
│ ○ Saving draft                                │
│                                               │
│ [Cancel]                                      │
└───────────────────────────────────────────────┘

Error states

Data source unavailable.

Agent timeout.

Drug interaction tool unavailable.

Citation validation failed.

Partial data retrieved.

9. Screen 5 — Interactive Timeline

Components

Trục thời gian theo encounter.

Bộ lọc:

Encounter.

Diagnosis.

Laboratory.

Medication.

Procedure.

ICU event.

Microbiology.

Marker theo loại event.

Chi tiết event khi click.

Citation/source cho từng event.

Badge cho conflict hoặc missing data.

Low-fidelity wireframe

┌──────────────────────────────────────────────────────────────┐
│ Timeline | Filter [All events ▼] [Date range ▼]             │
├──────────────────────────────────────────────────────────────┤
│ Admission 1      ICU stay       Lab event       Medication    │
│     ▲              ◆             ●               ■           │
│ hadm_id ...     stay_id ...    Creatinine      PRESCRIBED    │
│ admit/disch.    intime/out.    1.2 mg/dL       Metoprolol    │
│ [Source]        [Source]       [Source]         [Source]      │
└──────────────────────────────────────────────────────────────┘

10. Screen 6 — Medications

Components

Tên thuốc chuẩn hóa.

Liều, đường dùng, tần suất.

Trạng thái được nguồn hiện tại hỗ trợ:

Prescribed (prescriptions/pharmacy).

Administered (emar/emar_detail hoặc inputevents).

Discontinued khi có bằng chứng trạng thái/thời điểm ngừng.

Unknown khi không đủ bằng chứng.

Reported home medication chỉ xuất hiện khi tích hợp MIMIC-IV-ED; discharge medication chỉ xuất hiện khi có nguồn đáng tin cậy hỗ trợ.

Thời gian hiệu lực.

Nguồn.

Cảnh báo tương tác từ tool.

Badge khi chưa xác định được trạng thái hiện tại.

Interaction warning example

⚠ Potential interaction detected by Drug Knowledge Tool vX.Y
Medication A + Medication B
Severity: Moderate
Evidence source: [Open]
AI does not recommend changing treatment. Physician review required.

11. Screen 7 — Laboratory Analytics

Components

Dropdown chọn chỉ số.

Khoảng thời gian.

Line chart.

Reference range.

Các điểm đo kèm thời gian, giá trị và đơn vị.

Marker encounter/thay đổi thuốc.

Click điểm để mở source.

Tooltip hiển thị itemid, label, source table và charttime.

Warnings

Đơn vị không thống nhất.

Reference range thay đổi.

Thiếu dữ liệu.

Giá trị nghi ngờ.

Không đủ điểm để kết luận xu hướng.

Low-fidelity wireframe

┌──────────────────────────────────────────────────────────────┐
│ Lab Trends | Test [Creatinine ▼] | Range [30 days ▼]        │
├──────────────────────────────────────────────────────────────┤
│ 2.5 ┤                                  ●                    │
│ 2.0 ┤                         ●                             │
│ 1.5 ┤              ●                                        │
│ 1.0 ┤     ●                                                 │
│     └──────────────────────────────────────────────────────  │
│       01 Jul     10 Jul     20 Jul     28 Jul                │
│                                                              │
│ ⚠ Trend is descriptive only; verify clinical context.       │
└──────────────────────────────────────────────────────────────┘

12. Screen 8 — Conflict Resolution

Mục tiêu

Hiển thị mâu thuẫn mà không để AI tự chọn nguồn đúng.

Example

Conflict: Medication status cannot be resolved

Source A
- Metoprolol appears in `prescriptions`.
- Status: PRESCRIBED.

Source B
- No corresponding administration record found in `emar` for the selected time window.
- Status: ADMINISTRATION NOT CONFIRMED.

Status: UNRESOLVED

Doctor actions

Mark source A verified

Mark source B verified

Keep unresolved

Thêm ghi chú.

Mở toàn bộ hai nguồn.

Low-fidelity wireframe

┌──────────────────────────────────────────────────────────────┐
│ DATA CONFLICT — Medication status                           │
├───────────────────────────┬──────────────────────────────────┤
│ SOURCE A                  │ SOURCE B                         │
│ hosp.prescriptions        │ hosp.emar                        │
│ PRESCRIBED                │ No matching administration       │
│ starttime: ...            │ in selected time window          │
├───────────────────────────┴──────────────────────────────────┤
│ Status: UNRESOLVED                                         │
│ Doctor note: [___________________________________________]  │
│ [Verify A] [Verify B] [Keep Unresolved]                    │
└──────────────────────────────────────────────────────────────┘

13. Screen 9 — Edit Summary

Components

Text editor chia theo section.

Citation token không được xóa âm thầm.

Cảnh báo khi sửa claim nhưng citation không còn hỗ trợ.

Nút Revalidate citations.

So sánh bản AI và bản chỉnh sửa.

Rules

Khi thay đổi số liệu, hệ thống yêu cầu citation phù hợp.

Không cho phê duyệt nếu có claim lâm sàng không có citation.

Lưu version và người chỉnh sửa.

14. Screen 10 — HITL Review & Approval Modal

Required checklist

Tôi đã rà soát bản tóm tắt.

Tôi đã kiểm tra các nguồn quan trọng.

Tôi hiểu rằng nội dung AI chỉ mang tính hỗ trợ.

Tôi xác nhận các chỉnh sửa của mình.

Actions

Cancel

Save Draft

Reject

Approve

Nút Approve chỉ bật khi:

Checklist hoàn tất.

Không còn citation lỗi.

Không có claim bắt buộc chưa có nguồn.

Người dùng có quyền bác sĩ với bệnh nhân.

Low-fidelity wireframe

┌─────────────────────────────────────────────────────┐
│ Review and approve summary                          │
├─────────────────────────────────────────────────────┤
│ ☐ I reviewed the summary                            │
│ ☐ I checked critical evidence                       │
│ ☐ I understand AI is decision support only          │
│ ☐ I confirm my edits                                │
│                                                     │
│ Unresolved conflicts: 1                             │
│ Citation errors: 0                                  │
│                                                     │
│ [Cancel] [Save Draft] [Reject] [Approve disabled]  │
└─────────────────────────────────────────────────────┘

15. Screen 11 — Review History

Components

Version.

Người tạo/chỉnh sửa.

Thời gian.

Trạng thái.

Lý do thay đổi.

Diff giữa hai phiên bản.

Link xem bản cũ.

Không cho sửa/xóa lịch sử đã ghi.

Version 3 | APPROVED | Dr. Nguyen | 29/07/2026 20:30
Version 2 | UNDER_REVIEW | Dr. Nguyen | 29/07/2026 20:12
Version 1 | AI DRAFT | Agent | 29/07/2026 20:05

16. Screen 12 — PDF Export

Nội dung bắt buộc

subject_id, hadm_id/stay_id đã khử danh tính.

Version.

Ngày tạo.

Người phê duyệt.

Summary.

Citation/reference list.

Conflict/limitation còn tồn tại.

Disclaimer.

Rules

Bản APPROVED: xuất PDF chính thức.

Bản chưa duyệt: watermark DRAFT — NOT FOR CLINICAL USE.

17. Screen 13 — Admin Dashboard

User Management

Danh sách tài khoản.

Vai trò.

Trạng thái.

Khóa/mở khóa.

Patient Assignment

Gán hoặc thu hồi quyền bác sĩ.

Lịch sử phân quyền.

Audit Log

Actor.

Action.

Patient ID.

Timestamp.

Result.

Trace ID.

System Status

API.

Database.

MIMIC ingestion/checksum status.

Loaded modules: hosp, icu; optional MIMIC-IV-Note, MIMIC-IV-ED.

Vector DB nếu có nguồn văn bản.

LLM gateway.

Drug interaction tool.

18. UI States bắt buộc

Mỗi màn hình liên quan phải thiết kế:

Loading.

Empty.

Success.

Warning.

Error.

Permission denied.

Session expired.

Partial data.

Missing data.

Conflicting data.

Citation unavailable.

Source record missing.

Dataset module not loaded.

Checksum/schema validation failed.

Agent unavailable.

Draft.

Approved.

19. Safety Disclaimer

Hiển thị tại Patient Workspace, Approval Modal và PDF:

Bản tóm tắt này do AI tạo từ dữ liệu MIMIC-IV 3.1 đã khử định danh nhằm hỗ trợ bác sĩ rà soát hồ sơ. Nội dung không phải là chẩn đoán, khuyến nghị điều trị hoặc sự thay thế cho đánh giá chuyên môn. Bác sĩ phải kiểm tra bản tóm tắt và các nguồn được trích dẫn trước khi sử dụng. Các module không được nạp sẽ không được hệ thống suy đoán hoặc thay thế bằng dữ liệu do AI tạo.

20. Responsive và Accessibility

Ưu tiên desktop/tablet.

Source panel có thể thu gọn trên màn hình nhỏ.

Cảnh báo có icon và text, không chỉ dựa vào màu.

Hỗ trợ keyboard focus.

Contrast đủ rõ.

Tooltip giải thích các trạng thái và citation.

Không hiển thị dữ liệu nhạy cảm ở notification ngoài ứng dụng.

21. Prototype Acceptance Checklist

Có đủ Login, Dashboard và Patient Workspace.

Có luồng Generate → Draft → Review → Approve.

Citation mở đúng module, bảng và bản ghi MIMIC nguồn.

Dashboard/Workspace hiển thị subject_id, hadm_id và stay_id khi có.

Có Data Availability Panel và trạng thái NOT LOADED.

Có trạng thái agent processing.

Có conflict/missing data UI.

Có medication status và interaction warning.

Có laboratory chart.

Có review checklist trước khi approve.

Có version history.

Có PDF draft/approved state.

Có Admin và Audit Log screen.

Có loading, empty, error và permission-denied states.