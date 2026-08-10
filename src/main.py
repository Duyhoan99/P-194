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


app = FastAPI(
    title="Clinical Review Copilot API",
    description="Backend API for Clinical Review Copilot platform",
    version="1.0.0",
    lifespan=lifespan,
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
