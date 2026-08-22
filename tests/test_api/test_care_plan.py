import io
import re

import pdfplumber
import pytest
from pypdf import PdfReader

from src.api.dependencies import get_demo_repository
from src.clinical.care_plan_agent import care_plan_agent
from src.clinical.care_plan_share import care_plan_share_store
from src.clinical.demo_repository import DemoRepository
from src.main import app


@pytest.fixture(autouse=True)
def isolated_repository(monkeypatch: pytest.MonkeyPatch, tmp_path):
    repo = DemoRepository()
    app.dependency_overrides[get_demo_repository] = lambda: repo
    monkeypatch.setattr(care_plan_agent.settings, "agent_generation_backend", "deterministic")
    monkeypatch.setattr(care_plan_share_store, "_path", tmp_path / "care_plan_shares.json")
    try:
        yield repo
    finally:
        app.dependency_overrides.pop(get_demo_repository, None)


async def _approve_review(
    client,
    patient_id: str,
    *,
    medication_dose: str | None = None,
    clear_medications: bool = False,
) -> dict:
    generated_response = await client.post(
        f"/api/v1/patients/{patient_id}/reviews/generate",
        json={"profile_versions": ["type_2_diabetes@1.0.0"]},
    )
    assert generated_response.status_code == 201
    review = generated_response.json()

    if medication_dose or clear_medications:
        patched_sections = []
        for section in review["sections"]:
            if section["section_code"] != "current_medications":
                continue
            claims = []
            for claim in section["claims"]:
                updated = dict(claim)
                if clear_medications:
                    updated["text"] = "Không ghi nhận thuốc đang sử dụng"
                elif "Metformin" in updated["text"]:
                    updated["text"] = f"Thuốc hiện tại: Metformin {medication_dose}, uống buổi sáng"
                claims.append(updated)
            patched_sections.append({"section_code": section["section_code"], "claims": claims})

        patch_response = await client.patch(
            f"/api/v1/reviews/{review['review_id']}",
            json={
                "expected_version": review["version"],
                "sections": patched_sections,
                "edit_reason": "Bác sĩ xác nhận lại thuốc",
            },
        )
        assert patch_response.status_code == 200
        review = patch_response.json()

    approve_response = await client.post(
        f"/api/v1/reviews/{review['review_id']}/approve",
        json={
            "review_version_id": review["review_version_id"],
            "expected_version": review["version"],
            "clinician_confirmation": True,
        },
    )
    assert approve_response.status_code == 200
    return approve_response.json()


@pytest.mark.anyio
async def test_care_plan_requires_current_approved_review(client) -> None:
    response = await client.post("/api/v1/patients/PAT-001/care-plan")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REVIEW_APPROVAL_REQUIRED"


@pytest.mark.anyio
async def test_care_plan_is_short_vietnamese_and_uses_approved_summary(client) -> None:
    await _approve_review(client, "PAT-001", medication_dose="750 mg")

    response = await client.post("/api/v1/patients/PAT-001/care-plan")

    assert response.status_code == 200
    care_plan = response.json()
    serialized_plan = " ".join(str(value) for value in care_plan["plan"].values())
    assert care_plan["agent_type"] == "Agent hỗ trợ bệnh lý"
    assert care_plan["generation_mode"] == "deterministic_grounded"
    assert care_plan["requires_clinician_review"] is True
    assert care_plan["plan"]["medication_need"] == "yes"
    assert "Có chỉ định tiếp tục điều trị thuốc" in care_plan["plan"]["medication_assessment"]
    assert "HbA1c 7.4% cao hơn mục tiêu chung dưới 7%" in care_plan["plan"]["medication_assessment"]
    assert "CHỜ BÁC SĨ DUYỆT" in care_plan["plan"]["medication_recommendation"]
    assert "Metformin 750 mg" in care_plan["plan"]["medication_recommendation"]
    assert "Metformin 750 mg" in care_plan["plan"]["medication_note"]
    assert "Metformin 500" not in care_plan["plan"]["medication_note"]
    assert "FHIR" not in serialized_plan
    assert "Grounded" not in serialized_plan
    assert "Type 2 diabetes mellitus" not in serialized_plan
    assert "Hypertension" not in serialized_plan
    assert len(care_plan["plan"]["doctor_greeting"]) < 220
    assert len(care_plan["plan"]["diet_good"]) < 500
    assert care_plan["guideline_citations"]
    assert any("5481/QĐ-BYT" in citation for citation in care_plan["guideline_citations"])
    assert care_plan["clinical_basis"]
    assert care_plan["plan"]["personalization_summary"].startswith("Cá nhân hóa cho người bệnh")
    assert "BYT-5481-MUCTIEU" in care_plan["plan"]["medication_basis_ids"]


@pytest.mark.anyio
async def test_care_plan_exports_monochrome_pdf_from_clinician_edited_content(client) -> None:
    await _approve_review(client, "PAT-001", medication_dose="750 mg")
    care_plan_response = await client.post("/api/v1/patients/PAT-001/care-plan")
    assert care_plan_response.status_code == 200
    care_plan = care_plan_response.json()
    care_plan["plan"]["doctor_greeting"] = "Nội dung đã được bác sĩ chỉnh sửa trước khi xuất PDF."

    response = await client.post(
        "/api/v1/patients/PAT-001/care-plan/export.pdf",
        json={
            "plan": care_plan["plan"],
            "data_summary": care_plan["data_summary"],
            "doctor_sign_name": "BS. Nguyễn Văn A",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "Huong_dan_dieu_tri_PAT-001.pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")
    listen_url = response.headers["x-care-plan-listen-url"]
    assert "/care-plan/listen/" in listen_url
    token = listen_url.rsplit("/", 1)[-1]
    listen_page = await client.get(f"/api/v1/care-plan/listen/{token}")
    assert listen_page.status_code == 200
    assert "BẤM ĐỂ NGHE TOÀN BỘ HƯỚNG DẪN" in listen_page.text
    assert "BS. Nguyễn Văn A" in listen_page.text
    assert "medication_assessment" not in listen_page.text
    assert "guideline" not in listen_page.text.casefold()

    reader = PdfReader(io.BytesIO(response.content))
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "PHIẾU HƯỚNG DẪN ĐIỀU TRỊ VÀ CHĂM SÓC TẠI NHÀ" in extracted
    assert "Nội dung đã được bác sĩ chỉnh sửa trước khi xuất PDF." in extracted
    assert "Metformin 750 mg" in extracted
    assert "BS. Nguyễn Văn A" in extracted
    assert "CĂN CỨ CHUYÊN MÔN ÁP DỤNG" not in extracted
    assert "CÓ CẦN ĐIỀU TRỊ THUỐC?" not in extracted
    assert "ĐỀ XUẤT ĐỂ BÁC SĨ DUYỆT" not in extracted
    assert "NỘI DUNG CẦN BÁC SĨ RÀ SOÁT" not in extracted
    assert "Thuốc trong bản tóm tắt đã duyệt" not in extracted
    assert "Bác sĩ bổ sung thuốc" not in extracted
    assert "guideline" not in extracted.casefold()
    assert "trích nguồn" not in extracted.casefold()

    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        signature_page = pdf.pages[-1]
        doctor_title = signature_page.search("BÁC SĨ ĐIỀU TRỊ")[0]
        doctor_name = signature_page.search("BS. Nguyễn Văn A")[0]
        title_center = (doctor_title["x0"] + doctor_title["x1"]) / 2
        name_center = (doctor_name["x0"] + doctor_name["x1"]) / 2
        assert abs(title_center - name_center) < 1

    color_operators: list[tuple[float, float, float]] = []
    for page in reader.pages:
        content = page.get_contents()
        if content is None:
            continue
        streams = content if isinstance(content, list) else [content]
        for stream in streams:
            for match in re.findall(rb"([0-9.]+) ([0-9.]+) ([0-9.]+) (?:rg|RG)", stream.get_data()):
                color_operators.append(tuple(float(value) for value in match))
    assert color_operators
    assert all(abs(red - green) < 0.001 and abs(green - blue) < 0.001 for red, green, blue in color_operators)


@pytest.mark.anyio
async def test_care_plan_pdf_qr_requires_clinician_signature(client) -> None:
    await _approve_review(client, "PAT-001")
    care_plan_response = await client.post("/api/v1/patients/PAT-001/care-plan")
    care_plan = care_plan_response.json()

    response = await client.post(
        "/api/v1/patients/PAT-001/care-plan/export.pdf",
        json={
            "plan": care_plan["plan"],
            "data_summary": care_plan["data_summary"],
            "doctor_sign_name": "Chưa ký duyệt",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CARE_PLAN_SIGNATURE_REQUIRED"


@pytest.mark.anyio
async def test_agent_personalizes_all_demo_cases_and_maps_specific_basis(client) -> None:
    plans: dict[str, dict] = {}
    for patient_id in ("PAT-001", "PAT-002", "PAT-003", "PAT-004", "PAT-005", "PAT-006"):
        await _approve_review(client, patient_id)
        response = await client.post(f"/api/v1/patients/{patient_id}/care-plan")
        assert response.status_code == 200
        plans[patient_id] = response.json()

    fingerprints = {
        (
            response["plan"]["personalization_summary"],
            response["plan"]["diet_good"],
            response["plan"]["exercise"],
        )
        for response in plans.values()
    }
    assert len(fingerprints) == 6
    assert any(item["basis_id"] == "BYT-3879-LIPID" for item in plans["PAT-003"]["clinical_basis"])
    assert any(item["basis_id"] == "BYT-2892-BEOPHI" for item in plans["PAT-004"]["clinical_basis"])
    assert any(item["basis_id"] == "BYT-3879-BANCHAN" for item in plans["PAT-005"]["clinical_basis"])
    assert any(item["basis_id"] == "BYT-GAN-NHIEM-MO" for item in plans["PAT-006"]["clinical_basis"])
    assert "bảo vệ bàn chân" in plans["PAT-005"]["plan"]["personalization_summary"]
    assert "gan" in plans["PAT-006"]["plan"]["personalization_summary"]


@pytest.mark.anyio
async def test_approved_review_and_memory_survive_demo_runtime_restart(
    client,
    isolated_repository: DemoRepository,
    tmp_path,
) -> None:
    state_path = tmp_path / "review_state.json"
    isolated_repository.state_path = state_path
    approved = await _approve_review(client, "PAT-002")

    restored = DemoRepository(state_path=state_path)
    restored_review = restored.get_review("PAT-002")
    restored_memory = restored.get_patient_memory("PAT-002")

    assert restored_review is not None
    assert restored_review.status == "approved"
    assert restored_review.review_version_id == approved["review_version_id"]
    assert restored_memory is not None
    assert restored_memory.source_review_version_id == approved["review_version_id"]


@pytest.mark.anyio
async def test_agent_never_guesses_medication_time_from_approved_summary(client) -> None:
    await _approve_review(client, "PAT-002")

    response = await client.post("/api/v1/patients/PAT-002/care-plan")

    assert response.status_code == 200
    care_plan = response.json()
    assert "Amlodipine 5 mg" in care_plan["plan"]["medication_note"]
    assert "bổ sung" in care_plan["plan"]["morning_meds"].casefold()
    assert "bổ sung" in care_plan["plan"]["evening_meds"].casefold()


@pytest.mark.anyio
async def test_chat_care_plan_follows_the_same_approval_gate(client) -> None:
    blocked = await client.post(
        "/api/v1/patients/PAT-002/ask",
        json={"question": "Gợi ý phác đồ chăm sóc tại nhà"},
    )
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "not_allowed"
    assert "ký duyệt bản tóm tắt" in blocked.json()["answer"]

    await _approve_review(client, "PAT-002")
    allowed = await client.post(
        "/api/v1/patients/PAT-002/ask",
        json={"question": "Gợi ý phác đồ chăm sóc tại nhà"},
    )

    assert allowed.status_code == 200
    assert allowed.json()["status"] == "answered"
    assert "Amlodipine 5 mg" in allowed.json()["answer"]
    assert allowed.json()["citations"]


@pytest.mark.anyio
async def test_agent_proposes_guideline_medications_when_approved_summary_has_no_medication(client) -> None:
    await _approve_review(client, "PAT-001", clear_medications=True)

    response = await client.post("/api/v1/patients/PAT-001/care-plan")

    assert response.status_code == 200
    care_plan = response.json()
    assert care_plan["status"] == "needs_review"
    assert care_plan["data_summary"]["medications"] == []
    assert care_plan["plan"]["medication_need"] == "yes"
    assert "Có chỉ định xem xét điều trị bằng thuốc" in care_plan["plan"]["medication_assessment"]
    assert "Metformin 500 mg" in care_plan["plan"]["morning_meds"]
    assert "Amlodipin 5 mg" in care_plan["plan"]["morning_meds"]
    assert "CHỜ BÁC SĨ DUYỆT" in care_plan["plan"]["medication_note"]
    assert "chưa phải đơn thuốc có hiệu lực" in care_plan["plan"]["medication_note"].casefold()
    assert any("thuốc mới do Agent đề xuất" in item for item in care_plan["safety_flags"])


@pytest.mark.anyio
async def test_pat003_conflict_is_normalized_instead_of_reported_as_scope_error(client) -> None:
    response = await client.post(
        "/api/v1/patients/PAT-003/reviews/generate",
        json={"profile_versions": ["type_2_diabetes@1.0.0"]},
    )

    assert response.status_code == 201
    review = response.json()
    assert len(review["conflicts"]) == 1
    assert review["conflicts"][0]["conflict_type"] == "medication_dose_conflict"
    assert review["conflicts"][0]["status"] == "open"


def test_agent_does_not_propose_metformin_below_egfr_contraindication(isolated_repository) -> None:
    patient = isolated_repository.get_patient("PAT-001")
    assert patient is not None

    morning, evening, note, proposed, _ = care_plan_agent._medication_schedule(
        patient,
        {"diabetes": True, "hypertension": False, "ckd": True, "neuropathy": False},
        [],
        ["eGFR theo các kết quả nguồn: 35 mL/min/1,73 m²; 24 mL/min/1,73 m²."],
        [],
        [],
    )

    assert proposed is False
    assert "Metformin" not in morning
    assert "Metformin" not in evening
    assert "Không dùng Metformin" in note
    assert "eGFR 24" in note


def test_agent_does_not_propose_new_drug_while_data_conflict_is_open(isolated_repository) -> None:
    patient = isolated_repository.get_patient("PAT-003")
    assert patient is not None

    morning, evening, note, proposed, _ = care_plan_agent._medication_schedule(
        patient,
        {"diabetes": True, "hypertension": False, "ckd": False, "neuropathy": False},
        [],
        ["eGFR: 69 mL/min/1,73 m²"],
        [],
        ["Liều Metformin đang mâu thuẫn"],
    )

    assert proposed is False
    assert "xử lý" in morning
    assert "xử lý" in evening
    assert "Không đề xuất thuốc" in note


@pytest.mark.anyio
async def test_clinician_can_resolve_pat003_conflict_then_generate_plan(client) -> None:
    generated = await client.post(
        "/api/v1/patients/PAT-003/reviews/generate",
        json={"profile_versions": ["type_2_diabetes@1.0.0"]},
    )
    assert generated.status_code == 201
    review = generated.json()

    patched_sections = []
    for section in review["sections"]:
        claims = []
        for claim in section["claims"]:
            updated = dict(claim)
            if section["section_code"] == "current_medications" and "Metformin" in claim["text"]:
                updated["text"] = "Thuốc hiện tại: Metformin 850 mg, uống buổi sáng sau ăn"
            elif section["section_code"] == "changes_to_review" and claim["status"] == "needs_verification":
                updated["text"] = "Bác sĩ xác nhận sử dụng Metformin 850 mg theo đơn đã kiểm tra."
            claims.append(updated)
        patched_sections.append({"section_code": section["section_code"], "claims": claims})

    patched = await client.patch(
        f"/api/v1/reviews/{review['review_id']}",
        json={
            "expected_version": review["version"],
            "sections": patched_sections,
            "edit_reason": "Bác sĩ đối chiếu đơn gốc và xác nhận liều 850 mg",
        },
    )
    assert patched.status_code == 200
    review = patched.json()
    assert review["conflicts"][0]["status"] == "reviewed"
    assert not any(
        claim["status"] == "needs_verification"
        for section in review["sections"]
        for claim in section["claims"]
    )

    approved = await client.post(
        f"/api/v1/reviews/{review['review_id']}/approve",
        json={
            "review_version_id": review["review_version_id"],
            "expected_version": review["version"],
            "clinician_confirmation": True,
        },
    )
    assert approved.status_code == 200

    care_plan = await client.post("/api/v1/patients/PAT-003/care-plan")
    assert care_plan.status_code == 200
    assert "Metformin 850 mg" in care_plan.json()["plan"]["medication_note"]
