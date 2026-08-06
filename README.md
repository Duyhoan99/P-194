# AI Agent hỗ trợ tóm tắt hồ sơ lâm sàng đa nguồn

**Project:** P-194 · AI20K Build Phase Cohort 3
**Status:** Clinical retrieval backend has a fail-closed production boundary. Local development uses synthetic/MIMIC SQLite; production still requires an approved source, hospital authentication, patient-identity mapping and clinical governance sign-off.

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
- [docs/PRD.md](docs/PRD.md) — yêu cầu sản phẩm và acceptance criteria.
- [docs/brief.md](docs/brief.md) — product brief.
- [docs/Wireframe_UI FLow.md](docs/Wireframe_UI%20FLow.md) — luồng và wireframe mục tiêu.
- [docs/architecture_diagram.md](docs/architecture_diagram.md) — sơ đồ tóm tắt.

## Tech stack mục tiêu

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph + LangChain |
| LLM | Long-context provider, cấu hình qua environment variable (mặc định skeleton: `gpt-4o-mini`) |
| Retrieval | Parameterized SQL/tools trên dữ liệu cấu trúc; vector search chỉ khi có nguồn văn bản được cấp phép |
| Backend | FastAPI + Python 3.11+ |
| Frontend | Next.js 16 + TypeScript + Tailwind CSS (Tone xanh y tế) |
| Database | PostgreSQL mục tiêu; SQLite chỉ cho local skeleton |
| Deployment | Docker; object storage riêng tư cho PDF được phép |

## 🚀 Hướng dẫn khởi chạy ứng dụng (Quick Start Guide)

### 1. Setup môi trường Backend
```powershell
# Tạo môi trường ảo Python
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Cài đặt thư viện Python
pip install -r requirements.txt
```

### 2. Cấu hình file `.env`
Sao chép file cấu hình từ `.env.example`:
```powershell
cp .env.example .env
```
> ⚠️ **Lưu ý:** Đảm bảo biến `CLINICAL_CURSOR_SECRET` trong `.env` có độ dài tối thiểu 32 ký tự (mặc định trong mẫu: `local-development-only-change-me`).

### 3. Khởi tạo Cơ sở dữ liệu mẫu y tế (MIMIC-IV Demo DB)
```powershell
.\.venv\Scripts\python.exe scripts\setup_db.py
```
*(Script sẽ tự động chuyển đổi dữ liệu từ `mimic-iv-clinical-database-demo-2.2` thành cơ sở dữ liệu SQLite tại `data/mimic_demo.db`).*

### 4. Cài đặt thư viện Frontend
```powershell
cd frontend
npm install
cd ..
```

### 5. Khởi chạy Ứng dụng

#### 🔹 Cách 1: Chạy tự động cả Backend + Frontend (Khuyên dùng)
```powershell
.\.venv\Scripts\python.exe start.py
```
*(Script `start.py` sẽ tự động khởi chạy Backend ở cổng 8000, Frontend ở cổng 3000 và mở trình duyệt).*

#### 🔹 Cách 2: Chạy thủ công ở 2 Terminal riêng biệt
* **Terminal 1 (Backend FastAPI):**
  ```powershell
  .\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --port 8000
  ```
* **Terminal 2 (Frontend Next.js):**
  ```powershell
  cd frontend
  npm run dev
  ```

---

### 🔑 Đăng nhập & Trải nghiệm
* **Giao diện Web Frontend:** 👉 [http://localhost:3000](http://localhost:3000)
  * **Tài khoản bác sĩ mẫu:** `doctor-1` / Mật khẩu: `demo`
  * **Tài khoản bác sĩ 2:** `doctor-2` / Mật khẩu: `demo`
  * **Tài khoản quản trị:** `admin-1` / Mật khẩu: `demo`
* **Tài liệu API Backend (Swagger UI):** 👉 [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Chạy backend hiện tại (Chi tiết cấu hình)

Không đưa file MIMIC, credential hoặc dữ liệu restricted vào repository. Cấu hình secret trong `.env` cục bộ.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

### Next.js doctor interface

### MIMIC-IV local demo quick start

The default local demo reads only the MIMIC demo CSVs already present in
`mimic-iv-clinical-database-demo-2.2`. Build the read-only indexed SQLite
projection once, then start backend and frontend together:

```powershell
.\.venv\Scripts\python.exe scripts\setup_db.py
npm.cmd --prefix frontend install
.\scripts\start-dev.ps1
```

Open `http://localhost:3000` and sign in with `doctor-1` / `demo`. The demo
assignment is limited to the first subjects listed in
`MIMIC_DEMO_SUBJECTS_FILE`; the default limit is 3. If the configured LLM is
unavailable, summary generation still returns a reviewable evidence-only
`DRAFT` with a limitation explaining the fallback.

Run the metadata-only backend smoke check while both services are running:

```powershell
.\.venv\Scripts\python.exe scripts\run_demo_smoke.py
```

### Synthetic release-demo quick start

Run this path only with the fabricated local database; it never connects to a
hospital system or authorizes use of real patient data.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/create_synthetic_demo.py data/synthetic_demo.db
npm --prefix frontend install
.\scripts\start-dev.ps1
```

The local launcher starts the backend and frontend together. It keeps both
service logs in the same terminal and stops the sibling service when either
one exits. The backend is available at `http://localhost:8000` and the
frontend at `http://localhost:3000`.

For a containerized workflow, use Docker Compose instead:

```powershell
make demo-db
docker compose --profile local up --build
```

This starts the same backend and frontend ports in the `local` Compose
profile. Docker Desktop is required for this option.

After creating the synthetic database, `make demo-up` starts the local Compose
backend and frontend profiles. With the backend running, `make demo-smoke`
checks health, assigned synthetic subjects, source-table lineage, and a
reviewable draft. Smoke output is restricted to statuses, counts, synthetic
subject IDs, trace IDs, and source-table names; it never prints summary text,
clinical values, raw rows, cookies, headers, or secrets.

The demo accounts are `doctor-1`, `doctor-2`, `admin-1`, `steward-1`, and
`compliance-1`, all with password `demo`. They exist only for development/test
and demo authentication is disabled in production. This product supplies
evidence for clinician review only: it is not a diagnosis, treatment
recommendation, or clinical decision.

Additional actor routes are `GET/POST/DELETE /api/v1/admin/users` and its
assignment paths (admin only), `GET /api/v1/admin/audit` (admin/compliance
safe metadata), and `GET /api/v1/ops/clinical-status` plus
`GET /api/v1/ops/ingestion-runs` (admin/data steward operational metadata).

Production is out of scope. A real-data rollout requires reviewed PostgreSQL
migrations and indexes, trusted SSO/OIDC plus server-owned assignment,
patient-identity mapping, ingestion checksum/schema/foreign-key validation,
encrypted backup/restore, retention policy, incident response, and clinical
governance approval. Do not point this demo at a hospital database.

The clinician demo uses an explicit development-only login that creates an HTTP-only server session. The browser stores neither clinical data nor identity in localStorage, URL query strings, or analytics events.

```powershell
npm.cmd --prefix frontend install
.\scripts\start-dev.ps1
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` locally, open `http://localhost:3000`, then use the development-only account `doctor-1` / `demo`. The UI renders only patients returned by the server-side assignment boundary. Production requires trusted SSO/OIDC, PostgreSQL, patient-identity mapping, and clinical governance approval; demo authentication is disabled when `APP_ENV=production`.

Endpoints của skeleton:

| Method | Path | Mục đích |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/v1/status` | Trạng thái agent |
| POST | `/api/v1/chat` | Endpoint mẫu để kiểm thử LangGraph, không phải clinical API |

### Clinical retrieval API

#### Synthetic local demo

Create the deterministic local SQLite database before starting the local Compose profile:

```bash
make demo-db
make demo-test
docker compose --profile local up --build
```

`data/synthetic_demo.db` contains fabricated records only: subjects `101` and `102`, one ICU stay, and an intentional conflicting medication status for UI and evidence-handling demos. It contains no source clinical rows and is not for production use. Production requires `CLINICAL_BACKEND=postgresql` and an explicitly configured PostgreSQL DSN.

Clinical retrieval dùng adapter read-only và chỉ truy vấn các bảng/cột allow-list. SQLite chỉ dành cho local/test; production phải chọn PostgreSQL rõ ràng và không có fallback. MIMIC-IV 3.1 là dữ liệu khử định danh phục vụ development/research, không phải hồ sơ bệnh nhân live.

```dotenv
APP_ENV=development
CLINICAL_BACKEND=sqlite
CLINICAL_DATABASE_PATH=./data/synthetic_demo.db
CLINICAL_POSTGRES_DSN=
CLINICAL_POOL_SIZE=5
CLINICAL_SOURCE_DATASET=MIMIC-IV
CLINICAL_SOURCE_VERSION=3.1
CLINICAL_SOURCE_PROFILE=mimic-iv-3.1
CLINICAL_QUERY_TIMEOUT_SECONDS=2.0
CLINICAL_MAX_LIMIT=1000
CLINICAL_CURSOR_SECRET=local-development-only-change-me
CLINICAL_CURSOR_TTL_SECONDS=900
```

Routes:

| Method | Path | Mục đích |
|---|---|---|
| GET | `/api/v1/clinical/patients/{subject_id}` | Patient overview |
| GET | `/api/v1/clinical/patients/{subject_id}/timeline` | Encounter/ICU timeline |
| GET | `/api/v1/clinical/patients/{subject_id}/diagnoses-procedures` | Coded diagnoses and procedures |
| GET | `/api/v1/clinical/patients/{subject_id}/labs` | Laboratory evidence |
| GET | `/api/v1/clinical/patients/{subject_id}/microbiology` | Microbiology evidence |
| GET | `/api/v1/clinical/patients/{subject_id}/icu-events` | ICU events |
| GET | `/api/v1/clinical/patients/{subject_id}/medications` | Medication evidence and status |
| POST | `/api/v1/auth/demo-login` | Development/test-only signed demo session |
| POST | `/api/v1/auth/logout` | Clear the demo session |
| GET | `/api/v1/clinical/patients` | Patients assigned to the signed demo doctor |
| POST | `/api/v1/clinical/patients/{subject_id}/summaries` | Generate and persist an evidence-backed draft |
| GET/PATCH | `/api/v1/clinical/summaries/{summary_id}` | Read or create an edited draft version |
| POST | `/api/v1/clinical/summaries/{summary_id}/reject` | Reject with a non-empty reason |
| POST | `/api/v1/clinical/summaries/{summary_id}/approve` | Approve after a complete backend-validated checklist |
| POST | `/api/v1/clinical/summaries/{summary_id}/export` | Export an approved summary PDF |
| GET | `/api/v1/clinical/summaries/{summary_id}/versions` | Immutable summary version metadata |

Mọi request clinical phải có access context đáng tin cậy. Khi authentication provider chưa được cấu hình, dependency mặc định fail closed và trả `503`; không dùng `user_id` hoặc role do client tự gửi. Trong development/test, `DemoAssignmentProvider` chỉ được dùng qua dependency override và bị vô hiệu hóa khi `APP_ENV=production`.

Mỗi request dùng `limit` cho kích thước trang và có thể dùng `cursor` opaque do response trước trả về. Cursor có chữ ký, thời hạn và bị ràng buộc với subject/scope/filter/endpoint; không dùng offset sâu cho production.

Để chạy production, tổ chức triển khai phải cung cấp `CLINICAL_BACKEND=postgresql`, DSN bí mật, cursor secret ngẫu nhiên tối thiểu 32 ký tự, PostgreSQL read-only role, migration/index đã được kiểm tra, trusted `AuthProvider`/`AssignmentProvider`, patient-identity mapping và quy trình audit/backup/rollback. Code hiện fail closed nếu các integration đó chưa tồn tại; test pass không đồng nghĩa được phép dùng lâm sàng.

Response chỉ là evidence có `source lineage`, không phải chẩn đoán, khuyến nghị điều trị hay quyết định lâm sàng. Source thiếu được biểu diễn bằng `PARTIAL`/`NOT_LOADED`; database error trả `503`, timeout trả `504`, và response lỗi không chứa SQL, prompt, secret hoặc raw clinical value.

Kiểm thử:

```bash
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m pytest tests/test_clinical tests/test_api/test_clinical_routes.py -q
ruff check src tests
ruff check scripts/check_clinical_indexes.py
python scripts/check_clinical_indexes.py mimic_demo.db
```

Index checker chỉ đọc database, chỉ in tên bảng/index/query-plan và trả mã lỗi nếu index bắt buộc thiếu. Việc tạo index phải thực hiện qua migration/setup được review, không chạy trong app.

## Cấu trúc chính

```text
src/                  FastAPI, LangGraph, schemas và services
tests/                API và agent tests
docs/                 PRD, brief, wireframe, Architecture summary và technical guide
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
- [x] Clinical retrieval backend trên SQLite synthetic/local fixture
- [ ] Clinical ingestion pipeline
- [ ] Next.js UI và live deployment
- [ ] Video demo và pitch deck assets
- [x] User study metrics và evaluation set thực tế

## Team

| Member | Role | Student ID |
|---|---|---|
| Đào Trung Hiếu | AI Engineer / Backend Architecture | 2A202601238 |
| Phạm Duy Hoàn | Product Owner / Clinical Workflow | 2A202601378 |
| Nguyễn Đình Quốc | Team Lead / Prompt Engineer / PM | 2A202601935 |
| Đặng Hoàng Dũng | Data Engineer / QA | 2A202601886 |

## License

MIT — sử dụng cho mục đích giáo dục, tuân thủ điều khoản dữ liệu MIMIC-IV/PhysioNet.
