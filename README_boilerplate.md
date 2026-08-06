# AI Agent Tóm Tắt Bệnh Án & Hồ Sơ Sức Khỏe Đa Nguồn Cho Bác Sĩ

> Tóm tắt 1 câu: Hồ sơ bệnh nhân bị phân tán qua nhiều lần nhập viện, xét nghiệm, chẩn đoán, thủ thuật và lịch sử thuốc → AI Agent tổng hợp dữ liệu MIMIC-IV 3.1 thành bản tóm tắt lâm sàng có cấu trúc, có citation và bắt buộc bác sĩ rà soát trước khi sử dụng.

## Vấn đề (Problem)

Mô tả pain point cụ thể với data/số liệu:
- **Ai đang gặp vấn đề?** Bác sĩ điều trị bệnh nhân nội viện hoặc ICU, đặc biệt trong các tình huống khám lại, hội chẩn, tiếp nhận bệnh nhân từ khoa khác hoặc cần đánh giá diễn biến qua nhiều lần nhập viện.
- **Vấn đề tốn bao nhiêu thời gian/tiền?** Bác sĩ phải đọc và đối chiếu thủ công nhiều bảng dữ liệu như lần nhập viện, chẩn đoán, xét nghiệm, thuốc, thủ thuật và sự kiện ICU. Dự án chưa có số liệu benchmark nội bộ về thời gian trung bình hiện tại; mục tiêu MVP là giảm ít nhất 50% thời gian rà soát hồ sơ cũ trong thử nghiệm người dùng.
- **Tại sao các giải pháp hiện tại chưa đủ?** Các hệ thống EHR/EMR truyền thống thường hiển thị dữ liệu theo từng màn hình hoặc từng nhóm nghiệp vụ. Chúng không phải lúc nào cũng tự động dựng timeline, tổng hợp xu hướng, phân biệt trạng thái thuốc, phát hiện dữ liệu thiếu hoặc mâu thuẫn, và gắn nguồn đến từng nhận định lâm sàng.

## Giải pháp (Solution)

Sản phẩm sử dụng AI Agent để truy xuất, chuẩn hóa, đối chiếu và tổng hợp dữ liệu MIMIC-IV 3.1 thành bản tóm tắt lâm sàng có cấu trúc.

- **Feature 1:** Structured Clinical Summary
Tạo bản tóm tắt gồm tổng quan lâm sàng, vấn đề chính, bệnh nền, timeline nhập viện/ICU, lịch sử thuốc, xu hướng xét nghiệm, thủ thuật và các giới hạn dữ liệu.
- **Feature 2:** Claim-Level Citation
Mỗi nhận định lâm sàng phải có citation trỏ về đúng module, bảng và bản ghi nguồn trong MIMIC-IV 3.1, gồm subject_id, hadm_id, stay_id, thời gian, mã mục, giá trị và đơn vị khi có.
- **Feature 3:** Phát hiện dữ liệu thiếu hoặc mâu thuẫn, phân biệt thuốc được kê với thuốc đã thực hiện, hỗ trợ cảnh báo tương tác thuốc qua tool độc lập, đồng thời yêu cầu bác sĩ chỉnh sửa và phê duyệt trước khi lưu hoặc xuất kết quả.

## Target User

- **Primary:** Bác sĩ điều trị bệnh nhân nội viện hoặc ICU, cần xem nhanh dữ liệu từ nhiều lần nhập viện, xét nghiệm, chẩn đoán, thủ thuật, thuốc và sự kiện ICU trước khi khám, hội chẩn hoặc đánh giá diễn biến.
- **Secondary:** Bác sĩ chuyên khoa hoặc bác sĩ hội chẩn cần tra cứu nhanh các thông tin liên quan và kiểm tra nguồn của từng nhận định; quản trị viên hệ thống chịu trách nhiệm quản lý tài khoản, phân quyền bệnh nhân và audit log.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Agent | LangGraph + Long-context LLM |
| Retrieval | SQL/tool retrieval trên MIMIC-IV 3.1; RAG/Vector DB là phần mở rộng khi tích hợp nguồn văn bản |
| Backend | FastAPI + Python 3.11+ |
| Frontend | React/Next.js + TypeScript |
| Database | PostgreSQL |
| DevOps | Docker + GitHub Actions |

## Quick Start

```bash
# 1. Clone repo
git clone https://github.com/AI20K-Build-Cohort-2/team-YOUR_TEAM_NAME.git
cd team-YOUR_TEAM_NAME

# 2. Setup environment
cp .env.example .env
# Edit .env with your API keys

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run development server
uvicorn src.main:app --reload
```

## Project Structure

```
├── src/
│   ├── agents/          # LangGraph agent definitions
│   │   ├── graph.py     # Main graph (nodes + edges)
│   │   ├── state.py     # State schema
│   │   ├── nodes/       # Individual nodes
│   │   └── tools/       # Agent tools (truy vấn timeline, tương tác thuốc)
│   ├── api/             # FastAPI routes
│   ├── models/          # Pydantic schemas
│   ├── services/        # Business logic
│   ├── config.py        # Settings
│   └── main.py          # App entry point
├── tests/               # Test suite
├── docs/                # Documentation
├── eval/                # Evaluation results
├── presentation/        # Demo materials
├── Dockerfile           # Multi-stage build
├── docker-compose.yml   # Full stack
└── .github/workflows/   # CI/CD pipelines
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| POST | /api/v1/summarize | Sinh bản tóm tắt lâm sàng ở trạng thái DRAFT |
| POST | /api/v1/analyze | Phân tích dữ liệu thiếu, mâu thuẫn, xu hướng xét nghiệm và trạng thái thuốc |
| POST | /api/v1/confirm | HITL: Bác sĩ xác nhận và lưu tóm tắt |
| GET | /api/v1/citations/{citation_id} | Mở đúng bản ghi MIMIC-IV 3.1 nguồn

## Deliverables Checklist

- [x] Source Code (GitHub)
- [x] README.md
- [x] Architecture Diagram (`docs/architecture_diagram.md`)
- [x] AI Logs (auto-collected)
- [ ] Live URL / Deploy
- [ ] Video Demo
- [ ] Pitch Deck (`presentation/`)
- [x] Weekly Journal (`JOURNAL.md`)
- [x] Worklog (`WORKLOG.md`)
- [x] Evaluation Evidence (`eval/results/`)

## Team

| Member | Role | Student ID |
|--------|------|-----------|
| Đào Trung Hiếu | AI Engineer / Backend Architecture | 2A202601238 |
| Phạm Duy Hoàn | Product Owner / Clinical Workflow | 2A202601378 |
| Nguyễn Đình Quốc | Team Lead / Prompt Engineer / PM | 2A202601935 |
| Đặng Hoàng Dũng | Data Engineer / QA | 2A202601886 |

## License

MIT c
