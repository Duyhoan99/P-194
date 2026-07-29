# 1. Mục tiêu thiết kế

Giao diện giúp bác sĩ:

Tìm đúng bệnh nhân được phân công.

Sinh tóm tắt từ hồ sơ đa nguồn.

Kiểm tra nguồn của từng nhận định.

Nhận biết dữ liệu thiếu hoặc mâu thuẫn.

Chỉnh sửa và phê duyệt theo quy trình Human-in-the-loop.

Xem timeline, xu hướng xét nghiệm và xuất bản đã duyệt.

Nguyên tắc: AI chỉ hỗ trợ rà soát. Giao diện không được khiến người dùng hiểu bản DRAFT là kết luận y khoa đã được xác nhận.

# 2. Sitemap

Doctor
├── Login
├── Dashboard
└── Patient Workspace
    ├── Clinical Summary
    ├── Timeline
    ├── Medications
    ├── Lab Analytics
    ├── Documents
    ├── Conflicts
    └── Review History

Administrator
├── Admin Dashboard
├── User Management
├── Patient Assignment
├── Audit Log
└── System Status

# 3. Main UI Flow

flowchart TD
    A[Login] --> B{Authentication successful?}
    B -- No --> C[Show error / account locked]
    B -- Yes --> D[Doctor Dashboard]
    D --> E[Select assigned patient]
    E --> F{Authorized?}
    F -- No --> G[Access denied + audit log]
    F -- Yes --> H[Patient Workspace]
    H --> I[Generate Summary]
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

# 4. Flow theo vai trò

## 4.1. Doctor Flow

Login
→ Dashboard
→ Chọn bệnh nhân
→ Xem Patient Workspace
→ Generate Summary
→ Theo dõi trạng thái xử lý
→ Kiểm tra từng citation
→ Xem conflict/missing data
→ Chỉnh sửa hoặc yêu cầu tạo lại
→ Hoàn thành review checklist
→ Approve
→ Xuất PDF

## 4.2. Admin Flow

Login
→ Admin Dashboard
→ Quản lý tài khoản
→ Gán bác sĩ cho bệnh nhân
→ Kiểm tra audit log
→ Theo dõi lỗi hệ thống

# 5. Screen 1 — Login

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

# 6. Screen 2 — Doctor Dashboard

Mục tiêu

Giúp bác sĩ nhanh chóng mở đúng bệnh nhân và biết trạng thái tóm tắt.

Header

Tên bác sĩ.

Vai trò/khoa.

Notification.

Logout.

Main content

Thanh tìm kiếm theo mã bệnh nhân mô phỏng.

Danh sách bệnh nhân được phân công.

Bộ lọc theo khoa, encounter hoặc trạng thái.

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
│ Patient ID │ Latest encounter │ Summary status │ Action         │
│ P-10001    │ 29/07/2026       │ DRAFT          │ Continue Review│
│ P-10002    │ 27/07/2026       │ APPROVED       │ Open           │
│ P-10003    │ 20/07/2026       │ NOT GENERATED  │ Generate       │
└────────────────────────────────────────────────────────────────┘

Empty/Error states

Không có bệnh nhân được phân công.

Không tìm thấy kết quả.

Không đủ quyền.

API không phản hồi.

# 7. Screen 3 — Patient Workspace

Mục tiêu

Đây là màn hình trung tâm để đọc summary, kiểm tra nguồn và thực hiện HITL.

Header

Patient ID.

Tuổi/giới tính mô phỏng.

Encounter gần nhất.

Dị ứng nếu có dữ liệu.

Trạng thái summary.

Thời gian cập nhật.

Nút Generate/Regenerate.

Left navigation

Clinical Summary.

Timeline.

Medications.

Lab Trends.

Documents.

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

Imaging and Procedures.

Conflicts and Missing Information.

Safety Alerts.

Limitations.

Mỗi claim có citation [1], [2]...

Right source panel

Source type.

Document/record ID.

Encounter ID.

Date/time.

Excerpt hoặc structured value.

Highlight bằng chứng.

Nút Open full source.

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
│ Patient P-10001 | 68/M | DRAFT | Updated 20:42        [Regenerate Summary]  │
│ ⚠ AI-generated summary — physician review required                         │
├──────────────┬──────────────────────────────────────┬────────────────────────┤
│ Summary      │ CLINICAL OVERVIEW                    │ SOURCE EVIDENCE        │
│ Timeline     │                                      │                        │
│ Medications  │ Patient admitted for worsening      │ Source: Discharge Note │
│ Lab Trends   │ dyspnea over 3 days. [1]             │ ID: NOTE-1288          │
│ Documents    │                                      │ Date: 28/07/2026       │
│ Conflicts    │ ACTIVE PROBLEMS                      │                        │
│ History      │ - Heart failure... [2]               │ “...worsening dyspnea  │
│              │ - Renal impairment... [3][4]         │ over three days...”    │
│              │                                      │                        │
│              │ MEDICATIONS                          │ [Open full source]     │
│              │ - Metoprolol... [5]                  │                        │
├──────────────┴──────────────────────────────────────┴────────────────────────┤
│ [Edit] [Request Regeneration] [Reject] [Confirm Review] [Approve] [Export] │
└──────────────────────────────────────────────────────────────────────────────┘

Visual rules

DRAFT: nhãn nổi bật, không dùng màu xanh hoàn thành.

Cảnh báo nghiêm trọng: biểu tượng + chữ, không chỉ dùng màu.

Claim không chắc chắn phải có nhãn Insufficient evidence hoặc Conflicting.

Source panel không được che mất disclaimer.

# 8. Screen 4 — Agent Processing

Mục tiêu

Cho bác sĩ biết tiến trình cấp cao mà không hiển thị chain-of-thought.

Progress steps

Xác minh quyền truy cập.

Truy xuất timeline.

Truy xuất xét nghiệm và thuốc.

Đọc tài liệu lâm sàng.

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

# 9. Screen 5 — Interactive Timeline

Components

Trục thời gian theo encounter.

Bộ lọc:

Encounter.

Diagnosis.

Laboratory.

Medication.

Imaging.

Procedure.

Marker theo loại event.

Chi tiết event khi click.

Citation/source cho từng event.

Badge cho conflict hoặc missing data.

Low-fidelity wireframe

┌──────────────────────────────────────────────────────────────┐
│ Timeline | Filter [All events ▼] [Date range ▼]             │
├──────────────────────────────────────────────────────────────┤
│ 01 Jul       10 Jul       18 Jul        28 Jul              │
│   ● Lab        ◆ ED          ■ Drug        ▲ Admission      │
│   │            │             │             │                 │
│ Creatinine   Dyspnea      Metoprolol    Discharge note      │
│ 1.2 mg/dL    triage       prescribed    available           │
│ [Source]     [Source]      [Source]      [Source]            │
└──────────────────────────────────────────────────────────────┘

# 10. Screen 6 — Medications

Components

Tên thuốc chuẩn hóa.

Liều, đường dùng, tần suất.

Trạng thái:

Reported home medication.

Prescribed.

Administered.

Discontinued.

Discharge medication.

Unknown.

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

# 11. Screen 7 — Laboratory Analytics

Components

Dropdown chọn chỉ số.

Khoảng thời gian.

Line chart.

Reference range.

Các điểm đo kèm thời gian, giá trị và đơn vị.

Marker encounter/thay đổi thuốc.

Click điểm để mở source.

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

# 12. Screen 8 — Conflict Resolution

Mục tiêu

Hiển thị mâu thuẫn mà không để AI tự chọn nguồn đúng.

Example

Conflict: Allergy information does not match

Source A
- “No known drug allergies.”
- Admission note — 10/07/2026

Source B
- “Penicillin allergy.”
- Medication reconciliation — 12/07/2026

Status: UNRESOLVED

Doctor actions

Mark source A verified

Mark source B verified

Keep unresolved

Thêm ghi chú.

Mở toàn bộ hai nguồn.

Low-fidelity wireframe

┌──────────────────────────────────────────────────────────────┐
│ DATA CONFLICT — Allergy                                     │
├───────────────────────────┬──────────────────────────────────┤
│ SOURCE A                  │ SOURCE B                         │
│ Admission note            │ Medication reconciliation        │
│ “No known drug allergies” │ “Penicillin allergy”             │
│ 10/07/2026                │ 12/07/2026                       │
├───────────────────────────┴──────────────────────────────────┤
│ Status: UNRESOLVED                                         │
│ Doctor note: [___________________________________________]  │
│ [Verify A] [Verify B] [Keep Unresolved]                    │
└──────────────────────────────────────────────────────────────┘

# 13. Screen 9 — Edit Summary

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

# 14. Screen 10 — HITL Review & Approval Modal

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

# 15. Screen 11 — Review History

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

# 16. Screen 12 — PDF Export

Nội dung bắt buộc

Patient ID mô phỏng.

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

# 17. Screen 13 — Admin Dashboard

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

Vector DB.

LLM gateway.

Drug interaction tool.

# 18. UI States bắt buộc

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

Agent unavailable.

Draft.

Approved.

# 19. Safety Disclaimer

Hiển thị tại Patient Workspace, Approval Modal và PDF:

Bản tóm tắt này do AI tạo nhằm hỗ trợ bác sĩ rà soát hồ sơ. Nội dung không phải là chẩn đoán, khuyến nghị điều trị hoặc sự thay thế cho đánh giá chuyên môn. Bác sĩ phải kiểm tra bản tóm tắt và các nguồn được trích dẫn trước khi sử dụng.

# 20. Responsive và Accessibility

Ưu tiên desktop/tablet.

Source panel có thể thu gọn trên màn hình nhỏ.

Cảnh báo có icon và text, không chỉ dựa vào màu.

Hỗ trợ keyboard focus.

Contrast đủ rõ.

Tooltip giải thích các trạng thái và citation.

Không hiển thị dữ liệu nhạy cảm ở notification ngoài ứng dụng.

# 21. Prototype Acceptance Checklist

Có đủ Login, Dashboard và Patient Workspace.

Có luồng Generate → Draft → Review → Approve.

Citation mở đúng source panel.

Có trạng thái agent processing.

Có conflict/missing data UI.

Có medication status và interaction warning.

Có laboratory chart.

Có review checklist trước khi approve.

Có version history.

Có PDF draft/approved state.

Có Admin và Audit Log screen.

Có loading, empty, error và permission-denied states.