"""Metadata-only HTTP smoke test for the FHIR/PDF demo."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from typing import Any


class SmokeCheckError(RuntimeError):
    pass


class DemoClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with self._opener.open(request, timeout=15) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raw = error.read()
            payload_out = json.loads(raw) if raw else {"detail": error.reason}
            raise SmokeCheckError(f"{method} {path} failed with HTTP {error.code}: {payload_out}") from error
        except urllib.error.URLError as error:
            raise SmokeCheckError(f"Cannot connect to {self.base_url}: {error.reason}") from error


def format_safe_event(name: str, *, status: int, count: int | None = None, resource_id: str | None = None) -> str:
    fields = [name, f"http_status={status}"]
    if count is not None:
        fields.append(f"count={count}")
    if resource_id is not None:
        fields.append(f"resource_id={resource_id}")
    return " ".join(fields)


def run_smoke() -> None:
    client = DemoClient(os.getenv("DEMO_BASE_URL", "http://127.0.0.1:8000"))

    status, health = client.request("GET", "/health")
    if status != 200 or health.get("status") != "ok":
        raise SmokeCheckError("Health check did not return ok.")
    print(format_safe_event("health", status=status))

    status, _ = client.request("POST", "/api/v1/auth/login", {"email": "doctor-1", "password": "demo"})
    print(format_safe_event("login", status=status))

    status, patient_page = client.request("GET", "/api/v1/patients?page_size=10")
    patients = patient_page.get("items", [])
    if not patients:
        raise SmokeCheckError("The FHIR demo patient list is empty.")
    patient_id = str(patients[0]["patient_id"])
    print(format_safe_event("patients", status=status, count=len(patients), resource_id=patient_id))

    status, timeline = client.request("GET", f"/api/v1/patients/{patient_id}/timeline?page_size=10")
    if timeline.get("total", 0) < 1:
        raise SmokeCheckError("The selected patient has no canonical timeline evidence.")
    print(format_safe_event("timeline", status=status, count=int(timeline["total"]), resource_id=patient_id))

    status, trend = client.request("GET", f"/api/v1/patients/{patient_id}/trends?code=4548-4")
    if not trend.get("points"):
        raise SmokeCheckError("The selected patient has no HbA1c trend points.")
    print(format_safe_event("trend", status=status, count=len(trend["points"]), resource_id=patient_id))

    status, answer = client.request(
        "POST",
        f"/api/v1/patients/{patient_id}/ask",
        {"question": "HbA1c thay đổi như thế nào?"},
    )
    if answer.get("status") not in {"answered", "conflicting"}:
        raise SmokeCheckError("Ask-chart did not return an evidence-grounded answer.")
    print(format_safe_event("ask_chart", status=status, count=len(answer.get("citations", [])), resource_id=patient_id))

    status, review = client.request(
        "POST",
        f"/api/v1/patients/{patient_id}/reviews/generate",
        {"profile_versions": ["type_2_diabetes@1.0.0"]},
    )
    if review.get("status") not in {"generated", "edited"}:
        raise SmokeCheckError("Review generation did not produce a reviewable draft.")
    print(format_safe_event("review", status=status, resource_id=str(review.get("review_id", "unknown"))))


if __name__ == "__main__":
    run_smoke()
