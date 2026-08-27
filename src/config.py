from functools import lru_cache
from typing import Any, Literal

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
    llm_api_key: str = ""
    llm_model_name: str = "gpt-4o-mini"
    llm_base_url: str = ""
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Runtime data
    demo_data_dir: str = "./data/demo_mvp_v1"
    database_url: str = "sqlite:///./data/app.db"
    agent_generation_backend: Literal["deterministic", "openai", "llm"] = "deterministic"
    session_secret: str = "local-development-only-change-me"
    session_ttl_seconds: int = Field(default=900, ge=60, le=86400)
    care_plan_public_base_url: str = "http://localhost:8000"
    care_plan_share_ttl_seconds: int = Field(default=7776000, ge=3600, le=31536000)

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    @model_validator(mode="before")
    @classmethod
    def strip_string_inputs(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: (v.strip() if isinstance(v, str) else v)
                for k, v in data.items()
            }
        return data

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.app_env == "production" and len(self.session_secret) < 32:
            raise ValueError("production session secret must contain at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
