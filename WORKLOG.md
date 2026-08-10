# Worklog — Team P-194

Các mục dưới đây ghi lại công việc đã thực hiện trong repository. Người thực hiện trước đây được ghi theo Git username; phân công hiện tại được thống nhất trong README.

## Phân công hiện tại

| Thành viên | Trách nhiệm |
|---|---|
| Đào Trung Hiếu | AI/backend architecture và technical documentation |
| Phạm Duy Hoàn | Product owner và clinical workflow |
| Nguyễn Đình Quốc | Team lead, prompt engineer và PM |
| Đặng Hoàng Dũng | Data engineer và QA |

## 2026-07-24

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Dao-Trung-Hieu-2912 | Khởi tạo repository từ template và kiểm tra cấu trúc FastAPI/LangGraph | ✅ Done | `src/`, `tests/`, Docker skeleton | Chưa ghi nhận |

**Tổng kết ngày:** Repository skeleton sẵn sàng cho product design và implementation sau này.

## 2026-07-29

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Dao-Trung-Hieu-2912 | Hoàn thiện Gate 1 product brief, PRD và wireframe | ✅ Done | `Gate 1/brief.md`, `Gate 1/PRD.md`, `Gate 1/Wireframe_UI FLow.md` | Chưa ghi nhận |
| Dao-Trung-Hieu-2912 | Kiểm tra và cập nhật README/project deliverables | ✅ Done | `README.md`, `README_boilerplate.md` | Chưa ghi nhận |

**Tổng kết ngày:** MVP scope, guardrails, source lineage và acceptance criteria được định nghĩa.

## 2026-07-30

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Dao-Trung-Hieu-2912 | Rà soát PRD để lập architecture target | ✅ Done | Data sources, agent nodes, entities và NFR được trích xuất | Chưa ghi nhận |
| Dao-Trung-Hieu-2912 | Viết architecture document | ✅ Done | `ARCHITECTURE.md` | Chưa ghi nhận |

**Tổng kết ngày:** Hoàn thiện thiết kế system context, deployment topology, data lineage và HITL lifecycle.

## 2026-07-31

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Dao-Trung-Hieu-2912 | Chạy test skeleton | ✅ Done | `pytest tests -q`: `5 passed` | 0.1s |
| Dao-Trung-Hieu-2912 | Điền các tài liệu deliverable còn là template | ✅ Done | README, diagram, journal, worklog, evaluation report, presentation brief | Chưa ghi nhận |
| Dao-Trung-Hieu-2912 | Commit và push tài liệu architecture | ✅ Done | Commit `5c48630`, message `Hoàn thành`, branch `main` | Chưa ghi nhận |

**Tổng kết ngày:** Tài liệu đã được cập nhật theo P-194; code và UI vẫn giữ nguyên scope chưa triển khai.

## 2026-08-07

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Phạm Duy Hoàn | Rà soát và đánh giá thiết kế kiến trúc hệ thống Clinical Review Copilot | ✅ Done | `ARCHITECTURE_Clinical_Review_Copilot.md` | ~2h |
| Phạm Duy Hoàn | Phân tích và thẩm định bộ sơ đồ Mermaid kiến trúc (Overview, Agent Flow, Deployment) | ✅ Done | `Clinical_Review_Copilot_Diagrams.md` | ~1.5h |
| Phạm Duy Hoàn | Kiểm tra, cấu hình và xác minh hệ thống ghi log prompt AI tự động cho dự án | ✅ Done | `scripts/log_antigravity.py`, `scripts/submit_log.py`, `.ai-log/` | ~1h |

**Tổng kết ngày:** Hoàn tất rà soát toàn bộ thiết kế kiến trúc y tế, sơ đồ hệ thống Mermaid và cấu hình luồng logging an toàn, chuẩn bị sẵn sàng cho giai đoạn lập trình.

## 2026-08-08

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Pham Duy Hoan | Đọc và giải thích ba sơ đồ System Overview, Agent Flow và Deployment; Việt hóa các thuật ngữ kỹ thuật chính | ✅ Done | `Diagram.md` được rà soát và thống nhất cách hiểu giữa các thành viên | Chưa ghi nhận |
| Pham Duy Hoan | Tổng hợp `Readme-Clinical.md`, `ARCHITECTURE.md` và `Diagram.md` thành hợp đồng API để ba thành viên phát triển song song | ✅ Done | `API_CONTRACT.md`: endpoint, schema, mã lỗi, phân quyền, phiên bản, watermark, mock và ma trận phụ trách | Chưa ghi nhận |
| Pham Duy Hoan | Chốt lại phạm vi dữ liệu đầu vào của sản phẩm | ✅ Done | Chỉ sử dụng PDF có chữ, PDF scan/ảnh và FHIR R4 JSON Bundle | Chưa ghi nhận |
| Pham Duy Hoan | Loại CSV khỏi thiết kế đầu vào và hợp đồng API của Clinical Review Copilot | ✅ Done | Cập nhật `Readme-Clinical.md`, `ARCHITECTURE.md`, `Diagram.md`, `API_CONTRACT.md`; bỏ endpoint và adapter CSV | Chưa ghi nhận |

**Tổng kết ngày:** Hoàn thành hợp đồng API và thống nhất ba loại dữ liệu đầu vào cho Clinical Review Copilot. Ba thành viên đã có ranh giới tích hợp để phát triển song song.

## Open items

| Item | Owner | Status |
|---|---|---|
| Identity provider/session strategy | Chưa phân công | 🔄 Chưa chốt |
| MIMIC ingestion + PostgreSQL schema | Chưa phân công | 🔄 Chưa bắt đầu |
| Clinical retrieval/citation validator | Chưa phân công | 🔄 Chưa bắt đầu |
| Next.js UI and deployment | Chưa phân công | 🔄 Chưa bắt đầu |
| User study and evaluation set | Chưa phân công | 🔄 Chưa bắt đầu |

