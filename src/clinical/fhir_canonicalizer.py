"""Validate uploaded FHIR Bundles and convert supported resources to evidence."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

SUPPORTED_RESOURCE_TYPES = {
    "Condition",
    "Observation",
    "Encounter",
    "MedicationRequest",
    "MedicationStatement",
}


def _display(codeable: Any, default: str) -> str:
    if not isinstance(codeable, dict):
        return default
    if codeable.get("text"):
        return str(codeable["text"])
    codings = codeable.get("coding") or []
    if codings and isinstance(codings[0], dict):
        return str(codings[0].get("display") or codings[0].get("code") or default)
    return default


def _event_time(resource: dict[str, Any]) -> str | None:
    resource_type = resource.get("resourceType")
    if resource_type == "Condition":
        return resource.get("recordedDate") or resource.get("onsetDateTime")
    if resource_type == "Observation":
        return resource.get("effectiveDateTime") or resource.get("issued")
    if resource_type == "Encounter":
        return (resource.get("period") or {}).get("start")
    effective = resource.get("effectivePeriod") or {}
    return (
        resource.get("effectiveDateTime")
        or effective.get("start")
        or resource.get("authoredOn")
        or resource.get("dateAsserted")
    )


def _patient_reference(resource: dict[str, Any]) -> str | None:
    for key in ("subject", "patient"):
        value = resource.get(key)
        if isinstance(value, dict):
            reference = str(value.get("reference", ""))
            if "Patient/" in reference:
                return reference.split("Patient/", 1)[1].split("/", 1)[0]
    return None


def _statement(resource: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    resource_type = str(resource["resourceType"])
    if resource_type == "Condition":
        name = _display(resource.get("code"), "Chẩn đoán")
        coding = (resource.get("code") or {}).get("coding") or [{}]
        code = coding[0].get("code") if isinstance(coding[0], dict) else None
        return (
            "timeline_condition",
            f"Chẩn đoán/Tình trạng bệnh: {name}",
            "active_conditions",
            {"condition": name, "code": code, "resource": resource},
        )
    if resource_type == "Observation":
        name = _display(resource.get("code"), "Xét nghiệm")
        quantity = resource.get("valueQuantity") or {}
        if quantity.get("value") is not None:
            result = f"{quantity['value']} {quantity.get('unit', '')}".strip()
        elif resource.get("valueString") is not None:
            result = str(resource["valueString"])
        else:
            result = _display(resource.get("valueCodeableConcept"), "không có giá trị")
        return (
            "timeline_observation",
            f"Xét nghiệm: {name}; Kết quả: {result}",
            "recent_results",
            {"title": f"Xét nghiệm: {name}", "summary": f"Kết quả: {result}", "resource": resource},
        )
    if resource_type == "Encounter":
        encounter_types = resource.get("type") or []
        name = _display(encounter_types[0] if encounter_types else {}, "Lượt khám")
        status = str(resource.get("status", "unknown"))
        return (
            "timeline_encounter",
            f"Lượt khám: {name}; Trạng thái: {status}",
            "patient_overview",
            {"title": f"Lượt khám: {name}", "summary": f"Trạng thái: {status}", "resource": resource},
        )
    medication = _display(resource.get("medicationCodeableConcept"), "Thuốc")
    status = str(resource.get("status", "unknown"))
    return (
        "timeline_medication",
        f"Thuốc: {medication}; Trạng thái: {status}",
        "current_medications",
        {"title": f"Thuốc: {medication}", "summary": f"Trạng thái: {status}", "resource": resource},
    )


def canonicalize_fhir_bundle(
    payload: Any,
    *,
    patient_id: str,
    tenant_id: str,
    document_id: str,
    source_checksum: str | None = None,
) -> list[dict[str, Any]]:
    """Return patient-scoped evidence without replacing existing FHIR data."""
    if not isinstance(payload, dict) or payload.get("resourceType") != "Bundle":
        raise ValueError("FHIR upload must be a Bundle resource.")
    entries = payload.get("entry")
    if not isinstance(entries, list):
        raise ValueError("FHIR Bundle.entry must be a list.")
    checksum = source_checksum or f"sha256:{hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()}"
    evidence: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict) or resource.get("resourceType") not in SUPPORTED_RESOURCE_TYPES:
            continue
        referenced_patient = _patient_reference(resource)
        if referenced_patient and referenced_patient != patient_id:
            raise ValueError("FHIR resource patient reference does not match upload scope.")
        resource_type = str(resource["resourceType"])
        resource_id = str(resource.get("id") or f"entry-{index + 1}")
        fact_type, statement, section_code, source_value = _statement(resource)
        event_time = _event_time(resource)
        if event_time:
            statement = f"{statement} (ghi nhận {str(event_time)[:10]})"
        evidence_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{resource_type}:{resource_id}").hex[:12]
        citation = {
            "citation_id": f"cit_{document_id}_{resource_type}_{resource_id}",
            "source_type": "fhir",
            "document_id": document_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "json_pointer": f"/entry/{index}/resource",
            "snippet": json.dumps(resource, ensure_ascii=False)[:200],
            "source_checksum": checksum,
        }
        evidence.append({
            "evidence_id": f"fhirev_{evidence_uuid}",
            "tenant_id": tenant_id,
            "patient_id": patient_id,
            "fact_type": fact_type,
            "normalized_value": {"statement": statement, "section_code": section_code},
            "source_value": source_value,
            "source_time": event_time,
            "verification_status": "verified",
            "citations": [citation],
            "record_status": resource.get("status"),
        })
    if not evidence:
        raise ValueError("FHIR Bundle contains no supported clinical resources.")
    return evidence
