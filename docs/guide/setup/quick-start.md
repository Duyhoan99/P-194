---
title: "Quick Start"
description: "Khởi tạo project trong 5 phút"
weight: 1
---

## Quick Start Guide

## Synthetic Clinical Demo (Windows PowerShell)

This release-demo path is local and synthetic only. It must not connect to a
hospital source and its demonstration login must not be used for production.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/create_synthetic_demo.py data/synthetic_demo.db
npm --prefix frontend install
.\scripts\start-dev.ps1
```

The launcher keeps FastAPI and Next.js running together in one terminal:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

For Docker Desktop, use the Compose workflow instead:

```powershell
make demo-db
docker compose --profile local up --build
```

Both workflows use the synthetic local database only. The local workflow
requires the Python environment and `frontend\node_modules`; the Docker
workflow installs frontend dependencies inside its container.

Open `http://localhost:3000`. The local actor accounts are `doctor-1`,
`doctor-2`, `admin-1`, `steward-1`, and `compliance-1`; all use password
`demo`. Demo authentication and operations metadata work only in development
or test. Production remains fail-closed until trusted SSO/OIDC, a server-owned
assignment provider, PostgreSQL, patient mapping, governance approval, and
the required data/operational controls exist.

With the backend running, `python scripts/run_demo_smoke.py` verifies health,
assignment metadata, lineage table metadata, and a reviewable summary state.
It prints only statuses, counts, trace IDs, synthetic subject IDs, and
source-table names.

### Bước 1: Clone Template

```bash
git clone https://github.com/AI20K-Build-Cohort-2/starter-code-template.git C2-App-XXX
cd C2-App-XXX
```

### Bước 2: Environment Setup

```bash
# Tạo virtual environment
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux

# Cài dependencies
pip install -r requirements.txt

# Tạo .env từ template
cp .env.example .env
# → Mở .env và điền API keys
```

### Bước 3: Verify Setup

```bash
# Chạy server
uvicorn src.main:app --reload

# Mở browser: http://localhost:8000/docs
# → Phải thấy Swagger UI
```

### Bước 4: Git Setup

```bash
# Đổi remote origin sang repo của team
git remote set-url origin https://github.com/AI20K-Build-Cohort-2/C2-App-XXX.git

# Tạo branch develop
git checkout -b develop

# Push lần đầu
git push -u origin develop
```

## Folder Structure

```
C2-App-XXX/
├── src/                    ← Source code chính
│   ├── agents/             ← LangGraph agents
│   │   ├── graph.py        ← Graph definition
│   │   ├── state.py        ← State schema
│   │   ├── nodes/          ← Processing nodes
│   │   └── tools/          ← Agent tools
│   ├── api/                ← FastAPI routes
│   ├── models/             ← Pydantic schemas
│   ├── services/           ← Business logic
│   ├── config.py           ← Settings
│   └── main.py             ← App entry point
├── tests/                  ← Test suite
├── docs/                   ← Documentation
├── eval/                   ← Evaluation results
├── presentation/           ← Demo materials
├── Dockerfile              ← Multi-stage build
├── docker-compose.yml      ← Full stack
└── .github/workflows/      ← CI/CD
```

## Nguyên tắc tổ chức code

1. **Một file một trách nhiệm** — `graph.py` chỉ build graph, `state.py` chỉ định nghĩa state
2. **Nodes vào folder `nodes/`** — Mỗi node là một file riêng
3. **Tools vào folder `tools/`** — Mỗi tool là một file riêng
4. **API routes tách riêng** — Không trộn logic vào main.py
5. **Config centralized** — Tất cả settings trong `config.py`
