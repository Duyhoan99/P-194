# Clinical Review Copilot — P-194

Demo MVP hỗ trợ bác sĩ tổng hợp hồ sơ lâm sàng đa nguồn từ **FHIR R4** và **PDF/ảnh OCR**. Hệ thống chuẩn hoá dữ liệu thành timeline và evidence packet, trả lời câu hỏi có citation, phát hiện mâu thuẫn, tạo bản review và yêu cầu bác sĩ duyệt trước khi xuất PDF.

> Đây là phần mềm hỗ trợ rà soát, không chẩn đoán, kê đơn hoặc thay thế quyết định chuyên môn.

## Phạm vi hiện tại

- Nhập FHIR R4 Bundle dạng JSON.
- Nhập PDF có text hoặc tài liệu scan/ảnh qua OCR.
- Ghép tài liệu với bệnh nhân hiện có hoặc tạo hồ sơ mới.
- Timeline, xu hướng xét nghiệm, thuốc, xung đột dữ liệu và data-quality flags.
- Ask-chart và review generation có citation theo từng nguồn.
- Quy trình review: generated → edited → approved/rejected; chỉ bản đã duyệt mới được xuất PDF.
- Đăng nhập demo bằng cookie HttpOnly; phân quyền doctor/admin/data steward/compliance.
- Bộ dữ liệu `demo_mvp_v1` hoàn toàn synthetic, không chứa người bệnh thật.

Ứng dụng không phụ thuộc database hoặc schema dữ liệu nghiên cứu bên ngoài. Nguồn dữ liệu demo duy nhất nằm tại `data/demo_mvp_v1`.

## Kiến trúc runtime

```text
FHIR JSON ───────────────┐
                        ├─> validate/canonicalize ─> patient-scoped evidence
PDF / PNG / JPEG ─> OCR ┘                              │
                                                      ├─> timeline + trends
                                                      ├─> ask-chart + citations
                                                      └─> review + human approval + PDF
```

- Backend: FastAPI, Pydantic, LangGraph/LangChain.
- Frontend: Next.js 16, React, TypeScript.
- Demo state: repository in-memory khởi tạo từ FHIR/manifest trên disk.
- LLM: tuỳ chọn; mặc định dùng deterministic fallback để demo và test không gọi mạng.
- Trình duyệt gọi API cùng origin; Next.js proxy `/api/*` đến FastAPI.

## Chạy nhanh trên Windows

Yêu cầu: Python 3.11+, Node.js 22+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm.cmd --prefix frontend install
Copy-Item .env.example .env
python scripts\generate_demo_mvp_data.py
.\scripts\start-dev.ps1
```

Mở:

- Web: http://localhost:3000
- Swagger: http://localhost:8000/docs

Tài khoản demo:

| Vai trò | Tài khoản | Mật khẩu |
|---|---|---|
| Bác sĩ | `doctor-1` | `demo` |
| Bác sĩ | `doctor-2` | `demo` |
| Quản trị | `admin-1` | `demo` |
| Data steward | `steward-1` | `demo` |
| Compliance | `compliance-1` | `demo` |

## Chạy bằng Docker

```powershell
python scripts\generate_demo_mvp_data.py
docker compose --profile local up --build
```

Frontend chạy ở cổng 3000, backend ở cổng 8000. `API_PROXY_TARGET` trỏ proxy phía server đến backend; không cần public API URL trong browser.

## Kiểm tra chất lượng

```powershell
pytest -q
ruff check src tests scripts conftest.py
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend test -- --runInBand
npm.cmd --prefix frontend run build
```

Khi backend đang chạy:

```powershell
python scripts\run_demo_smoke.py
```

Smoke test chỉ in trạng thái, số lượng và ID synthetic; không in nội dung hồ sơ, raw document, cookie hoặc secret.

## Cấu hình chính

```dotenv
APP_ENV=development
DEMO_DATA_DIR=./data/demo_mvp_v1
SESSION_SECRET=local-development-only-change-me
SESSION_TTL_SECONDS=900
AGENT_GENERATION_BACKEND=deterministic
LLM_API_KEY=
LLM_MODEL_NAME=gpt-4o-mini
LLM_BASE_URL=
API_PROXY_TARGET=http://127.0.0.1:8000
```

Không commit `.env`, credential hoặc dữ liệu người bệnh thật. Muốn triển khai ngoài demo cần SSO/OIDC tin cậy, persistence được mã hoá, tenant/patient access control, backup/retention, audit bất biến và phê duyệt quản trị lâm sàng.
