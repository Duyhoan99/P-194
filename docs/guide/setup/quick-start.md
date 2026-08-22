---
title: "Quick Start"
description: "Chạy Clinical Review Copilot trên máy local"
weight: 1
---

## Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm.cmd --prefix frontend install
Copy-Item .env.example .env
python scripts\generate_demo_mvp_data.py
.\scripts\start-dev.ps1
```

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

Đăng nhập `doctor-1` / `demo`. Bộ `data/demo_mvp_v1` hoàn toàn synthetic và gồm FHIR R4 Bundle, PDF cùng biến thể OCR.

## Docker Desktop

```powershell
python scripts\generate_demo_mvp_data.py
docker compose --profile local up --build
```

## Xác minh

```powershell
pytest -q
ruff check src tests scripts conftest.py
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend test -- --runInBand
npm.cmd --prefix frontend run build
```

Khi backend đang chạy, `python scripts\run_demo_smoke.py` kiểm tra login, danh sách bệnh nhân, timeline, trend, ask-chart và review generation mà không in dữ liệu lâm sàng thô.
