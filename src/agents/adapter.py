"""Stable C2/C3 adapter boundary for backend-supplied AgentRequest payloads."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from src.agents.contracts import AgentRequest
from src.agents.evidence import build_scoped_evidence
from src.agents.state import RuntimeScope


class AgentRequestAdapter:
    """Validate a backend/fixture payload without changing the public contract."""

    def adapt(self, payload: Mapping[str, Any], *, runtime_scope: RuntimeScope) -> AgentRequest:
        request = AgentRequest.model_validate(dict(payload))
        if (
            request.tenant_id != runtime_scope["tenant_id"]
            or request.patient_id != runtime_scope["patient_id"]
            or request.request_id != runtime_scope["request_id"]
        ):
            raise ValueError("Backend payload does not match locked runtime scope.")
        return request

    def from_evidence_packet(
        self,
        packet: Mapping[str, Any] | Any,
        *,
        request_id: str,
        task_type: str,
        tenant_id: str,
        user_id: str,
        profile_versions: list[str],
        approved_memory: dict[str, Any] | None = None,
        question: str | None = None,
    ) -> AgentRequest:
        """Map Member 1's locked packet onto the authoritative AgentRequest.

        The mapping only formats backend-supplied canonical facts. It never
        calculates deltas, trend direction, unit conversions, medication
        differences, conflicts, interactions, or eGFR.
        """
        raw_packet = _mapping(packet)
        patient_id = str(raw_packet.get("patient_id", ""))
        data_watermark = str(raw_packet.get("data_watermark", ""))
        if not patient_id or not data_watermark:
            raise ValueError("Evidence packet requires patient_id and data_watermark.")
        if approved_memory is not None:
            memory_patient_id = str(approved_memory.get("patient_id", patient_id))
            if memory_patient_id != patient_id:
                raise ValueError("Approved memory does not match the locked patient scope.")

        payload = {
            "request_id": request_id,
            "task_type": task_type,
            "tenant_id": tenant_id,
            "patient_id": patient_id,
            "user_id": user_id,
            "data_watermark": data_watermark,
            "profile_versions": profile_versions,
            "approved_memory": approved_memory,
            "structured_facts": _structured_facts(raw_packet, tenant_id=tenant_id),
            "note_evidence": _pdf_note_evidence(raw_packet, tenant_id=tenant_id),
            "question": question,
        }
        runtime_scope: RuntimeScope = {
            "tenant_id": tenant_id,
            "patient_id": patient_id,
            "request_id": request_id,
        }
        request = self.adapt(payload, runtime_scope=runtime_scope)
        # Validate the whole packet before the graph runs so backend callers
        # fail closed on cross-patient evidence.
        build_scoped_evidence(request)
        return request


def _mapping(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        mapped = value.to_dict()
        if isinstance(mapped, Mapping):
            return dict(mapped)
    if hasattr(value, "model_dump"):
        mapped = value.model_dump(mode="json")
        if isinstance(mapped, Mapping):
            return dict(mapped)
    raise TypeError("Evidence packet must be a mapping or serializable model.")


def _citation_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="json"))
    raise TypeError("Citation must be a mapping or serializable model.")


def _citations(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [_citation_payload(value) for value in values]


def _section_for_event(event_type: str) -> str:
    return {
        "condition": "active_conditions",
        "allergy": "active_conditions",
        "medication": "current_medications",
        "observation": "recent_results",
        "note": "changes_to_review",
    }.get(event_type.casefold(), "patient_overview")


_CLINICAL_TERM_REPLACEMENTS = (
    ("Đái tháo đường type 2", "Đái tháo đường típ 2"),
    ("Type 2 diabetes mellitus", "Đái tháo đường típ 2"),
    ("Chronic kidney disease", "Bệnh thận mạn"),
    ("Hypertension", "Tăng huyết áp"),
    ("Obesity", "Béo phì"),
    ("Systolic blood pressure", "Huyết áp tâm thu"),
    ("Diastolic blood pressure", "Huyết áp tâm trương"),
    ("Hemoglobin A1c", "HbA1c"),
    ("Glucose", "Đường huyết"),
    ("Lượt khám GHI CHÚ TÁI KHÁM", "Lần tái khám"),
    ("Lượt khám Ghi chú tái khám", "Lần tái khám"),
    ("Lượt khám Tái khám", "Lần tái khám"),
    ("Lượt khám khám", "Lần khám"),
)

_FHIR_STATUS_LABELS = {
    "entered-in-error": "ghi nhận sai",
    "on-hold": "tạm ngưng",
    "completed": "đã hoàn thành",
    "finished": "đã hoàn thành",
    "inactive": "không còn hiệu lực",
    "active": "đang sử dụng",
    "intended": "dự kiến",
    "stopped": "đã ngừng",
    "cancelled": "đã hủy",
    "unknown": "chưa xác định",
}


def _localize_clinical_text(value: Any) -> str:
    """Translate technical FHIR display values before they reach the UI."""
    text = str(value or "").strip()
    for source, target in _CLINICAL_TERM_REPLACEMENTS:
        if text.casefold() == source.casefold():
            text = target
            break
        text = re.sub(
            rf"\s*\({re.escape(source)}\)",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(re.escape(source), target, text, flags=re.IGNORECASE)
    for status, label in _FHIR_STATUS_LABELS.items():
        text = re.sub(rf"(?<![\w-]){re.escape(status)}(?![\w-])", label, text, flags=re.IGNORECASE)
    return text


def _timeline_facts(packet: dict[str, Any], tenant_id: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    patient_id = str(packet["patient_id"])
    for raw_event in packet.get("timeline", []):
        event = _mapping(raw_event)
        citations = _citations(event.get("citations"))
        if not citations:
            continue
        event_id = str(event.get("event_id", ""))
        event_type = str(event.get("event_type", "event"))
        occurred_at = str(event.get("occurred_at", ""))
        date = occurred_at[:10] if occurred_at else ""
        title = _localize_clinical_text(event.get("title", ""))
        summary = _localize_clinical_text(event.get("summary", ""))
        statement = f"{title} ngày {date}: {summary}" if date else f"{title}: {summary}"
        record_status = event.get("record_status") or event.get("status")
        if record_status is None and any("entered-in-error" in str(citation.get("snippet", "")).casefold() for citation in citations):
            record_status = "entered-in-error"
        facts.append(
            {
                "evidence_id": event_id,
                "tenant_id": tenant_id,
                "patient_id": patient_id,
                "fact_type": f"timeline_{event_type}",
                "normalized_value": {
                    "statement": statement,
                    "section_code": _section_for_event(event_type),
                },
                "source_value": {"title": title, "summary": summary},
                "source_time": occurred_at or None,
                "verification_status": "verified",
                "citations": citations,
                "record_status": record_status,
            }
        )
    return facts


def _trend_facts(packet: dict[str, Any], tenant_id: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    patient_id = str(packet["patient_id"])
    display_by_code = {"4548-4": "HbA1c", "2339-0": "Glucose", "2160-0": "Creatinine"}
    for code, raw_points in packet.get("lab_trends", {}).items():
        points = [_mapping(point) for point in raw_points]
        usable = [point for point in points if _citations(point.get("citations"))]
        if not usable:
            continue
        entries: list[str] = []
        required_tokens: list[str] = []
        citations: list[dict[str, Any]] = []
        seen_citations: set[str] = set()
        seen_points: set[tuple[str, str, str]] = set()
        for point in usable:
            value = str(point.get("value"))
            unit = str(point.get("unit", "")).strip()
            date = str(point.get("observed_at", ""))[:10]
            point_key = (date, value, unit)

            for citation in _citations(point.get("citations")):
                citation_id = str(citation.get("citation_id", ""))
                if citation_id and citation_id not in seen_citations:
                    seen_citations.add(citation_id)
                    citations.append(citation)

            if point_key in seen_points:
                continue
            seen_points.add(point_key)
            entries.append(f"{value} {unit} ({date})".strip())
            required_tokens.extend(token for token in (value, unit, date) if token)
        display = display_by_code.get(str(code), str(code))
        statement = f"Diễn tiến {display}: {'; '.join(entries)}."
        safe_code = re.sub(r"[^A-Za-z0-9]+", "-", str(code)).strip("-")
        facts.append(
            {
                "evidence_id": f"FACT-{patient_id}-TREND-{safe_code}",
                "tenant_id": tenant_id,
                "patient_id": patient_id,
                "fact_type": "lab_trend_backend_fact",
                "normalized_value": {
                    "statement": statement,
                    "required_tokens": required_tokens,
                    "section_code": "recent_results",
                    "method": "source_reported_series",
                },
                "source_value": {"backend_fact": True, "canonical_points": usable},
                "source_time": usable[-1].get("observed_at") if usable else None,
                "verification_status": "verified",
                "citations": citations,
            }
        )
    return facts


def _flag_facts(packet: dict[str, Any], tenant_id: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    patient_id = str(packet["patient_id"])
    for raw_conflict in packet.get("conflicts", []):
        conflict = _mapping(raw_conflict)
        citations = _citations(conflict.get("source_a")) + _citations(conflict.get("source_b"))
        if not citations:
            continue
        facts.append(
            {
                "evidence_id": str(conflict.get("conflict_id", "")),
                "tenant_id": tenant_id,
                "patient_id": patient_id,
                "fact_type": "medication_conflict_backend_fact",
                "normalized_value": {
                    "statement": str(conflict.get("description", "")),
                    "section_code": "changes_to_review",
                },
                "source_value": conflict,
                "source_time": None,
                "verification_status": "needs_verification",
                "citations": citations,
            }
        )
    for raw_interaction in packet.get("drug_interactions", []):
        interaction = _mapping(raw_interaction)
        citations = _citations(interaction.get("citations"))
        if not citations:
            continue
        facts.append(
            {
                "evidence_id": str(interaction.get("flag_id", "")),
                "tenant_id": tenant_id,
                "patient_id": patient_id,
                "fact_type": "drug_interaction_backend_fact",
                "normalized_value": {
                    "statement": str(interaction.get("description", "")),
                    "section_code": "changes_to_review",
                },
                "source_value": interaction,
                "source_time": None,
                "verification_status": "verified",
                "citations": citations,
            }
        )
    return facts


def _condition_facts(packet: dict[str, Any], tenant_id: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    patient_id = str(packet["patient_id"])
    for raw_cond in packet.get("active_conditions", []):
        cond = _mapping(raw_cond)
        condition_name = _localize_clinical_text(cond.get("condition") or cond.get("name") or "Chẩn đoán")
        source_time = cond.get("source_time")
        dated_condition = (
            f"Chẩn đoán/Tình trạng bệnh: {condition_name} (ghi nhận {str(source_time)[:10]})"
            if source_time else f"Chẩn đoán/Tình trạng bệnh: {condition_name}"
        )
        citations = _citations(cond.get("citations", []))
        if not citations:
            continue
        facts.append(
            {
                "evidence_id": str(cond.get("evidence_id") or f"FACT-{patient_id}-COND-{cond.get('code', 'active')}"),
                "tenant_id": tenant_id,
                "patient_id": patient_id,
                "fact_type": "timeline_condition",
                "normalized_value": {
                    "statement": dated_condition,
                    "section_code": "active_conditions",
                },
                "source_value": cond,
                "source_time": source_time,
                "verification_status": "verified",
                "citations": citations,
            }
        )
    return facts


def _current_medication_facts(packet: dict[str, Any], tenant_id: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    patient_id = str(packet["patient_id"])
    for index, raw_medication in enumerate(packet.get("current_medications", []), 1):
        medication = _mapping(raw_medication)
        citations = _citations(medication.get("citations", []))
        if not citations:
            continue
        name = str(medication.get("medication") or medication.get("name") or "Thuốc")
        status = _localize_clinical_text(medication.get("status") or "active")
        source_time = medication.get("source_time")
        medication_statement = f"Thuốc hiện tại: {name} ({status})"
        if source_time:
            medication_statement += f" (ghi nhận {str(source_time)[:10]})"
        facts.append({
            "evidence_id": str(medication.get("evidence_id") or f"FACT-{patient_id}-CURRENT-MED-{index}"),
            "tenant_id": tenant_id,
            "patient_id": patient_id,
            "fact_type": "current_medication_backend_fact",
            "normalized_value": {
                "statement": medication_statement,
                "section_code": "current_medications",
            },
            "source_value": medication,
            "source_time": source_time,
            "verification_status": "verified",
            "citations": citations,
        })
    return facts


def _consolidate_structured_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge duplicate clinical facts across timeline and raw PDF/FHIR extractions on matching dates."""
    consolidated: list[dict[str, Any]] = []
    seen_facts: dict[tuple[str, str, str], dict[str, Any]] = {}

    for fact in facts:
        nv = fact.get("normalized_value", {})
        stmt = str(nv.get("statement", "") if isinstance(nv, dict) else nv)
        sec = str(nv.get("section_code", "") if isinstance(nv, dict) else "")
        ft = str(fact.get("fact_type", ""))
        stmt_clean = stmt.lower()

        # Trend series facts should always be preserved intact
        if "trend" in ft or "diễn tiến" in stmt_clean:
            consolidated.append(fact)
            continue

        # Extract date
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", stmt_clean)
        source_time_str = str(fact.get("source_time", ""))[:10] if fact.get("source_time") else ""
        date_key = date_match.group(1) if date_match else (source_time_str or "no_date")

        if sec == "current_medications" or "thuốc" in stmt_clean:
            clean_med = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", stmt_clean)
            clean_med = re.sub(r"thuốc(?:\s+hiện\s+tại)?:\s*", "", clean_med)
            clean_med = re.sub(r"(?:trạng thái|ghi nhận|đang duy trì|đang sử dụng|active|stopped|discontinued).*", "", clean_med)
            clean_med = re.sub(r"\(.*?\)", "", clean_med).strip()
            med_match = re.search(r"^([a-z\s]+?\d+(?:\.\d+)?\s*(?:mg|g|ml|mcg|ui|iu)?)", clean_med)
            if med_match:
                drug_key = re.sub(r"\s+", " ", med_match.group(1)).strip()
                sem_key = f"med:{drug_key}"
            else:
                sem_key = f"med:{clean_med[:30].strip()}"
        elif sec == "recent_results" or "xét nghiệm" in stmt_clean:
            without_date = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", stmt_clean)
            val_match = re.search(r"(?:kết quả|kết quả:|\:)\s*(\d+(?:\.\d+)?)", without_date) or re.search(r"(\d+(?:\.\d+)?)\s*(?:%|mmol/l|µmol/l|umol/l|mg/dl|ml/min|mmhg|mm\[hg\])?", without_date)
            val_str = val_match.group(1) if val_match else ""
            val_norm = re.sub(r"\.0$", "", val_str)

            if "hba1c" in without_date:
                test_key = "hba1c"
            elif "glucose" in without_date or "đường huyết" in without_date:
                test_key = "glucose"
            elif "creatinine" in without_date:
                test_key = "creatinine"
            elif "egfr" in without_date:
                test_key = "egfr"
            elif "tâm thu" in without_date or "systolic" in without_date:
                test_key = "bp_sys"
            elif "tâm trương" in without_date or "diastolic" in without_date:
                test_key = "bp_dia"
            elif "huyết áp" in without_date or "blood pressure" in without_date:
                try:
                    num_val = float(val_norm)
                    test_key = "bp_sys" if num_val >= 100 else "bp_dia"
                except Exception:
                    test_key = "bp"
            else:
                test_key = without_date[:20].strip()

            sem_key = f"lab:{test_key}:{val_norm}"
        elif sec == "active_conditions" or "chẩn đoán" in stmt_clean:
            cond_clean = re.sub(r"\(.*?\)", "", stmt_clean)
            cond_clean = re.sub(r"chẩn đoán/tình trạng bệnh:\s*", "", cond_clean)
            cond_clean = re.sub(r"ghi nhận\s+\d{4}-\d{2}-\d{2}", "", cond_clean).strip()
            sem_key = f"cond:{cond_clean}"
        else:
            sem_key = f"other:{re.sub(r'\s+', ' ', stmt_clean)}"

        group_key = (sec, date_key, sem_key)
        if group_key not in seen_facts:
            seen_facts[group_key] = fact
            consolidated.append(fact)
        else:
            existing = seen_facts[group_key]
            existing_cits = existing.get("citations", [])
            seen_cids = {c.get("citation_id") or c.get("document_id") or c.get("resource_id") for c in existing_cits}
            for c in fact.get("citations", []):
                cid = c.get("citation_id") or c.get("document_id") or c.get("resource_id")
                if cid and cid not in seen_cids:
                    seen_cids.add(cid)
                    existing_cits.append(c)
            existing["citations"] = existing_cits

    return consolidated


def _structured_facts(packet: dict[str, Any], tenant_id: str) -> list[dict[str, Any]]:
    raw_facts = [
        *_flag_facts(packet, tenant_id),
        *_condition_facts(packet, tenant_id),
        *_current_medication_facts(packet, tenant_id),
        *_trend_facts(packet, tenant_id),
        *_timeline_facts(packet, tenant_id),
        *_uploaded_fhir_facts(packet, tenant_id),
        *_pdf_structured_facts(packet, tenant_id),
    ]
    return _consolidate_structured_facts(raw_facts)


def _uploaded_fhir_facts(packet: dict[str, Any], tenant_id: str) -> list[dict[str, Any]]:
    """Copy already-canonical uploaded FHIR evidence into locked request scope."""
    patient_id = str(packet.get("patient_id", ""))
    facts: list[dict[str, Any]] = []
    for raw_item in packet.get("fhir_evidence", []):
        item = _mapping(raw_item)
        if str(item.get("patient_id", patient_id)) != patient_id:
            continue
        citations = _citations(item.get("citations", []))
        if not citations:
            continue
        copied = dict(item)
        copied["tenant_id"] = tenant_id
        copied["patient_id"] = patient_id
        copied["citations"] = citations
        facts.append(copied)
    return facts


def _pdf_structured_facts(packet: dict[str, Any], tenant_id: str) -> list[dict[str, Any]]:
    """Extract verified PDF evidence items from the packet for structured_facts."""
    patient_id = str(packet.get("patient_id", ""))
    facts: list[dict[str, Any]] = []
    for raw_item in packet.get("pdf_evidence", []):
        item = _mapping(raw_item)
        if item.get("verification_status") != "verified":
            continue
        item_patient = str(item.get("patient_id", patient_id))
        if item_patient != patient_id:
            continue
        citations = _citations(item.get("citations", []))
        if not citations:
            continue
        facts.append({
            "evidence_id": item.get("evidence_id", ""),
            "tenant_id": tenant_id,
            "patient_id": patient_id,
            "fact_type": item.get("fact_type", "pdf_text_block"),
            "normalized_value": item.get("normalized_value", {}),
            "source_value": item.get("source_value", {}),
            "source_time": item.get("source_time"),
            "verification_status": "verified",
            "citations": citations,
            "record_status": item.get("record_status"),
        })
    return facts


def _pdf_note_evidence(packet: dict[str, Any], tenant_id: str) -> list[dict[str, Any]]:
    """Extract needs_verification PDF evidence items for note_evidence."""
    patient_id = str(packet.get("patient_id", ""))
    items: list[dict[str, Any]] = []
    for raw_item in packet.get("pdf_evidence", []):
        item = _mapping(raw_item)
        if item.get("verification_status") != "needs_verification":
            continue
        item_patient = str(item.get("patient_id", patient_id))
        if item_patient != patient_id:
            continue
        citations = _citations(item.get("citations", []))
        if not citations:
            continue
        items.append({
            "evidence_id": item.get("evidence_id", ""),
            "fact_type": item.get("fact_type", "pdf_text_block"),
            "normalized_value": item.get("normalized_value", {}),
            "source_value": item.get("source_value", {}),
            "source_time": item.get("source_time"),
            "verification_status": "needs_verification",
            "citations": citations,
        })
    return items
