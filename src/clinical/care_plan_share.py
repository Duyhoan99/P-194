"""Persistent, revocable public shares for clinician-approved care plans."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import socket

from src.clinical.care_plan_agent import CarePlanDraft
from src.config import get_settings


def _get_local_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _now() -> datetime:
    return datetime.now(UTC)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _spoken_text(plan: dict[str, Any]) -> str:
    sections = [
        plan.get("doctor_greeting", ""),
        f"Thuốc buổi sáng: {plan.get('morning_meds', '')}",
        f"Thuốc buổi tối: {plan.get('evening_meds', '')}",
        plan.get("medication_note", ""),
        f"Chế độ ăn nên thực hiện: {plan.get('diet_good', '')}",
        f"Thực phẩm cần hạn chế: {plan.get('diet_bad', '')}",
        f"Vận động và sinh hoạt: {plan.get('exercise', '')}",
        f"Dấu hiệu cần xử trí khẩn cấp: {plan.get('emergency_warning', '')}",
        f"Tái khám: {plan.get('follow_up', '')}",
    ]
    return " ".join(str(item).strip() for item in sections if str(item).strip())


class CarePlanShareStore:
    """Stores only the patient-facing snapshot; opaque tokens are never persisted."""

    def __init__(self) -> None:
        settings = get_settings()
        self._path = Path(settings.demo_data_dir) / ".runtime" / "care_plan_shares.json"
        self._database_url = settings.database_url
        self._ttl_seconds = settings.care_plan_share_ttl_seconds
        self._lock = threading.RLock()
        self._schema_ready = False

    @property
    def public_base_url(self) -> str:
        settings = get_settings()
        configured_base_url = settings.care_plan_public_base_url.rstrip("/")
        render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
        if render_hostname and configured_base_url in {"http://localhost:8000", "http://127.0.0.1:8000"}:
            return f"https://{render_hostname}"
        if configured_base_url in {"http://localhost:8000", "http://127.0.0.1:8000"}:
            lan_ip = _get_local_lan_ip()
            if lan_ip and lan_ip != "127.0.0.1":
                return f"http://{lan_ip}:{settings.app_port}"
        return configured_base_url

    @property
    def _uses_postgres(self) -> bool:
        return self._database_url.startswith(("postgresql://", "postgres://"))

    def _ensure_postgres_schema(self) -> None:
        if self._schema_ready:
            return
        with self._lock:
            if self._schema_ready:
                return
            with psycopg.connect(self._database_url, connect_timeout=10) as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS care_plan_shares (
                        token_hash CHAR(64) PRIMARY KEY,
                        patient_id VARCHAR(80) NOT NULL,
                        doctor_sign_name VARCHAR(120) NOT NULL,
                        issued_at TIMESTAMPTZ NOT NULL,
                        expires_at TIMESTAMPTZ NOT NULL,
                        revoked_at TIMESTAMPTZ NULL,
                        plan JSONB NOT NULL,
                        spoken_text TEXT NOT NULL
                    )
                    """
                )
                # The public Supabase Data API receives no policies, so anon/authenticated
                # roles cannot read signed care-plan snapshots. The backend table owner can.
                connection.execute("ALTER TABLE care_plan_shares ENABLE ROW LEVEL SECURITY")
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_care_plan_shares_patient_active
                    ON care_plan_shares (patient_id, issued_at DESC)
                    """
                )
            self._schema_ready = True

    def _load(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, records: list[dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self._path)

    def issue(
        self,
        *,
        patient_id: str,
        plan: CarePlanDraft,
        doctor_sign_name: str,
    ) -> tuple[str, str, datetime]:
        token = secrets.token_urlsafe(32)
        issued_at = _now()
        expires_at = issued_at + timedelta(seconds=self._ttl_seconds)
        patient_plan = plan.model_dump()
        # Deliberately exclude internal reasoning, guideline IDs, assessments and sources.
        public_plan = {
            key: patient_plan.get(key, "")
            for key in (
                "doctor_greeting",
                "morning_meds",
                "evening_meds",
                "medication_note",
                "diet_good",
                "diet_bad",
                "exercise",
                "emergency_warning",
                "follow_up",
            )
        }
        record = {
            "token_hash": _token_hash(token),
            "patient_id": patient_id,
            "doctor_sign_name": doctor_sign_name.strip(),
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "revoked_at": None,
            "plan": public_plan,
            "spoken_text": _spoken_text(public_plan),
        }
        saved_to_postgres = False
        if self._uses_postgres:
            try:
                self._ensure_postgres_schema()
                with psycopg.connect(self._database_url, connect_timeout=10) as connection:
                    connection.execute(
                        """
                        UPDATE care_plan_shares
                        SET revoked_at = %s
                        WHERE patient_id = %s AND revoked_at IS NULL
                        """,
                        (issued_at, patient_id),
                    )
                    connection.execute(
                        """
                        INSERT INTO care_plan_shares (
                            token_hash, patient_id, doctor_sign_name, issued_at,
                            expires_at, revoked_at, plan, spoken_text
                        ) VALUES (%s, %s, %s, %s, %s, NULL, %s, %s)
                        """,
                        (
                            record["token_hash"],
                            patient_id,
                            record["doctor_sign_name"],
                            issued_at,
                            expires_at,
                            Jsonb(public_plan),
                            record["spoken_text"],
                        ),
                    )
                saved_to_postgres = True
            except Exception:
                saved_to_postgres = False

        if not saved_to_postgres:
            with self._lock:
                records = self._load()
                for existing in records:
                    if existing.get("patient_id") == patient_id and not existing.get("revoked_at"):
                        existing["revoked_at"] = issued_at.isoformat()
                records.append(record)
                self._save(records)
        share_url = f"{self.public_base_url}/api/v1/care-plan/listen/{token}"
        return token, share_url, expires_at

    def get(self, token: str) -> dict[str, Any] | None:
        digest = _token_hash(token)
        record = None
        if self._uses_postgres:
            try:
                self._ensure_postgres_schema()
                with psycopg.connect(
                    self._database_url,
                    connect_timeout=10,
                    row_factory=dict_row,
                ) as connection:
                    record = connection.execute(
                        """
                        SELECT token_hash, patient_id, doctor_sign_name, issued_at,
                               expires_at, revoked_at, plan, spoken_text
                        FROM care_plan_shares
                        WHERE token_hash = %s
                        """,
                        (digest,),
                    ).fetchone()
            except Exception:
                record = None
        if not record:
            with self._lock:
                record = next((item for item in self._load() if item.get("token_hash") == digest), None)
        if not record or record.get("revoked_at"):
            return None
        try:
            expires_at = record["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at <= _now():
                return None
        except (KeyError, TypeError, ValueError):
            return None
        return record


care_plan_share_store = CarePlanShareStore()
