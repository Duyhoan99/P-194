"""Demo MVP v1 repository handling baseline data loading, canonical mapping, OCR items, reviews, memory, and audit logs."""

import json
from pathlib import Path
import uuid
from datetime import datetime
from typing import Any
from src.agents.contracts import AgentResult
from src.clinical.canonical import (
    PatientSummary,
    TimelineEvent,
    TrendPoint,
    ReviewResponse,
    ReviewSection,
    VerifiedClaim,
    ConflictFlag,
    DrugInteractionFlag,
    DataQualityFlag,
    Coverage,
    PatientMemory,
    MemoryItem,
    VerificationItem,
    FhirCitation,
    DocumentCitation,
    RecordCitation,
    Citation,
)
from src.clinical.evidence_packet import EvidencePacket
from src.clinical.calculation import (
    convert_unit,
    format_display_value,
    calculate_delta,
    calculate_trend,
)
from src.services.medication_safety import MedicationSafetyService


class DemoRepository:
    """In-memory & JSON backed repository for demo_mvp_v1 baseline dataset."""

    def __init__(self, data_dir: str | Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parents[2] / "data" / "demo_mvp_v1"
        self.data_dir = Path(data_dir)

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

    def _load_baseline(self) -> None:
        manifest_path = self.data_dir / "dataset_manifest.json"
        if not manifest_path.exists():
            return

        with open(manifest_path, "r", encoding="utf-8") as f:
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
            if bundle_path and bundle_path.exists():
                with open(bundle_path, "r", encoding="utf-8") as bf:
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

            self._patients[p_id] = PatientSummary(
                patient_id=p_id,
                pseudonym=name,
                age=age,
                sex=gender if gender in ("male", "female", "other", "unknown") else "unknown",
                primary_condition="Đái tháo đường típ 2",
                last_encounter_at="2026-08-10T12:00:00+07:00",
                latest_data_watermark=wm,
            )

        # Load default OCR items if gold/ocr.json exists
        gold_ocr = self.data_dir / "gold" / "ocr.json"
        if gold_ocr.exists():
            try:
                with open(gold_ocr, "r", encoding="utf-8") as f:
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
                with open(gold_conflicts, "r", encoding="utf-8") as f:
                    c_data = json.load(f)
                    for case in c_data.get("cases", []):
                        p_id = case.get("patient_id")
                        c_id = case.get("case_id", f"CONFLICT-{p_id}")
                        self._conflicts.setdefault(p_id, []).append({
                            "conflict_id": c_id,
                            "type": case.get("type", "medication_dose_conflict"),
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
                            "status": case.get("status", "unresolved")
                        })
            except Exception:
                pass

    def get_patient(self, patient_id: str) -> PatientSummary | None:
        return self._patients.get(patient_id)

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
        events: list[TimelineEvent] = []

        for entry in bundle.get("entry", []):
            res = entry.get("resource", {})
            r_type = res.get("resourceType")
            if str(res.get("status", "")).casefold() == "entered-in-error":
                continue
            r_id = res.get("id", "res_1")
            doc_id = f"DOC-{patient_id}-FHIR"
            cit = FhirCitation(
                citation_id=f"cit_{r_id}",
                document_id=doc_id,
                resource_type=r_type,
                resource_id=r_id,
                snippet=json.dumps(res, ensure_ascii=False)[:100],
                source_checksum="sha256:baseline",
            )

            if r_type == "Encounter":
                events.append(
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
                events.append(
                    TimelineEvent(
                        event_id=f"evt_{r_id}",
                        event_type="observation",
                        occurred_at=res.get("effectiveDateTime", "2026-01-01T08:00:00+07:00"),
                        title=f"Xét nghiệm: {code_text}",
                        summary=f"Kết quả: {val} {unit}".strip(),
                        citations=[cit],
                    )
                )
            elif r_type in ("MedicationStatement", "MedicationRequest"):
                med_name = res.get("medicationCodeableConcept", {}).get("text") or "Thuốc"
                events.append(
                    TimelineEvent(
                        event_id=f"evt_{r_id}",
                        event_type="medication",
                        occurred_at=res.get("effectiveDateTime") or res.get("authoredOn") or "2026-01-01T08:00:00+07:00",
                        title=f"Thuốc: {med_name}",
                        summary=f"Trạng thái: {res.get('status', 'active')}",
                        citations=[cit],
                    )
                )

        events.sort(key=lambda e: e.occurred_at, reverse=True)
        return events

    def get_trends(self, patient_id: str, code: str) -> tuple[str, str, list[TrendPoint]]:
        bundle = self._bundles.get(patient_id, {})
        points: list[dict[str, Any]] = []

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

                    cit = FhirCitation(
                        citation_id=f"cit_{r_id}",
                        document_id=f"DOC-{patient_id}-FHIR",
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
                        points.append({
                            "observed_at": t_str,
                            "value": disp_val,
                            "unit": unit,
                            "raw_value": float(raw_v),
                            "raw_unit": raw_u,
                            "calculation": prov.to_dict() if prov else None,
                            "reference_range": ref_map.get(code, {"low": None, "high": None}),
                            "citations": [cit],
                        })

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

    def add_fhir_evidence(self, patient_id: str, evidence_items: list[dict[str, Any]]) -> None:
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

    def mark_reviews_stale(self, patient_id: str) -> int:
        """Mark all non-approved reviews for a patient as stale. Returns count marked."""
        revs = self._reviews.get(patient_id, [])
        count = 0
        for rev in revs:
            if rev.status not in {"approved", "stale"}:
                rev.status = "stale"  # type: ignore[assignment]
                count += 1
        return count

    def build_evidence_packet(self, patient_id: str) -> EvidencePacket:
        """Build the locked C1 packet consumed by the C3 agent adapter."""
        if patient_id not in self._patients:
            raise KeyError(f"Patient {patient_id} not found")
        events = self.get_timeline(patient_id)
        _, _, hba1c_points = self.get_trends(patient_id, "4548-4")
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
            lab_trends={"4548-4": [point.model_dump(mode="json") for point in hba1c_points]},
            active_conditions=[{
                "condition": "Đái tháo đường Típ 2",
                "code": "44054006",
                "citations": [{
                    "citation_id": "cit_baseline_cond",
                    "source_type": "fhir",
                    "document_id": f"DOC-{patient_id}-FHIR",
                    "resource_type": "Condition",
                    "resource_id": "baseline_cond",
                    "snippet": "Đái tháo đường Típ 2",
                    "source_checksum": "sha256:baseline"
                }]
            }],
            current_medications=[{
                "medication": "Metformin 1000mg",
                "status": "active",
                "citations": [{
                    "citation_id": "cit_baseline_med",
                    "source_type": "fhir",
                    "document_id": f"DOC-{patient_id}-FHIR",
                    "resource_type": "MedicationStatement",
                    "resource_id": "baseline_med",
                    "snippet": "Metformin 1000mg",
                    "source_checksum": "sha256:baseline"
                }]
            }],
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
        for sec in current.sections:
            sec_dict = sec.model_dump()
            for patch_sec in sections:
                if patch_sec.get("section_code") == sec.section_code:
                    if "clinician_text" in patch_sec:
                        sec_dict["clinician_text"] = patch_sec["clinician_text"]
            updated_sections.append(ReviewSection(**sec_dict))

        new_rev = current.model_copy(
            update={
                "review_version_id": new_rv_id,
                "version": new_version,
                "status": "edited",
                "updated_at": now_str,
                "sections": updated_sections,
            }
        )
        revs.append(new_rev)
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
