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

    def get_patient(self, patient_id: str) -> PatientSummary | None:
        return self._patients.get(patient_id)

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

        display_name = "HbA1c" if code == "4548-4" else ("Glucose" if code == "2339-0" else "Creatinine")
        target_unit = "%" if code == "4548-4" else ("mmol/L" if code == "2339-0" else "µmol/L")

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
                        points.append({
                            "observed_at": t_str,
                            "value": disp_val,
                            "unit": unit,
                            "raw_value": float(raw_v),
                            "raw_unit": raw_u,
                            "calculation": prov.to_dict() if prov else None,
                            "reference_range": {"low": None, "high": 7.0 if code == "4548-4" else None},
                            "citations": [cit],
                        })

        points.sort(key=lambda x: x["observed_at"])
        trend_points = [TrendPoint(**p) for p in points]
        return display_name, target_unit, trend_points

    def build_evidence_packet(self, patient_id: str) -> EvidencePacket:
        """Build the locked C1 packet consumed by the C3 agent adapter."""
        if patient_id not in self._patients:
            raise KeyError(f"Patient {patient_id} not found")
        events = self.get_timeline(patient_id)
        _, _, hba1c_points = self.get_trends(patient_id, "4548-4")
        dates = sorted(event.occurred_at[:10] for event in events if event.occurred_at)
        return EvidencePacket(
            patient_id=patient_id,
            data_watermark=self.get_watermark(patient_id),
            coverage_start=dates[0] if dates else None,
            coverage_end=dates[-1] if dates else None,
            encounter_count=sum(event.event_type == "encounter" for event in events),
            timeline=[event.model_dump(mode="json") for event in events],
            lab_trends={"4548-4": [point.model_dump(mode="json") for point in hba1c_points]},
            active_conditions=[{"condition": "Đái tháo đường Típ 2", "code": "44054006"}],
            current_medications=[{"medication": "Metformin 1000mg", "status": "active"}],
            conflicts=[],
            drug_interactions=[],
            data_quality_flags=[],
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
