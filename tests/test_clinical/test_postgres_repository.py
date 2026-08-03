import pytest

from src.api.dependencies import build_clinical_repository
from src.clinical.errors import ClinicalDatabaseUnavailable
from src.config import Settings


def test_postgresql_factory_rejects_missing_dsn_without_fallback():
    settings = Settings(
        app_env="development",
        clinical_backend="postgresql",
        clinical_postgres_dsn="",
        clinical_cursor_secret="s" * 32,
    )

    with pytest.raises(ClinicalDatabaseUnavailable):
        build_clinical_repository(settings)


def test_postgres_integration_requires_explicit_test_dsn():
    if not __import__("os").getenv("CLINICAL_TEST_POSTGRES_DSN"):
        pytest.skip("CLINICAL_TEST_POSTGRES_DSN is not configured")
