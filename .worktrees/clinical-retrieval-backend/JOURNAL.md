# Development Journal — Team P-194

Tài liệu ghi lại các quyết định và kết quả phát triển. Giai đoạn hiện tại tập trung vào product definition và architecture; chưa triển khai clinical ingestion, production API hoặc UI.

## Phân công hiện tại

| Thành viên | Trách nhiệm |
|---|---|
| Đào Trung Hiếu | AI agent, backend architecture và technical documentation |
| Phạm Duy Hoàn | Product scope, clinical workflow và acceptance criteria |
| Nguyễn Đình Quốc | Team lead, prompt engineering và project management |
| Đặng Hoàng Dũng | Data preparation, evaluation và QA |

## Week 1: 2026-07-24 – 2026-07-29

### Mục tiêu

- Xác định bài toán AI Agent hỗ trợ bác sĩ tóm tắt hồ sơ đa nguồn.
- Hoàn thiện product brief, PRD và wireframe cho MVP.
- Chuẩn bị repository và test skeleton.

### Đã hoàn thành

- Chọn MIMIC-IV 3.1 đã khử định danh làm nguồn dữ liệu MVP; giới hạn ở module `hosp` và `icu`.
- Mô tả user roles `DOCTOR` / `ADMIN`, patient assignment, citation bắt buộc và human-in-the-loop.
- Định nghĩa acceptance criteria cho groundedness, numeric integrity, conflict handling, permission và PDF approval.
- Kiểm tra cấu trúc FastAPI/LangGraph template và các test hiện có.

### Khó khăn và giải pháp

| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Dữ liệu lâm sàng nằm ở nhiều bảng và mức encounter khác nhau | Ghi rõ khóa `subject_id`, `hadm_id`, `stay_id` và source lineage trong PRD | Có mô hình retrieval và citation có thể kiểm tra |
| MIMIC-IV-Note/ED chưa được cấp trong bộ hiện tại | Đặt chúng ngoài MVP và yêu cầu UI hiển thị `NOT_LOADED` | Tránh suy đoán hoặc tạo dữ liệu thay thế |
| Template ban đầu còn endpoint/chat mẫu | Đánh dấu rõ skeleton và clinical API mục tiêu trong tài liệu | Không nhầm code mẫu với tính năng đã hoàn thành |

### Bài học

- Evidence phải được truy xuất và chuẩn hóa trước khi gọi LLM.
- Citation cần là entity độc lập để kiểm tra từng claim.
- Human review phải được thực thi ở backend, không chỉ ở UI.

### Kế hoạch tiếp theo

- Chốt identity provider, LLM provider và drug-interaction source.
- Thiết kế schema PostgreSQL/Alembic và ingestion pipeline cho cohort nhỏ.
- Xây retrieval tools và citation validator trước khi làm UI.

## Week 2: 2026-07-30 – 2026-07-31

### Mục tiêu

- Hoàn thiện architecture document và các tài liệu bàn giao.
- Xác minh test skeleton.
- Chuẩn hóa tài liệu để push lên `main`.

### Đã hoàn thành

- Viết lại [ARCHITECTURE.md](ARCHITECTURE.md) với system context, deployment, data model, agent workflow, security và open decisions.
- Cập nhật `README.md` theo sản phẩm P-194 và thay sơ đồ generic bằng architecture của dự án.
- Ghi nhận test hiện tại: `5 passed` với `pytest tests -q`.
- Commit architecture với message `Hoàn thành` và push lên nhánh `main`.

### Khó khăn và giải pháp

| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Chưa có live URL và user-study metrics | Ghi `Chưa cung cấp` / `Chưa đo` thay vì tự bịa dữ liệu | Tài liệu trung thực và có thể cập nhật sau |
| Một số tài liệu vẫn là template generic | Điền nội dung dựa trên PRD/brief và đánh dấu phần chưa triển khai | Deliverable docs nhất quán với scope MVP |

### Bài học

- Tài liệu kiến trúc cần phân biệt rõ target architecture và repository skeleton.
- Các chỉ số chưa benchmark phải được ghi là chưa đo, không dùng target làm actual.

### Kế hoạch tiếp theo

- Xác nhận các quyết định production ở cuối `ARCHITECTURE.md`.
- Bắt đầu implementation theo thứ tự: access control → ingestion → retrieval → validation → review API → UI.
