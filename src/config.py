from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    # LLM
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Database
    database_url: str = "sqlite:///./data/app.db"
    summary_database_path: str = "./data/clinical_summaries.db"
    summary_backend: Literal["sqlite", "postgresql"] = "sqlite"
    summary_agent_backend: Literal["deterministic", "langgraph"] = "deterministic"
    summary_postgres_dsn: str = ""
    clinical_database_path: str = "./data/mimic_demo.db"
    clinical_backend: Literal["sqlite", "postgresql"] = "sqlite"
    clinical_postgres_dsn: str = ""
    clinical_pool_size: int = Field(default=5, ge=1, le=50)
    clinical_source_dataset: str = "MIMIC-IV"
    clinical_source_version: str = "3.1"
    clinical_source_profile: str = "mimic-iv-3.1"
    clinical_query_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    clinical_max_limit: int = Field(default=1000, ge=1, le=5000)
    clinical_cursor_secret: str = ""
    clinical_cursor_ttl_seconds: int = Field(default=900, ge=60, le=86400)
    mimic_demo_source_dir: str = "./mimic-iv-clinical-database-demo-2.2"
    mimic_demo_subjects_file: str = "./mimic-iv-clinical-database-demo-2.2/demo_subject_id.csv"
    mimic_demo_subject_limit: int = Field(default=3, ge=1, le=100)

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    @model_validator(mode="after")
    def validate_production_clinical_configuration(self) -> "Settings":
        if self.app_env == "production":
            if self.summary_backend != "postgresql":
                raise ValueError("production summary backend must be explicitly set to postgresql")
            if not self.summary_postgres_dsn:
                raise ValueError("production summary PostgreSQL DSN is required")
            if self.clinical_backend != "postgresql":
                raise ValueError("production clinical backend must be explicitly set to postgresql")
            if not self.clinical_postgres_dsn:
                raise ValueError("production PostgreSQL DSN is required")
            if len(self.clinical_cursor_secret) < 32:
                raise ValueError("production cursor secret must contain at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
