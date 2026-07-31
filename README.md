# AI Agent hỗ trợ tóm tắt hồ sơ lâm sàng đa nguồn

**Project:** P-194 · AI20K Build Phase Cohort 3
**Status:** MVP design and documentation; clinical data ingestion, production API and UI are not implemented yet.

## Mục tiêu

Bác sĩ phải đọc nhiều lần nhập viện, xét nghiệm, chẩn đoán, thủ thuật, thuốc và sự kiện ICU để hiểu diễn biến của một bệnh nhân. Dự án thiết kế một AI Agent có thể truy xuất dữ liệu MIMIC-IV 3.1 đã khử định danh, chuẩn hóa theo dòng thời gian và tạo bản tóm tắt có citation tới từng bản ghi nguồn.

Agent chỉ tạo bản `DRAFT`. Bác sĩ được phân công phải kiểm tra nguồn, chỉnh sửa và phê duyệt trước khi bản tóm tắt được sử dụng hoặc xuất PDF. Hệ thống không tự chẩn đoán, kê đơn, thay đổi điều trị hoặc ghi đè hồ sơ EHR.

## Phạm vi MVP

- Vai trò `DOCTOR` và `ADMIN`, kèm kiểm tra phân công bệnh nhân ở phía server.
- MIMIC-IV 3.1 module `hosp` và `icu`: bệnh nhân, encounters, chẩn đoán, xét nghiệm, vi sinh, thuốc, thủ thuật và ICU events.
- Structured clinical summary, claim-level citation, timeline, laboratory trends, medication status, missing/conflicting data và limitation panel.
- Human-in-the-loop: draft → review → approve/reject, version history và audit log.
- MIMIC-IV-Note, MIMIC-IV-ED, text RAG và drug-interaction knowledge source là phần mở rộng; hiện hiển thị `NOT_LOADED`.

## Kiến trúc và tài liệu

- [ARCHITECTURE.md](ARCHITECTURE.md) — kiến trúc mục tiêu, data lineage, agent workflow, API boundary, bảo mật và deployment.
- [Gate 1/PRD.md](Gate%201/PRD.md) — yêu cầu sản phẩm và acceptance criteria.
- [Gate 1/brief.md](Gate%201/brief.md) — product brief.
- [Gate 1/Wireframe_UI FLow.md](Gate%201/Wireframe_UI%20FLow.md) — luồng và wireframe mục tiêu.
- [docs/architecture_diagram.md](docs/architecture_diagram.md) — sơ đồ tóm tắt.

## Tech stack mục tiêu

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph + LangChain |
| LLM | Long-context provider, cấu hình qua environment variable (mặc định skeleton: `gpt-4o-mini`) |
| Retrieval | Parameterized SQL/tools trên dữ liệu cấu trúc; vector search chỉ khi có nguồn văn bản được cấp phép |
| Backend | FastAPI + Python 3.11+ |
| Frontend | Next.js + TypeScript (chưa triển khai) |
| Database | PostgreSQL mục tiêu; SQLite chỉ cho local skeleton |
| Deployment | Docker; object storage riêng tư cho PDF được phép |

## Chạy skeleton hiện tại

Không đưa file MIMIC, credential hoặc dữ liệu restricted vào repository. Cấu hình secret trong `.env` cục bộ.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

Endpoints hiện có của skeleton:

| Method | Path | Mục đích |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/v1/status` | Trạng thái agent |
| POST | `/api/v1/chat` | Endpoint mẫu để kiểm thử LangGraph, không phải clinical API |

Kiểm thử hiện tại: `5 passed` (`pytest tests -q`).

## Cấu trúc chính

```text
src/                  FastAPI, LangGraph, schemas và services
tests/                API và agent tests
Gate 1/               PRD, brief và wireframe
docs/                 Architecture summary và technical guide
eval/results/         Evaluation evidence
presentation/         Pitch/demo materials
scripts/              Setup và AI usage logging hooks
```

## An toàn dữ liệu

Chỉ dùng MIMIC-IV đã khử định danh hoặc dữ liệu mock được phép. Raw CSV/CSV.GZ, restricted excerpts, PhysioNet credentials và dữ liệu ngoài assignment không được commit, ghi vào public AI log hoặc gửi vào prompt. Citation không hợp lệ phải chặn việc lưu draft; bác sĩ là người quyết định cuối cùng.

## Deliverables

- [x] Source repository và tests
- [x] Product brief, PRD và wireframe
- [x] Architecture document và diagram
- [x] AI usage logging hooks
- [ ] Clinical ingestion/retrieval implementation
- [ ] Next.js UI và live deployment
- [ ] Video demo và pitch deck assets
- [ ] User study metrics và evaluation set thực tế

## Team

| Member | Role | Student ID |
|---|---|---|
| Dao-Trung-Hieu-2912 | Project owner / documentation | Chưa cung cấp |
| Thành viên bổ sung | Chưa cung cấp | Chưa cung cấp |

## License

MIT — sử dụng cho mục đích giáo dục, tuân thủ điều khoản dữ liệu MIMIC-IV/PhysioNet.
