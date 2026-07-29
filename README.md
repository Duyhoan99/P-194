# AI Agent Tóm Tắt Bệnh Án & Hồ Sơ Sức Khỏe Đa Nguồn Cho Bác Sĩ

> Tóm tắt 1 câu: Thời gian tra cứu hồ sơ cũ quá lâu → AI Agent tổng hợp bệnh án đa nguồn thành tóm tắt lâm sàng có trích nguồn cho Bác sĩ điều trị.

## Vấn đề (Problem)

Mô tả pain point cụ thể với data/số liệu:
- **Ai đang gặp vấn đề?** Bác sĩ điều trị tại các bệnh viện và phòng khám.
- **Vấn đề tốn bao nhiêu thời gian/tiền?** Bệnh án của một bệnh nhân thường trải dài qua nhiều đợt khám (bao gồm xét nghiệm, hình ảnh, đơn thuốc). Bác sĩ mất rất nhiều thời gian để tra cứu, đọc lại và xâu chuỗi thông tin trước mỗi lượt khám.
- **Tại sao các giải pháp hiện tại chưa đủ?** Các hệ thống EHR/EMR truyền thống thường lưu trữ dữ liệu phân mảnh. Chúng không tự động tổng hợp, thiếu khả năng phát hiện mâu thuẫn hay tương tác thuốc thông minh, dẫn đến rủi ro sai sót y khoa khi bác sĩ bị quá tải thông tin.

## Giải pháp (Solution)

Sản phẩm giải quyết vấn đề bằng một AI Agent chuyên biệt giúp tổng hợp hồ sơ sức khỏe thành bản tóm tắt lâm sàng có cấu trúc theo dòng thời gian:
- **Feature 1:** Sinh tóm tắt lâm sàng có cấu trúc (Timeline, Vấn đề chính, Bệnh nền, Thuốc đang dùng, Xu hướng chỉ số).
- **Feature 2:** Trích nguồn (citation) tuyệt đối. Mọi câu tóm tắt đều trích nguồn trỏ ngược về tài liệu/lượt khám gốc để chống hallucination, đảm bảo grounded data.
- **Feature 3:** Phân tích & cảnh báo (phát hiện mâu thuẫn dữ liệu, gắn cờ tương tác thuốc) kết hợp quy trình HITL (bác sĩ phải rà soát, chỉnh sửa và xác nhận trước khi lưu).

## Target User

- **Primary:** Bác sĩ điều trị trực tiếp.
- **Secondary:** Quản trị viên hệ thống y tế / Bác sĩ hội chẩn.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Agent | LangGraph + LLM ngữ cảnh dài (RAG, Vector DB, Hybrid search) |
| Backend | FastAPI + Python 3.11+ |
| Frontend | React/Next.js + TypeScript (Giao diện tóm tắt + Panel nguồn gốc) |
| Database | PostgreSQL + Object Store |
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
| POST | /api/v1/summarize | Sinh tóm tắt lâm sàng từ hồ sơ bệnh nhân |
| POST | /api/v1/analyze | Phân tích mâu thuẫn & tương tác thuốc |
| POST | /api/v1/confirm | HITL: Bác sĩ xác nhận và lưu tóm tắt |

## Deliverables Checklist

- [x] Source Code (GitHub)
- [x] README.md
- [ ] Architecture Diagram (`docs/architecture_diagram.md`)
- [x] AI Logs (auto-collected)
- [ ] Live URL / Deploy
- [ ] Video Demo
- [ ] Pitch Deck (`presentation/`)
- [ ] Weekly Journal (`JOURNAL.md`)
- [ ] Worklog (`WORKLOG.md`)
- [ ] Evaluation Evidence (`eval/results/`)

## Team

| Member | Role | Student ID |
|--------|------|-----------|
| [Tên Bạn] | AI Engineer / Fullstack | [ID] |
| [Tên Bạn 2] | Data / Backend | [ID] |
| [Tên Bạn 3] | Frontend / Prompt Eng | [ID] |

## License

MIT
