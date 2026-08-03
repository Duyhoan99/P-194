"""Run a metadata-only smoke check against the local synthetic demo API.

The script deliberately accepts only loopback API targets and never prints
response bodies. Its output is restricted to statuses, counts, synthetic
subject IDs, trace IDs, and source-table names.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any

DEFAULT_API_URL = "http://127.0.0.1:8000"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class SmokeCheckError(RuntimeError):
    """Raised when the local demo cannot complete a safe smoke step."""


def local_api_url() -> str:
    """Return a normalized loopback-only API base URL."""
    value = os.environ.get("DEMO_API_URL", DEFAULT_API_URL).rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOCAL_HOSTS:
        raise SmokeCheckError("DEMO_API_URL must target a loopback HTTP API.")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise SmokeCheckError("DEMO_API_URL must be an API origin without a path or credentials.")
    if parsed.username or parsed.password:
        raise SmokeCheckError("DEMO_API_URL must not contain credentials.")
    return value


def format_safe_event(label: str, payload: dict[str, Any], *, status_code: int | None = None) -> str:
    """Format a strict metadata allow-list without retaining clinical content."""
    parts = [label]
    if status_code is not None:
        parts.append(f"status_code={status_code}")
    if isinstance(payload.get("status"), str):
        parts.append(f"status={payload['status']}")
    source_tables: list[str] = []
    records = payload.get("records")
    if isinstance(records, list):
        parts.append(f"record_count={len(records)}")
        source_tables = sorted(
            {
                lineage.get("table")
                for record in records
                if isinstance(record, dict)
                and isinstance((lineage := record.get("lineage")), dict)
                and isinstance(lineage.get("table"), str)
            }
        )
    if isinstance(payload.get("trace_id"), str):
        parts.append(f"trace_id={payload['trace_id']}")
    if source_tables:
        parts.append(f"source_tables={','.join(source_tables)}")
    return " ".join(parts)


class LocalDemoClient:
    """Minimal cookie-aware JSON client that never exposes HTTP response bodies."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with self._opener.open(request, timeout=10) as response:
                raw_body = response.read()
                parsed = json.loads(raw_body) if raw_body else {}
                if not isinstance(parsed, dict):
                    raise SmokeCheckError("Local demo returned an unexpected response shape.")
                return response.status, parsed
        except urllib.error.HTTPError as error:
            raise SmokeCheckError(f"{method} {path} failed with status_code={error.code}.") from None
        except (urllib.error.URLError, TimeoutError):
            raise SmokeCheckError("Local demo API is unavailable.") from None
        except json.JSONDecodeError:
            raise SmokeCheckError("Local demo returned invalid JSON.") from None


def _summary_metadata(version: dict[str, Any]) -> dict[str, Any]:
    draft = version.get("draft")
    trace_id = draft.get("trace_id") if isinstance(draft, dict) else None
    return {"status": version.get("status"), "trace_id": trace_id}


def run_smoke() -> None:
    """Check health, assignment, evidence lineage, and the reviewable draft state."""
    client = LocalDemoClient(local_api_url())

    health_status, _ = client.request("GET", "/health")
    print(format_safe_event("health", {}, status_code=health_status))

    login_status, _ = client.request(
        "POST", "/api/v1/auth/demo-login", {"username": "doctor-1", "password": "demo"}
    )
    print(format_safe_event("demo_login", {}, status_code=login_status))

    patients_status, patients = client.request("GET", "/api/v1/clinical/patients")
    subject_ids = patients.get("patients")
    if not isinstance(subject_ids, list) or not all(isinstance(subject_id, int) for subject_id in subject_ids):
        raise SmokeCheckError("Assigned-subject metadata is invalid.")
    if not subject_ids:
        raise SmokeCheckError("Demo doctor has no assigned synthetic subjects.")
    print(
        "assigned_subjects"
        f" status_code={patients_status} subject_count={len(subject_ids)}"
        f" subject_ids={','.join(str(subject_id) for subject_id in subject_ids)}"
        f" trace_id={patients.get('trace_id', 'missing')}"
    )

    subject_id = subject_ids[0]
    evidence_status, evidence = client.request("GET", f"/api/v1/clinical/patients/{subject_id}/labs?limit=1")
    print(format_safe_event("laboratory_evidence", evidence, status_code=evidence_status))

    generate_status, generated = client.request("POST", f"/api/v1/clinical/patients/{subject_id}/summaries", {})
    print(format_safe_event("summary_generation", _summary_metadata(generated), status_code=generate_status))

    draft = generated.get("draft")
    conflicts = draft.get("conflicts") if isinstance(draft, dict) else None
    unresolved_count = sum(
        1
        for conflict in conflicts if isinstance(conflict, dict) and conflict.get("status") == "UNRESOLVED"
    ) if isinstance(conflicts, list) else 0
    review_status = generated.get("status") if isinstance(generated.get("status"), str) else "UNKNOWN"
    trace_id = _summary_metadata(generated).get("trace_id", "missing")
    print(f"summary_review status={review_status} unresolved_conflict_count={unresolved_count} trace_id={trace_id}")


def main() -> int:
    try:
        run_smoke()
    except SmokeCheckError as error:
        print(f"demo_smoke status=FAILED reason={error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
