"""Demo MVP v1 repository handling baseline data loading, canonical mapping, OCR items, reviews, memory, and audit logs."""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agents.contracts import AgentResult
from src.clinical.calculation import (
    convert_unit,
    format_display_value,
)
from src.clinical.canonical import (
    ConflictFlag,
    Coverage,
    DataQualityFlag,
    DocumentCitation,
    DrugInteractionFlag,
    FhirCitation,
    MemoryItem,
    PatientMemory,
    PatientSummary,
    ReviewResponse,
    ReviewSection,
    TimelineEvent,
    TrendPoint,
    VerificationItem,
)
from src.clinical.evidence_packet import EvidencePacket
from src.config import get_settings
from src.services.medication_safety import MedicationSafetyService


class DemoRepository:
    """In-memory & JSON backed repository for demo_mvp_v1 baseline dataset."""

    def __init__(
        self,
        data_dir: str | Path | None = None,
        state_path: str | Path | None = None,
    ):
        if data_dir is None:
            data_dir = get_settings().demo_data_dir
        self.data_dir = Path(data_dir)
        self.state_path = Path(state_path) if state_path else None

        self._patients: dict[str, PatientSummary] = {}
        self._bundles: dict[str, dict[str, Any]] = {}
        self._verification_items: dict[str, VerificationItem] = {}
        self._reviews: dict[str, list[ReviewResponse]] = {}  # patient_id -> list of review versions
        self._memories: dict[str, list[PatientMemory]] = {}   # patient_id -> list of memory versions
        self._audit_logs: list[dict[str, Any]] = []
        self._watermarks: dict[str, str] = {}
        # PDF evidence: patient_id -> list of canonical evidence item dicts with DocumentCitation
        self._pdf_evidence: dict[str, list[dict[str, Any]]] = {}
        # Canonical evidence from FHIR Bundles uploaded during this runtime.
        self._uploaded_fhir_evidence: dict[str, list[dict[str, Any]]] = {}
        # PDF verification items from low-confidence OCR
        self._pdf_verification_items: dict[str, list[dict[str, Any]]] = {}
        self._conflicts: dict[str, list[dict[str, Any]]] = {}
        self.med_safety = MedicationSafetyService()

        self._load_baseline()
        self._load_review_state()

    def _load_review_state(self) -> None:
        """Restore clinician review approvals for the persistent demo runtime."""
        if self.state_path is None or not self.state_path.is_file():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            reviews = payload.get("reviews", {})
            memories = payload.get("memories", {})
            self._reviews = {
                patient_id: [ReviewResponse.model_validate(item) for item in items]
                for patient_id, items in reviews.items()
                if patient_id in self._patients and isinstance(items, list)
            }
            self._memories = {
                patient_id: [PatientMemory.model_validate(item) for item in items]
                for patient_id, items in memories.items()
                if patient_id in self._patients and isinstance(items, list)
            }
        except (OSError, ValueError, TypeError):
            self._reviews = {}
            self._memories = {}

    def _persist_review_state(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "reviews": {
                patient_id: [review.model_dump(mode="json") for review in reviews]
                for patient_id, reviews in self._reviews.items()
            },
            "memories": {
                patient_id: [memory.model_dump(mode="json") for memory in memories]
                for patient_id, memories in self._memories.items()
            },
        }
        temporary = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.state_path)

    def _load_baseline(self) -> None:
        manifest_path = self.data_dir / "dataset_manifest.json"
        if not manifest_path.exists():
            return

        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        for p_info in manifest.get("patients", []):
            p_id = p_info["patient_id"]
            bundle_rel = p_info.get("fhir_bundle")
            bundle_path = self.data_dir / bundle_rel if bundle_rel else None

            wm = f"wm_{p_id}_v1"
            self._watermarks[p_id] = wm

            name = "Bệnh nhân Demo"
            gender = "female"
            age = 58
            primary_condition: str | None = None
            last_encounter_at: str | None = None
            if bundle_path and bundle_path.exists():
                with open(bundle_path, encoding="utf-8") as bf:
                    b_data = json.load(bf)
                    self._bundles[p_id] = b_data
                    for entry in b_data.get("entry", []):
                        res = entry.get("resource", {})
                        if res.get("resourceType") == "Patient":
                            gender = res.get("gender", "unknown")
                            if res.get("name"):
                                name = res["name"][0].get("text", name)
                            bdate = res.get("birthDate")
                            if bdate:
                                try:
                                    byear = int(bdate.split("-")[0])
                                    age = datetime.now().year - byear
                                except Exception:
                                    pass
                        elif res.get("resourceType") == "Condition" and primary_condition is None:
                            clinical_codes = {
                                str(coding.get("code", "")).casefold()
                                for coding in res.get("clinicalStatus", {}).get("coding", [])
                            }
                            if not clinical_codes.intersection({"inactive", "resolved", "remission"}):
                                codeable = res.get("code", {})
                                codings = codeable.get("coding", [])
                                primary_condition = codeable.get("text") or (
                                    codings[0].get("display") if codings else None
                                )
                        elif res.get("resourceType") == "Encounter":
                            started_at = res.get("period", {}).get("start")
                            if started_at and (last_encounter_at is None or started_at > last_encounter_at):
                                last_encounter_at = started_at

            self._patients[p_id] = PatientSummary(
                patient_id=p_id,
                pseudonym=name,
                age=age,
                sex=gender if gender in ("male", "female", "other", "unknown") else "unknown",
                primary_condition=primary_condition or "Chưa có dữ liệu",
                last_encounter_at=last_encounter_at,
                latest_data_watermark=wm,
            )

        # Load default OCR items if gold/ocr.json exists
        gold_ocr = self.data_dir / "gold" / "ocr.json"
        if gold_ocr.exists():
            try:
                with open(gold_ocr, encoding="utf-8") as f:
                    ocr_data = json.load(f)
                    for item in ocr_data.get("verification_items", []):
                        v_id = item["verification_item_id"]
                        self._verification_items[v_id] = VerificationItem(
                            verification_item_id=v_id,
                            document_id=item.get("document_id", "DOC-001"),
                            page_number=item.get("page_number", 1),
                            block_id=item.get("block_id"),
                            bbox=item.get("bbox"),
                            extracted_text=item.get("extracted_text", ""),
                            corrected_text=item.get("corrected_text"),
                            confidence=item.get("confidence", 0.75),
                            status=item.get("status", "pending"),
                        )
            except Exception:
                pass

        # Load baseline conflicts if gold/conflicts.json exists
        gold_conflicts = self.data_dir / "gold" / "conflicts.json"
        if gold_conflicts.exists():
            try:
                with open(gold_conflicts, encoding="utf-8") as f:
                    c_data = json.load(f)
                    for case in c_data.get("cases", []):
                        p_id = case.get("patient_id")
                        c_id = case.get("case_id", f"CONFLICT-{p_id}")
                        raw_status = str(case.get("status", "open"))
                        self._conflicts.setdefault(p_id, []).append({
                            "conflict_id": c_id,
                            "conflict_type": case.get("conflict_type") or case.get("type", "medication_dose_conflict"),
                            "description": "Liều Metformin đang mâu thuẫn: FHIR ghi 500 mg, trong khi tài liệu ghi 850 mg.",
                            "source_a": [{
                                "citation_id": "PAT-003-MED-001",
                                "source_type": "canonical_record",
                                "source_record_id": "PAT-003-MED-001",
                                "source_time": "2025-03-20",
                                "snippet": "Metformin 500 MG; 500 mg twice daily"
                            }],
                            "source_b": [{
                                "citation_id": "DOC-PAT003-RX-001",
                                "source_type": "pdf",
                                "document_id": "DOC-PAT003-RX-001",
                                "document_name": "PAT-003_prescription_conflict.pdf",
                                "page_number": 1,
                                "block_id": "rx-metformin",
                                "snippet": "Metformin 850 mg",
                                "source_checksum": "a3db17359c3b2039946fcd1a2ad10887936de545e223a9c148e1435b0b2e7c54",
                                "extraction_version": "1.0.0"
                            }],
                            # Gold fixtures cũ dùng ``unresolved`` trong khi contract
                            # công khai dùng ``open``. Chuẩn hóa ngay tại biên nạp dữ
                            # liệu để PAT-003 không bị hiểu nhầm thành lỗi patient scope.
                            "status": "open" if raw_status == "unresolved" else raw_status,
                        })
            except Exception:
                pass

    def get_patient(self, patient_id: str) -> PatientSummary | None:
        if patient_id in self._patients:
            return self._patients[patient_id]
        return self.find_patient_by_identifier_or_name(patient_id, patient_id)

    def create_blank_patient(self, patient_id: str, pseudonym: str = "Bệnh nhân mới") -> PatientSummary:
        """Dynamically register a new patient in runtime repository."""
        pat = PatientSummary(
            patient_id=patient_id,
            pseudonym=pseudonym,
            age=52,
            sex="unknown",
            primary_condition="Chưa có dữ liệu",
            last_encounter_at=datetime.now().strftime("%Y-%m-%dT08:00:00+07:00"),
            latest_data_watermark=f"wm_{patient_id}_{uuid.uuid4().hex[:6]}",
        )
        self._patients[patient_id] = pat
        self._bundles.setdefault(patient_id, {"resourceType": "Bundle", "type": "collection", "entry": []})
        return pat

    def find_patient_by_identifier_or_name(self, identifier: str | None, name: str | None = None) -> PatientSummary | None:
        """Find an existing patient by patient_id or matching pseudonym/name (accent-insensitive)."""
        import unicodedata

        def _norm(s: str) -> str:
            s = unicodedata.normalize("NFKD", s)
            return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()

        # 1. Try matching by identifier
        if identifier:
            clean_id = identifier.strip().upper().replace("PAT", "PAT-").replace("--", "-")
            if clean_id in self._patients:
                return self._patients[clean_id]
            norm_id = _norm(identifier)
            for p_id, pat in self._patients.items():
                if norm_id in _norm(p_id) or _norm(p_id) in norm_id:
                    return pat
                if norm_id in _norm(pat.pseudonym) or _norm(pat.pseudonym) in norm_id:
                    return pat

        # 2. Try matching by name
        if name:
            norm_name = _norm(name)
            if len(norm_name) >= 2:
                for pat in self._patients.values():
                    pat_norm = _norm(pat.pseudonym)
                    if norm_name in pat_norm or pat_norm in norm_name:
                        return pat

        return None



    def create_blank_patient(self, patient_id: str, name: str) -> PatientSummary:
        patient = PatientSummary(
            patient_id=patient_id,
            pseudonym=name,
            sex="unknown",
            age=None,
            primary_condition="Chưa có dữ liệu",
            last_encounter_at=None,
            latest_data_watermark=self.get_watermark(patient_id),
        )
        self._patients[patient_id] = patient
        return patient

    def delete_patient(self, patient_id: str) -> bool:
        """Deletes the patient and all associated state from the repository.
        Returns True if the patient existed and was deleted, False otherwise.
        Note: Baseline patients will reappear if the repository is reloaded.
        """
        if patient_id not in self._patients:
            return False

        self._patients.pop(patient_id, None)
        self._bundles.pop(patient_id, None)
        self._reviews.pop(patient_id, None)
        self._memories.pop(patient_id, None)
        self._persist_review_state()
        self._pdf_evidence.pop(patient_id, None)
        self._uploaded_fhir_evidence.pop(patient_id, None)
        self._watermarks.pop(patient_id, None)

        pdf_verif = self._pdf_verification_items.pop(patient_id, [])
        for v in pdf_verif:
            v_id = v.get("verification_item_id")
            if v_id:
                self._verification_items.pop(v_id, None)

        return True

    def list_patients(self, search: str | None = None, page: int = 1, page_size: int = 20) -> tuple[list[PatientSummary], int]:
        items = list(self._patients.values())
        if search:
            s = search.lower()
            items = [p for p in items if s in p.patient_id.lower() or s in p.pseudonym.lower()]
        total = len(items)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    def get_watermark(self, patient_id: str) -> str:
        return self._watermarks.get(patient_id, f"wm_{patient_id}_v1")

    def update_watermark(self, patient_id: str) -> str:
        new_wm = f"wm_{patient_id}_{uuid.uuid4().hex[:6]}"
        self._watermarks[patient_id] = new_wm
        if patient_id in self._patients:
            self._patients[patient_id].latest_data_watermark = new_wm
        return new_wm

    # Verification Items
    def list_verification_items(
        self, patient_id: str, status: str | None = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[VerificationItem], int]:
        items = list(self._verification_items.values())
        if status:
            items = [item for item in items if item.status == status]
        total = len(items)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    def update_verification_item(
        self, item_id: str, decision: str, corrected_text: str | None = None
    ) -> tuple[VerificationItem, str]:
        item = self._verification_items.get(item_id)
        if not item:
            raise KeyError(f"Verification item {item_id} not found")

        item.status = decision  # type: ignore
        if corrected_text is not None:
            item.corrected_text = corrected_text

        # Find patient for this doc and bump watermark
        patient_id = "PAT-003"  # default baseline patient for OCR
        new_wm = self.update_watermark(patient_id)
        return item, new_wm

    # Timeline & Trends
    def get_timeline(self, patient_id: str) -> list[TimelineEvent]:
        bundle = self._bundles.get(patient_id, {})
        raw_events: list[TimelineEvent] = []

        for entry in bundle.get("entry", []):
            res = entry.get("resource", {})
            r_type = res.get("resourceType")
            if str(res.get("status", "")).casefold() == "entered-in-error":
                continue
            r_id = res.get("id", "res_1")
            meta = res.get("meta", {}) if isinstance(res.get("meta"), dict) else {}
            src_type = meta.get("source_type") or "fhir"
            doc_id = meta.get("document_id") or f"DOC-{patient_id}-FHIR"
            doc_name = meta.get("document_name") or f"Ho_So_{patient_id}.json"

            if src_type in ("pdf", "ocr"):
                cit = DocumentCitation(
                    citation_id=f"cit_{r_id}",
                    source_type=src_type,
                    document_id=doc_id,
                    document_name=doc_name,
                    page_number=1,
                    block_id=r_id,
                    snippet=json.dumps(res, ensure_ascii=False)[:100],
                    source_checksum="sha256:baseline",
                )
            else:
                cit = FhirCitation(
                    citation_id=f"cit_{r_id}",
                    document_id=doc_id,
                    resource_type=r_type,
                    resource_id=r_id,
                    snippet=json.dumps(res, ensure_ascii=False)[:100],
                    source_checksum="sha256:baseline",
                )

            if r_type == "Encounter":
                raw_events.append(
                    TimelineEvent(
                        event_id=f"evt_{r_id}",
                        event_type="encounter",
                        occurred_at=res.get("period", {}).get("start", "2026-01-01T08:00:00+07:00"),
                        title=f"Lượt khám {res.get('type', [{}])[0].get('text', 'Tái khám')}",
                        summary=f"Trạng thái: {res.get('status', 'finished')}",
                        citations=[cit],
                    )
                )
            elif r_type == "Observation":
                code_text = res.get("code", {}).get("text") or res.get("code", {}).get("coding", [{}])[0].get("display", "Xét nghiệm")
                val = res.get("valueQuantity", {}).get("value")
                unit = res.get("valueQuantity", {}).get("unit", "")
                raw_num = float(val) if val is not None and isinstance(val, (int, float, str)) and str(val).replace(".", "", 1).isdigit() else None
                disp_val = f"{int(raw_num) if raw_num is not None and raw_num.is_integer() else raw_num} {unit}".strip() if raw_num is not None else f"{val} {unit}".strip()
                raw_events.append(
                    TimelineEvent(
                        event_id=f"evt_{r_id}",
                        event_type="observation",
                        occurred_at=res.get("effectiveDateTime", "2026-01-01T08:00:00+07:00"),
                        title=f"Xét nghiệm: {code_text}",
                        summary=f"Kết quả: {disp_val}".strip(),
                        citations=[cit],
                    )
                )
            elif r_type in ("MedicationStatement", "MedicationRequest"):
                med_name = res.get("medicationCodeableConcept", {}).get("text") or "Thuốc"
                raw_events.append(
                    TimelineEvent(
                        event_id=f"evt_{r_id}",
                        event_type="medication",
                        occurred_at=res.get("effectiveDateTime") or res.get("authoredOn") or "2026-01-01T08:00:00+07:00",
                        title=f"Thuốc: {med_name}",
                        summary=f"Trạng thái: {res.get('status', 'active')}",
                        citations=[cit],
                    )
                )

        # Merge duplicates across multi-source extractions while consolidating citations
        merged_events: dict[tuple[str, str, str, str], TimelineEvent] = {}
        for ev in raw_events:
            dt_key = str(ev.occurred_at)[:10]
            norm_title = re.sub(r"\s+", " ", ev.title.casefold().strip())
            norm_summary = re.sub(r"(\d+)\.0(?=\s|$|[^\d])", r"\1", ev.summary.casefold().strip())
            norm_summary = re.sub(r"\s+", " ", norm_summary)
            key = (ev.event_type, dt_key, norm_title, norm_summary)
            if key not in merged_events:
                merged_events[key] = ev
            else:
                existing = merged_events[key]
                seen_cids = {c.citation_id for c in existing.citations}
                for c in ev.citations:
                    if c.citation_id not in seen_cids:
                        seen_cids.add(c.citation_id)
                        existing.citations.append(c)

        events = list(merged_events.values())
        events.sort(key=lambda e: e.occurred_at, reverse=True)
        return events

    def get_trends(self, patient_id: str, code: str) -> tuple[str, str, list[TrendPoint]]:
        bundle = self._bundles.get(patient_id, {})
        merged_points: dict[tuple[str, str, str], dict[str, Any]] = {}

        if code == "4548-4":
            display_name = "HbA1c"
            target_unit = "%"
        elif code == "2339-0":
            display_name = "Glucose"
            target_unit = "mmol/L"
        elif code == "2160-0":
            display_name = "Creatinine"
            target_unit = "µmol/L"
        elif code == "33914-3":
            display_name = "eGFR"
            target_unit = "mL/min/1.73m2"
        elif code == "8480-6":
            display_name = "BP Systolic"
            target_unit = "mmHg"
        elif code == "8462-4":
            display_name = "BP Diastolic"
            target_unit = "mmHg"
        else:
            display_name = code
            target_unit = ""

        for entry in bundle.get("entry", []):
            res = entry.get("resource", {})
            if res.get("resourceType") == "Observation":
                if str(res.get("status", "")).casefold() == "entered-in-error":
                    continue
                codings = res.get("code", {}).get("coding", [])
                matched = any(c.get("code") == code for c in codings) or code.lower() in (res.get("code", {}).get("text") or "").lower()
                if matched:
                    raw_v = res.get("valueQuantity", {}).get("value")
                    raw_u = res.get("valueQuantity", {}).get("unit", "")
                    t_str = res.get("effectiveDateTime", "2026-01-01T08:00:00+07:00")
                    r_id = res.get("id", "res_obs")
                    meta = res.get("meta", {}) if isinstance(res.get("meta"), dict) else {}
                    src_type = meta.get("source_type") or "fhir"
                    doc_id = meta.get("document_id") or f"DOC-{patient_id}-FHIR"
                    doc_name = meta.get("document_name") or f"Ho_So_{patient_id}.json"

                    if src_type in ("pdf", "ocr"):
                        cit = DocumentCitation(
                            citation_id=f"cit_{r_id}",
                            source_type=src_type,
                            document_id=doc_id,
                            document_name=doc_name,
                            page_number=1,
                            block_id=r_id,
                            snippet=f"{display_name}: {raw_v} {raw_u}",
                            source_checksum="sha256:baseline",
                        )
                    else:
                        cit = FhirCitation(
                            citation_id=f"cit_{r_id}",
                            document_id=doc_id,
                            resource_type="Observation",
                            resource_id=r_id,
                            snippet=f"{display_name}: {raw_v} {raw_u}",
                            source_checksum="sha256:baseline",
                        )

                    if raw_v is not None:
                        canonical_val, scale, unit, prov = convert_unit(raw_v, code, raw_u, target_unit, [cit.citation_id])
                        disp_val = format_display_value(canonical_val, scale)
                        ref_map = {
                            "4548-4": {"low": None, "high": 7.0},
                            "2339-0": {"low": 3.9, "high": 7.0},
                            "2160-0": {"low": 44.0, "high": 106.0},
                            "33914-3": {"low": 60.0, "high": None},
                            "8480-6": {"low": 90.0, "high": 140.0},
                        }
                        dt_key = str(t_str)[:10]
                        pt_key = (dt_key, str(disp_val), str(unit))
                        if pt_key not in merged_points:
                            merged_points[pt_key] = {
                                "observed_at": t_str,
                                "value": disp_val,
                                "unit": unit,
                                "raw_value": float(raw_v),
                                "raw_unit": raw_u,
                                "calculation": prov.to_dict() if prov else None,
                                "reference_range": ref_map.get(code, {"low": None, "high": None}),
                                "citations": [cit],
                            }
                        else:
                            existing = merged_points[pt_key]
                            seen_cids = {c.citation_id for c in existing["citations"]}
                            if cit.citation_id not in seen_cids:
                                existing["citations"].append(cit)

        points = list(merged_points.values())
        points.sort(key=lambda x: x["observed_at"])
        trend_points = [TrendPoint(**p) for p in points]
        return display_name, target_unit, trend_points

    def add_pdf_evidence(
        self,
        patient_id: str,
        document_id: str,
        evidence_items: list[dict[str, Any]],
        verification_items: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add canonicalized PDF evidence for a specific patient.

        Patient isolation: each evidence item must belong to patient_id.
        Cross-patient evidence is silently rejected (fail-closed).
        Reviews that are not yet approved are marked stale automatically.
        """
        if patient_id not in self._patients:
            raise KeyError(f"Patient {patient_id} not found")

        safe_items: list[dict[str, Any]] = []
        for item in evidence_items:
            item_patient = str(item.get("patient_id", patient_id))
            # Reject cross-patient evidence — fail closed
            if item_patient != patient_id:
                continue
            safe_items.append(item)

        if safe_items:
            self._pdf_evidence.setdefault(patient_id, []).extend(safe_items)

        if verification_items:
            self._pdf_verification_items.setdefault(patient_id, []).extend(verification_items)
            for v in verification_items:
                v_id = v["verification_item_id"]
                self._verification_items[v_id] = VerificationItem(
                    verification_item_id=v_id,
                    document_id=v.get("document_id", document_id),
                    page_number=v.get("page_number", 1),
                    block_id=v.get("block_id"),
                    bbox=v.get("bbox"),
                    extracted_text=v.get("extracted_text", ""),
                    corrected_text=v.get("corrected_text"),
                    confidence=v.get("confidence", 0.5),
                    status=v.get("status", "pending"),
                )

    def add_fhir_evidence(
        self,
        patient_id: str,
        evidence_items: list[dict[str, Any]],
        raw_bundle: dict[str, Any] | None = None,
    ) -> None:
        """Merge uploaded FHIR evidence into runtime state without replacing baseline Bundle data."""
        if patient_id not in self._patients:
            raise KeyError(f"Patient {patient_id} not found")
        safe_items = [
            item for item in evidence_items
            if str(item.get("patient_id", patient_id)) == patient_id
        ]
        if len(safe_items) != len(evidence_items):
            raise ValueError("FHIR evidence contains a foreign patient scope.")
        self._uploaded_fhir_evidence.setdefault(patient_id, []).extend(safe_items)

        # Merge raw bundle entries into self._bundles so timeline, trends & medications appear
        if raw_bundle and isinstance(raw_bundle, dict):
            bundle = self._bundles.setdefault(patient_id, {"resourceType": "Bundle", "type": "collection", "entry": []})
            entries = bundle.setdefault("entry", [])
            for new_entry in raw_bundle.get("entry", []):
                if isinstance(new_entry, dict) and new_entry not in entries:
                    entries.append(new_entry)

    def add_parsed_clinical_document(
        self,
        patient_id: str,
        parsed_doc: Any,
        document_id: str,
        document_name: str,
    ) -> None:
        """Ingest parsed clinical observations, timeline encounters, and conditions into the patient's FHIR bundle."""
        if patient_id not in self._patients:
            raise KeyError(f"Patient {patient_id} not found")

        doc_date = getattr(parsed_doc, "document_date", None) or datetime.now().strftime("%Y-%m-%d")
        occurred_iso = f"{doc_date}T08:00:00+07:00"

        doc_ext = (document_name or "").lower()
        src_type = "ocr" if doc_ext.endswith((".jpg", ".png", ".jpeg")) else "pdf"
        meta_info = {
            "source_type": src_type,
            "document_name": document_name,
            "document_id": document_id,
        }

        bundle = self._bundles.setdefault(patient_id, {"resourceType": "Bundle", "type": "collection", "entry": []})
        entries = bundle.setdefault("entry", [])

        # 1. Add Encounter entry if not duplicate
        enc_id = f"enc_{document_id}"
        enc_title = getattr(parsed_doc, "document_title", None) or "Phiếu kết quả xét nghiệm"
        enc_resource = {
            "resourceType": "Encounter",
            "id": enc_id,
            "status": "finished",
            "type": [{"text": enc_title}],
            "period": {"start": occurred_iso, "end": occurred_iso},
            "meta": meta_info,
        }
        has_duplicate_enc = any(
            isinstance(e, dict)
            and e.get("resource", {}).get("resourceType") == "Encounter"
            and str(e.get("resource", {}).get("period", {}).get("start", ""))[:10] == occurred_iso[:10]
            and str(e.get("resource", {}).get("type", [{}])[0].get("text", "")).casefold() == enc_title.casefold()
            for e in entries
        )
        if not has_duplicate_enc:
            entries.append({"resource": enc_resource})

        # 2. Add Observation entries if not duplicate
        observations = getattr(parsed_doc, "observations", [])
        for idx, obs in enumerate(observations):
            obs_id = f"obs_{document_id}_{idx}"
            obs_name = getattr(obs, "name", "Xét nghiệm")
            obs_code = getattr(obs, "code", "unknown")
            obs_val = getattr(obs, "value", None)
            obs_unit = getattr(obs, "unit", "")
            obs_flag = getattr(obs, "flag", None)

            obs_resource = {
                "resourceType": "Observation",
                "id": obs_id,
                "status": "final",
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": obs_code, "display": obs_name}],
                    "text": obs_name,
                },
                "valueQuantity": {
                    "value": obs_val,
                    "unit": obs_unit,
                },
                "effectiveDateTime": occurred_iso,
                "meta": meta_info,
            }
            if obs_flag:
                obs_resource["interpretation"] = [{"text": obs_flag}]

            has_duplicate_obs = any(
                isinstance(e, dict)
                and e.get("resource", {}).get("resourceType") == "Observation"
                and str(e.get("resource", {}).get("effectiveDateTime", ""))[:10] == occurred_iso[:10]
                and str(e.get("resource", {}).get("code", {}).get("text", "")).casefold() == obs_name.casefold()
                and str(e.get("resource", {}).get("valueQuantity", {}).get("value")) == str(obs_val)
                for e in entries
            )
            if not has_duplicate_obs:
                entries.append({"resource": obs_resource})

        # 3. Add Condition entries if not duplicate
        conditions = getattr(parsed_doc, "conditions", [])
        for idx, cond in enumerate(conditions):
            cond_id = f"cond_{document_id}_{idx}"
            cond_name = getattr(cond, "name", "Chẩn đoán")
            cond_code = getattr(cond, "code", None)
            cond_date = getattr(cond, "recorded_date", None) or doc_date

            cond_resource = {
                "resourceType": "Condition",
                "id": cond_id,
                "clinicalStatus": {"coding": [{"code": "active"}]},
                "code": {
                    "coding": [{"system": "http://snomed.info/sct", "code": cond_code or "unknown", "display": cond_name}],
                    "text": cond_name,
                },
                "recordedDate": f"{cond_date}T08:00:00+07:00",
                "meta": meta_info,
            }
            has_duplicate_cond = any(
                isinstance(e, dict)
                and e.get("resource", {}).get("resourceType") == "Condition"
                and str(e.get("resource", {}).get("code", {}).get("text", "")).casefold() == cond_name.casefold()
                for e in entries
            )
            if not has_duplicate_cond:
                entries.append({"resource": cond_resource})

        # 4. Add MedicationRequest entries if not duplicate
        medications = getattr(parsed_doc, "medications", [])
        for idx, med in enumerate(medications):
            med_id = f"med_{document_id}_{idx}"
            med_name = getattr(med, "name", "Thuốc điều trị")
            med_dose = getattr(med, "dose", None)

            med_resource = {
                "resourceType": "MedicationRequest",
                "id": med_id,
                "status": "active",
                "intent": "order",
                "medicationCodeableConcept": {
                    "coding": [{"display": med_name}],
                    "text": med_name,
                },
                "authoredOn": occurred_iso,
                "meta": meta_info,
            }
            if med_dose:
                med_resource["dosageInstruction"] = [{"text": med_dose}]

            has_duplicate_med = any(
                isinstance(e, dict)
                and e.get("resource", {}).get("resourceType") == "MedicationRequest"
                and str(e.get("resource", {}).get("medicationCodeableConcept", {}).get("text", "")).casefold() == med_name.casefold()
                and str(e.get("resource", {}).get("authoredOn", ""))[:10] == occurred_iso[:10]
                for e in entries
            )
            if not has_duplicate_med:
                entries.append({"resource": med_resource})

        # 5. Update patient summary
        pat = self._patients.get(patient_id)
        if pat:
            pat.last_encounter_at = occurred_iso
            if conditions and (pat.primary_condition == "Chưa có dữ liệu" or not pat.primary_condition):
                cond_names = [str(getattr(c, "name", "") or "") for c in conditions if getattr(c, "name", "")]
                pat.primary_condition = ", ".join(cond_names) if cond_names else str(getattr(conditions[0], "name", pat.primary_condition))
            if getattr(parsed_doc, "birth_date", None):
                try:
                    byear = int(str(parsed_doc.birth_date).split("-")[0])
                    pat.age = datetime.now().year - byear
                except Exception:
                    pass
            if getattr(parsed_doc, "gender", None) and parsed_doc.gender in ("male", "female"):
                pat.sex = parsed_doc.gender


    def mark_reviews_stale(self, patient_id: str) -> int:
        """Mark all non-approved reviews for a patient as stale. Returns count marked."""
        revs = self._reviews.get(patient_id, [])
        count = 0
        for rev in revs:
            if rev.status not in {"approved", "stale"}:
                rev.status = "stale"  # type: ignore[assignment]
                count += 1
        if count:
            self._persist_review_state()
        return count

    @staticmethod
    def _codeable_text(codeable: Any, default: str) -> str:
        if not isinstance(codeable, dict):
            return default
        text = str(codeable.get("text") or "").strip()
        if text:
            return text
        codings = codeable.get("coding") or []
        if codings and isinstance(codings[0], dict):
            return str(codings[0].get("display") or codings[0].get("code") or default)
        return default

    def _clinical_resource_records(self, patient_id: str) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
        """Return patient-scoped FHIR resources with their provenance citations."""
        records: dict[tuple[str, str], tuple[dict[str, Any], list[dict[str, Any]]]] = {}
        for entry in self._bundles.get(patient_id, {}).get("entry", []):
            resource = entry.get("resource", {}) if isinstance(entry, dict) else {}
            if not isinstance(resource, dict) or not resource.get("resourceType"):
                continue
            resource_type = str(resource["resourceType"])
            resource_id = str(resource.get("id") or f"resource-{len(records) + 1}")
            meta = resource.get("meta", {}) if isinstance(resource.get("meta"), dict) else {}
            doc_id = meta.get("document_id") or f"DOC-{patient_id}-FHIR"
            doc_name = meta.get("document_name") or f"Ho_So_{patient_id}.json"
            src_type = meta.get("source_type") or "fhir"

            if src_type in ("pdf", "ocr"):
                citation = DocumentCitation(
                    citation_id=f"cit_{resource_id}",
                    source_type=src_type,
                    document_id=doc_id,
                    document_name=doc_name,
                    page_number=1,
                    block_id=resource_id,
                    snippet=json.dumps(resource, ensure_ascii=False)[:200],
                    source_checksum="sha256:baseline",
                ).model_dump(mode="json")
                records[(resource_type, resource_id)] = (resource, [citation])
            else:
                fhir_cit = FhirCitation(
                    citation_id=f"cit_{resource_id}",
                    document_id=doc_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    snippet=json.dumps(resource, ensure_ascii=False)[:200],
                    source_checksum="sha256:baseline",
                ).model_dump(mode="json")
                records[(resource_type, resource_id)] = (resource, [fhir_cit])

        # Uploaded FHIR is already canonicalized and scope-checked. Prefer the
        # uploaded version if it intentionally replaces a resource with the same id.
        for item in self._uploaded_fhir_evidence.get(patient_id, []):
            source_value = item.get("source_value", {}) if isinstance(item, dict) else {}
            resource = source_value.get("resource", {}) if isinstance(source_value, dict) else {}
            if not isinstance(resource, dict) or not resource.get("resourceType"):
                continue
            resource_type = str(resource["resourceType"])
            resource_id = str(resource.get("id") or item.get("evidence_id") or f"upload-{len(records) + 1}")
            citations = [dict(c) for c in item.get("citations", []) if isinstance(c, dict)]
            records[(resource_type, resource_id)] = (resource, citations)
        return list(records.values())

    def _active_conditions(self, patient_id: str) -> list[dict[str, Any]]:
        conditions: list[dict[str, Any]] = []
        for resource, citations in self._clinical_resource_records(patient_id):
            if resource.get("resourceType") != "Condition":
                continue
            clinical_codes = {
                str(coding.get("code", "")).casefold()
                for coding in resource.get("clinicalStatus", {}).get("coding", [])
                if isinstance(coding, dict)
            }
            if clinical_codes.intersection({"inactive", "resolved", "remission", "entered-in-error"}):
                continue
            codeable = resource.get("code", {})
            codings = codeable.get("coding", []) if isinstance(codeable, dict) else []
            conditions.append({
                "condition": self._codeable_text(codeable, "Chẩn đoán chưa đặt tên"),
                "code": str(codings[0].get("code") or "") if codings else None,
                "clinical_status": next(iter(clinical_codes), "active"),
                "recorded_at": resource.get("recordedDate") or resource.get("onsetDateTime"),
                "citations": citations,
            })
        conditions.sort(key=lambda item: str(item.get("recorded_at") or ""))
        return conditions

    def _current_medications(self, patient_id: str) -> list[dict[str, Any]]:
        medications: list[dict[str, Any]] = []
        active_statuses = {"active", "on-hold", "intended"}
        for resource, citations in self._clinical_resource_records(patient_id):
            resource_type = resource.get("resourceType")
            if resource_type not in {"MedicationRequest", "MedicationStatement"}:
                continue
            status = str(resource.get("status") or "unknown").casefold()
            if status not in active_statuses:
                continue
            instructions = resource.get("dosageInstruction") or resource.get("dosage") or []
            dosage_parts: list[str] = []
            for instruction in instructions:
                if not isinstance(instruction, dict):
                    continue
                text = str(instruction.get("text") or "").strip()
                if text:
                    dosage_parts.append(text)
            medications.append({
                "medication": self._codeable_text(resource.get("medicationCodeableConcept"), "Thuốc chưa đặt tên"),
                "status": status,
                "dosage": "; ".join(dosage_parts) or None,
                "recorded_at": (
                    resource.get("authoredOn")
                    or resource.get("effectiveDateTime")
                    or resource.get("dateAsserted")
                    or (resource.get("effectivePeriod") or {}).get("start")
                ),
                "resource_type": resource_type,
                "citations": citations,
            })
        medications.sort(key=lambda item: (str(item.get("recorded_at") or ""), item["medication"]))
        return medications

    def _allergies(self, patient_id: str) -> list[dict[str, Any]]:
        allergies: list[dict[str, Any]] = []
        for resource, citations in self._clinical_resource_records(patient_id):
            if resource.get("resourceType") != "AllergyIntolerance":
                continue
            status_codes = {
                str(coding.get("code", "")).casefold()
                for coding in resource.get("clinicalStatus", {}).get("coding", [])
                if isinstance(coding, dict)
            }
            if status_codes.intersection({"inactive", "resolved", "entered-in-error"}):
                continue
            reactions = []
            for reaction in resource.get("reaction", []):
                for manifestation in reaction.get("manifestation", []):
                    reactions.append(self._codeable_text(manifestation, "Phản ứng chưa mô tả"))
            allergies.append({
                "substance": self._codeable_text(resource.get("code"), "Dị ứng chưa đặt tên"),
                "reactions": reactions,
                "criticality": resource.get("criticality"),
                "citations": citations,
            })
        return allergies

    def _latest_observations(self, patient_id: str) -> list[dict[str, Any]]:
        observations_by_code: dict[str, list[dict[str, Any]]] = {}
        for resource, citations in self._clinical_resource_records(patient_id):
            if resource.get("resourceType") != "Observation":
                continue
            if str(resource.get("status") or "").casefold() in {"entered-in-error", "cancelled"}:
                continue
            codeable = resource.get("code", {})
            codings = codeable.get("coding", []) if isinstance(codeable, dict) else []
            code = str(codings[0].get("code") or "") if codings else self._codeable_text(codeable, "unknown")
            quantity = resource.get("valueQuantity") or {}
            if quantity.get("value") is None:
                continue
            observations_by_code.setdefault(code, []).append({
                "code": code,
                "display": self._codeable_text(codeable, code),
                "value": quantity.get("value"),
                "unit": quantity.get("unit") or quantity.get("code") or "",
                "observed_at": resource.get("effectiveDateTime") or resource.get("issued"),
                "citations": citations,
            })

        latest: list[dict[str, Any]] = []
        for points in observations_by_code.values():
            points.sort(key=lambda item: str(item.get("observed_at") or ""))
            current = dict(points[-1])
            if len(points) > 1:
                previous = points[-2]
                current["previous_value"] = previous.get("value")
                current["previous_observed_at"] = previous.get("observed_at")
                try:
                    delta = float(current["value"]) - float(previous["value"])
                    current["trend"] = "increased" if delta > 0 else "decreased" if delta < 0 else "stable"
                except (TypeError, ValueError):
                    current["trend"] = "unknown"
            latest.append(current)
        latest.sort(key=lambda item: (str(item.get("display") or ""), str(item.get("code") or "")))
        return latest

    def build_evidence_packet(self, patient_id: str) -> EvidencePacket:
        """Build the locked C1 packet consumed by the C3 agent adapter."""
        if patient_id not in self._patients:
            raise KeyError(f"Patient {patient_id} not found")
        events = self.get_timeline(patient_id)
        # Keep the established C3-agent contract focused on the profiled HbA1c
        # series. Care-plan personalization reads all metrics from
        # latest_observations without inflating unrelated chat citations.
        trend_codes = ("4548-4",)
        lab_trends: dict[str, list[dict[str, Any]]] = {}
        for code in trend_codes:
            _, _, points = self.get_trends(patient_id, code)
            if points:
                lab_trends[code] = [point.model_dump(mode="json") for point in points]
        dates = sorted(event.occurred_at[:10] for event in events if event.occurred_at)
        pdf_evs = list(self._pdf_evidence.get(patient_id, []))
        pdf_doc_ids = list({
            str(cit.get("document_id"))
            for item in pdf_evs
            for cit in item.get("citations", [])
            if cit.get("document_id")
        })
        return EvidencePacket(
            patient_id=patient_id,
            data_watermark=self.get_watermark(patient_id),
            coverage_start=dates[0] if dates else None,
            coverage_end=dates[-1] if dates else None,
            encounter_count=sum(event.event_type == "encounter" for event in events),
            timeline=[event.model_dump(mode="json") for event in events],
            lab_trends=lab_trends,
            latest_observations=self._latest_observations(patient_id),
            active_conditions=self._active_conditions(patient_id),
            current_medications=self._current_medications(patient_id),
            allergies=self._allergies(patient_id),
            fhir_evidence=list(self._uploaded_fhir_evidence.get(patient_id, [])),
            conflicts=list(self._conflicts.get(patient_id, [])),
            drug_interactions=[],
            data_quality_flags=[],
            pdf_evidence=pdf_evs,
            pdf_document_ids=pdf_doc_ids,
        )

    # Reviews State Machine
    def get_review(self, patient_id: str, version: int | None = None, review_version_id: str | None = None) -> ReviewResponse | None:
        revs = self._reviews.get(patient_id, [])
        if not revs:
            return None

        if review_version_id:
            for r in revs:
                if r.review_version_id == review_version_id:
                    return r
            return None

        if version is not None:
            for r in revs:
                if r.version == version:
                    return r
            return None

        return revs[-1]  # Latest version

    def generate_review(
        self,
        patient_id: str,
        profile_versions: list[str],
        agent_result: AgentResult,
        evidence_packet: EvidencePacket,
    ) -> ReviewResponse:
        """Persist a contract-valid AgentResult without regenerating AI facts."""
        wm = self.get_watermark(patient_id)
        if evidence_packet.patient_id != patient_id or evidence_packet.data_watermark != wm:
            raise ValueError("Evidence packet is outside the locked patient/watermark scope.")
        if agent_result.task_type != "review_generation" or agent_result.data_watermark != wm:
            raise ValueError("AgentResult does not match the review generation watermark.")
        if agent_result.status not in {"answered", "conflicting"} or agent_result.sections is None:
            raise ValueError("AgentResult is not persistable as a generated review.")

        now_str = datetime.now().isoformat()
        rev_id = f"rev_{patient_id}"
        rv_id = f"rv_{uuid.uuid4().hex[:8]}"
        previous = self._reviews.get(patient_id, [])
        version = previous[-1].version + 1 if previous else 1
        sections = [ReviewSection.model_validate(section.model_dump(mode="json")) for section in agent_result.sections]

        review = ReviewResponse(
            review_id=rev_id,
            review_version_id=rv_id,
            patient_id=patient_id,
            status="generated",
            version=version,
            generated_at=now_str,
            updated_at=now_str,
            approved_at=None,
            data_watermark=wm,
            is_current_watermark=True,
            profile_versions=profile_versions,
            coverage=Coverage(
                start_date=evidence_packet.coverage_start,
                end_date=evidence_packet.coverage_end,
                encounter_count=evidence_packet.encounter_count,
            ),
            sections=sections,
            conflicts=[ConflictFlag.model_validate(item) for item in evidence_packet.conflicts],
            drug_interactions=[DrugInteractionFlag.model_validate(item) for item in evidence_packet.drug_interactions],
            data_quality_flags=[DataQualityFlag.model_validate(item) for item in evidence_packet.data_quality_flags],
            disclaimer="Tài liệu chỉ phục vụ rà soát lâm sàng. Bác sĩ chịu trách nhiệm cho mọi quyết định điều trị.",
            clinician_confirmation=None,
            memory_version_used=None,
        )

        self._reviews.setdefault(patient_id, []).append(review)
        self._persist_review_state()
        return review

    def patch_review(
        self, review_id: str, expected_version: int, sections: list[dict[str, Any]], reason: str | None = None
    ) -> ReviewResponse:
        patient_id = review_id.replace("rev_", "")
        revs = self._reviews.get(patient_id, [])
        if not revs:
            raise KeyError(f"Review {review_id} not found")

        current = revs[-1]
        if current.version != expected_version:
            from src.clinical.errors import ReviewPolicyError
            raise ReviewPolicyError("VERSION_CONFLICT")
        if current.status == "approved":
            from src.clinical.errors import ReviewPolicyError
            raise ReviewPolicyError("INVALID_TRANSITION")

        now_str = datetime.now().isoformat()
        new_version = current.version + 1
        new_rv_id = f"rv_{uuid.uuid4().hex[:8]}"

        updated_sections = []
        clinician_reviewed_conflict = False
        for sec in current.sections:
            sec_dict = sec.model_dump()
            for patch_sec in sections:
                if patch_sec.get("section_code") == sec.section_code:
                    if "clinician_text" in patch_sec:
                        sec_dict["clinician_text"] = patch_sec["clinician_text"]
                    if "claims" in patch_sec:
                        incoming_claims = {
                            str(item.get("claim_id")): item
                            for item in patch_sec.get("claims", [])
                            if isinstance(item, dict) and item.get("claim_id")
                        }
                        existing_ids = {claim.claim_id for claim in sec.claims}
                        incoming_claims = {
                            k: v for k, v in incoming_claims.items() if k in existing_ids
                        }
                        edited_claims = []
                        for claim in sec.claims:
                            incoming = incoming_claims.get(claim.claim_id)
                            if not incoming:
                                edited_claims.append(claim)
                                continue
                            text = str(incoming.get("text") or "").strip()
                            if not text or len(text) > 4000:
                                from src.clinical.errors import ReviewPolicyError
                                raise ReviewPolicyError("INVALID_CLAIM_EDIT")
                            if text == claim.text.strip():
                                edited_claims.append(claim)
                                continue
                            if not reason or len(reason.strip()) < 3:
                                reason = "Bác sĩ điều chỉnh thông tin lâm sàng"
                            # Bác sĩ chỉ gửi nội dung; trích dẫn gốc vẫn do server
                            # giữ để không thể giả mạo nguồn. Trạng thái verified
                            # dưới đây là xác nhận lâm sàng do server ghi nhận từ
                            # thao tác có lý do, không đọc trạng thái từ client.
                            edited_claims.append(
                                claim.model_copy(
                                    update={
                                        "text": text,
                                        "status": "verified",
                                        "confidence": "high",
                                        "generator_version": "clinician-verified@1.0.0",
                                    }
                                )
                            )
                            if sec.section_code == "changes_to_review" and claim.status == "needs_verification":
                                clinician_reviewed_conflict = True
                        sec_dict["claims"] = [claim.model_dump(mode="json") for claim in edited_claims]
            updated_sections.append(ReviewSection(**sec_dict))

        updated_conflicts = [
            conflict.model_copy(update={"status": "reviewed"})
            if clinician_reviewed_conflict and conflict.status == "open"
            else conflict.model_copy()
            for conflict in current.conflicts
        ]

        new_rev = current.model_copy(
            update={
                "review_version_id": new_rv_id,
                "version": new_version,
                "status": "edited",
                "updated_at": now_str,
                "sections": updated_sections,
                "conflicts": updated_conflicts,
            }
        )
        revs.append(new_rev)
        self._persist_review_state()
        return new_rev

    def approve_review(
        self, review_id: str, review_version_id: str, expected_version: int, clinician_confirmation: bool
    ) -> ReviewResponse:
        patient_id = review_id.replace("rev_", "")
        revs = self._reviews.get(patient_id, [])
        if not revs:
            raise KeyError(f"Review {review_id} not found")

        current = revs[-1]
        if current.version != expected_version:
            from src.clinical.errors import ReviewPolicyError
            raise ReviewPolicyError("VERSION_CONFLICT")
        if current.review_version_id != review_version_id:
            from src.clinical.errors import ReviewPolicyError
            raise ReviewPolicyError("VERSION_CONFLICT")

        if not clinician_confirmation:
            from src.clinical.errors import ReviewPolicyError
            raise ReviewPolicyError("CONFIRMATION_REQUIRED")

        # Verify claims have citations
        for sec in current.sections:
            for clm in sec.claims:
                if clm.status == "verified" and not clm.citations:
                    from src.clinical.errors import ReviewPolicyError
                    raise ReviewPolicyError("EVIDENCE_REQUIRED")

        now_str = datetime.now().isoformat()
        current.status = "approved"
        current.approved_at = now_str
        current.clinician_confirmation = True

        # Generate PatientMemory version
        self._create_patient_memory(patient_id, current)
        self._persist_review_state()
        return current

    def reject_review(self, review_id: str, expected_version: int, reason: str) -> ReviewResponse:
        patient_id = review_id.replace("rev_", "")
        revs = self._reviews.get(patient_id, [])
        if not revs:
            raise KeyError(f"Review {review_id} not found")

        current = revs[-1]
        if current.version != expected_version:
            from src.clinical.errors import ReviewPolicyError
            raise ReviewPolicyError("VERSION_CONFLICT")

        current.status = "rejected"
        current.updated_at = datetime.now().isoformat()
        self._persist_review_state()
        return current

    def list_review_versions(self, review_id: str) -> list[dict[str, Any]]:
        patient_id = review_id.replace("rev_", "")
        revs = self._reviews.get(patient_id, [])
        out = []
        for r in revs:
            out.append({
                "review_version_id": r.review_version_id,
                "version": r.version,
                "author_id": "usr_doctor_demo",
                "status": r.status,
                "created_at": r.updated_at,
                "checksum": f"sha256:{r.review_version_id}",
            })
        return out

    def _create_patient_memory(self, patient_id: str, approved_review: ReviewResponse) -> PatientMemory:
        mems = self._memories.get(patient_id, [])
        new_version = len(mems) + 1
        mem_id = f"memv_{uuid.uuid4().hex[:8]}"

        items = []
        for sec in approved_review.sections:
            for clm in sec.claims:
                items.append(
                    MemoryItem(
                        item_id=f"mem_{uuid.uuid4().hex[:8]}",
                        category=sec.section_code,
                        text=clm.text,
                        citations=clm.citations,
                    )
                )

        memory = PatientMemory(
            memory_version_id=mem_id,
            version=new_version,
            patient_id=patient_id,
            source_review_version_id=approved_review.review_version_id,
            items=items,
            approved_by="usr_doctor_demo",
            approved_at=approved_review.approved_at or datetime.now().isoformat(),
        )

        if patient_id not in self._memories:
            self._memories[patient_id] = []
        self._memories[patient_id].append(memory)
        approved_review.memory_version_used = new_version
        return memory

    def get_patient_memory(self, patient_id: str, version: int | None = None) -> PatientMemory | None:
        mems = self._memories.get(patient_id, [])
        if not mems:
            return None
        if version is not None:
            for m in mems:
                if m.version == version:
                    return m
            return None
        return mems[-1]
