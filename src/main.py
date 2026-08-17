import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api.admin_routes import router as admin_router
from src.api.auth_routes import router as auth_router
from src.api.clinical_routes import register_clinical_error_handlers
from src.api.clinical_routes import router as clinical_router
from src.api.ops_routes import router as ops_router
from src.api.review_routes import router as review_router
from src.api.routes import router
from src.api.summary_routes import router as summary_router
from src.api.patient_routes import router as patient_router
from src.api.ingestion_routes import router as ingestion_router
from src.api.ocr_routes import router as ocr_router
from src.api.review_v1_routes import router as review_v1_router
from src.api.claim_routes import router as claim_router
from src.api.ask_routes import router as ask_router
from src.config import get_settings
from src.logger import setup_logging

# Khởi tạo logger
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} in {settings.app_env} mode")
    yield
    logger.info("Shutting down...")


from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

SWAGGER_DARK_STYLE = """
<style>
  body { background: #06090e !important; color: #e2e8f0 !important; font-family: 'Inter', -apple-system, sans-serif !important; }
  .swagger-ui .topbar { background-color: #0c121d !important; border-bottom: 1px solid rgba(255,255,255,0.08) !important; }
  .swagger-ui .topbar .topbar-wrapper { max-width: 1400px; margin: 0 auto; }
  .swagger-ui .topbar a span { color: #14b8a6 !important; font-weight: 700 !important; }
  .swagger-ui { background: #06090e !important; }
  .swagger-ui .info .title { color: #f1f5f9 !important; font-weight: 700 !important; }
  .swagger-ui .info p, .swagger-ui .info li, .swagger-ui .info span { color: #94a3b8 !important; }
  .swagger-ui .scheme-container { background: #0c121d !important; border-bottom: 1px solid rgba(255,255,255,0.08) !important; box-shadow: none !important; }
  .swagger-ui .opblock { border-radius: 12px !important; border: 1px solid rgba(255,255,255,0.08) !important; background: #0e1522 !important; box-shadow: none !important; margin: 0 0 16px !important; }
  .swagger-ui .opblock .opblock-summary { border-color: rgba(255,255,255,0.05) !important; padding: 10px 16px !important; }
  .swagger-ui .opblock .opblock-summary-path { color: #38bdf8 !important; font-family: monospace !important; font-weight: 600 !important; }
  .swagger-ui .opblock .opblock-summary-description { color: #94a3b8 !important; }
  .swagger-ui .opblock-get { border-color: rgba(20,184,166,0.3) !important; background: rgba(20,184,166,0.05) !important; }
  .swagger-ui .opblock-post { border-color: rgba(6,182,212,0.3) !important; background: rgba(6,182,212,0.05) !important; }
  .swagger-ui .opblock-delete { border-color: rgba(244,63,94,0.3) !important; background: rgba(244,63,94,0.05) !important; }
  .swagger-ui .opblock-put { border-color: rgba(245,158,11,0.3) !important; background: rgba(245,158,11,0.05) !important; }
  .swagger-ui .btn.execute { background-color: #14b8a6 !important; border-color: #14b8a6 !important; color: #ffffff !important; border-radius: 9999px !important; font-weight: 600 !important; }
  .swagger-ui .btn.authorize { color: #14b8a6 !important; border-color: #14b8a6 !important; border-radius: 9999px !important; }
  .swagger-ui select, .swagger-ui input[type=text] { background: #131b2b !important; color: #e2e8f0 !important; border: 1px solid rgba(255,255,255,0.15) !important; border-radius: 8px !important; }
  .swagger-ui .model-box, .swagger-ui section.models { background: #0c121d !important; border-color: rgba(255,255,255,0.08) !important; border-radius: 12px !important; }
  .swagger-ui section.models h4 { color: #e2e8f0 !important; }
  .swagger-ui .model-title, .swagger-ui .model { color: #94a3b8 !important; }
  .swagger-ui .response-col_status { color: #14b8a6 !important; }
  .swagger-ui table thead tr td, .swagger-ui table thead tr th { color: #94a3b8 !important; border-color: rgba(255,255,255,0.08) !important; }
</style>
"""

app = FastAPI(
    title="Clinical Review Copilot API (P-194)",
    description="Backend API for Clinical Review Copilot platform — FHIR R4 & PDF/OCR Ingestion",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
)

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
        <link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
        <link rel="shortcut icon" href="https://fastapi.tiangolo.com/img/favicon.png">
        <title>Clinical Review Copilot API — Swagger UI</title>
        {SWAGGER_DARK_STYLE}
        </head>
        <body>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
        const ui = SwaggerUIBundle({{
            url: '/openapi.json',
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout",
            deepLinking: true,
            showExtensions: true,
            showCommonExtensions: true
        }})
        </script>
        </body>
        </html>
        """
    )

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(patient_router, prefix="/api/v1")
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(ocr_router, prefix="/api/v1")
app.include_router(review_v1_router, prefix="/api/v1")
app.include_router(claim_router, prefix="/api/v1")
app.include_router(ask_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(ops_router, prefix="/api/v1")
app.include_router(summary_router, prefix="/api/v1")
app.include_router(review_router, prefix="/api/v1")
app.include_router(clinical_router, prefix="/api/v1")
register_clinical_error_handlers(app)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.4f}s")

    return response


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
