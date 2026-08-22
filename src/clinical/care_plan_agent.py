"""Agent hỗ trợ bệnh lý dựa trên bản tóm tắt đã được bác sĩ ký duyệt.

Đầu vào lâm sàng của agent chỉ gồm PatientMemory sinh từ đúng phiên bản
ReviewResponse đã duyệt và guideline nội bộ phù hợp. Contract đầu ra được giữ
ổn định để giao diện care-plan hiện tại không phải thay đổi.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Literal

import httpx
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from src.clinical.canonical import PatientMemory, PatientSummary, ReviewResponse
from src.config import get_settings


class CarePlanDraft(BaseModel):
    doctor_greeting: str
    personalization_summary: str = ""
    medication_need: Literal["yes", "no", "undetermined"] = "undetermined"
    medication_assessment: str = ""
    medication_recommendation: str = ""
    medication_basis_ids: list[str] = Field(default_factory=list)
    morning_meds: str
    evening_meds: str
    medication_note: str
    diet_good: str
    diet_bad: str
    diet_basis_ids: list[str] = Field(default_factory=list)
    exercise: str
    exercise_basis_ids: list[str] = Field(default_factory=list)
    emergency_warning: str
    warning_basis_ids: list[str] = Field(default_factory=list)
    follow_up: str
    follow_up_days: int | None = None
    guideline_citation: str


class CarePlanDataSummary(BaseModel):
    conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    latest_observations: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class ClinicalBasisItem(BaseModel):
    basis_id: str
    source_title: str
    source_reference: str
    section: str
    applied_content: str
    applies_to: list[Literal["medication", "diet", "exercise", "warning"]] = Field(default_factory=list)


class CarePlanResponse(BaseModel):
    status: Literal["draft", "needs_review"]
    generation_mode: Literal["deterministic_grounded", "llm_grounded"]
    agent_type: str
    data_watermark: str
    requires_clinician_review: bool = True
    disclaimer: str
    safety_flags: list[str] = Field(default_factory=list)
    guideline_citations: list[str] = Field(default_factory=list)
    evidence_citation_ids: list[str] = Field(default_factory=list)
    clinical_basis: list[ClinicalBasisItem] = Field(default_factory=list)
    data_summary: CarePlanDataSummary
    plan: CarePlanDraft


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _remove_english_parentheses(value: str) -> str:
    return _compact(re.sub(r"\s*\([^)]*[A-Za-z][^)]*\)", "", value))


def _vietnamize(value: str) -> str:
    replacements = {
        "Type 2 diabetes mellitus": "đái tháo đường típ 2",
        "Chronic kidney disease": "bệnh thận mạn",
        "Hypertension": "tăng huyết áp",
        "Systolic blood pressure": "huyết áp tâm thu",
        "Diastolic blood pressure": "huyết áp tâm trương",
        "Hemoglobin A1c": "HbA1c",
        "Glucose": "đường huyết",
        "finished": "đã hoàn thành",
        "active": "đang sử dụng",
        "once daily": "1 lần/ngày",
        "twice daily": "2 lần/ngày",
    }
    result = value
    for source, target in replacements.items():
        result = re.sub(re.escape(source), target, result, flags=re.IGNORECASE)
    result = re.sub(r"\bMG\b", "mg", result)
    return _compact(result)


class ClinicalCarePlanAgent:
    """Soạn bản nháp chăm sóc ngắn gọn từ thông tin bác sĩ đã duyệt."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.guidelines_dir = Path(__file__).parents[2] / "data" / "guidelines"

    @staticmethod
    def _items(memory: PatientMemory, category: str) -> list[str]:
        return [item.text for item in memory.items if item.category == category and item.text.strip()]

    def _conditions(self, memory: PatientMemory) -> list[str]:
        conditions: list[str] = []
        for text in self._items(memory, "active_conditions"):
            cleaned = re.sub(r"^Chẩn đoán/Tình trạng bệnh\s*:\s*", "", text, flags=re.IGNORECASE)
            cleaned = _remove_english_parentheses(_vietnamize(cleaned)).strip(" .;")
            if cleaned and cleaned.casefold() not in {item.casefold() for item in conditions}:
                conditions.append(cleaned)
        return conditions

    def _medications(self, memory: PatientMemory) -> list[tuple[str, str]]:
        medications: list[tuple[str, str]] = []
        seen: set[str] = set()
        for raw_text in self._items(memory, "current_medications"):
            lowered = raw_text.casefold()
            if any(
                phrase in lowered
                for phrase in (
                    "không ghi nhận thuốc",
                    "chưa ghi nhận thuốc",
                    "không dùng thuốc",
                    "chưa có thuốc",
                )
            ):
                continue
            cleaned = re.sub(r"^(?:Thuốc hiện tại|Thuốc)\s*:\s*", "", raw_text, flags=re.IGNORECASE)
            cleaned = re.split(r"\s+ngày\s+\d{4}-\d{2}-\d{2}", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
            cleaned = re.sub(r"\s*\((?:active|đang sử dụng)\)\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*:\s*Trạng thái\s*:\s*(?:active|đang sử dụng)\s*$", "", cleaned, flags=re.IGNORECASE)
            cleaned = _vietnamize(cleaned).strip(" .;-")
            key = cleaned.casefold()
            if cleaned and key not in seen:
                seen.add(key)
                medications.append((cleaned, _vietnamize(raw_text).casefold()))
        return medications

    def _observations(self, memory: PatientMemory) -> list[str]:
        observations: list[str] = []
        for text in self._items(memory, "recent_results"):
            cleaned = _vietnamize(text)
            if cleaned not in observations:
                observations.append(cleaned)
        return observations[:5]

    def _condition_flags(self, conditions: list[str]) -> dict[str, bool]:
        corpus = " ".join(conditions).casefold()
        return {
            "diabetes": "đái tháo đường" in corpus,
            "hypertension": "tăng huyết áp" in corpus,
            "ckd": "bệnh thận mạn" in corpus,
            "neuropathy": "thần kinh ngoại biên" in corpus,
            "dyslipidemia": "rối loạn lipid" in corpus or "tăng lipid" in corpus,
            "obesity": "béo phì" in corpus or "thừa cân" in corpus,
            "fatty_liver": "gan nhiễm mỡ" in corpus,
        }

    def _guideline_files(
        self,
        flags: dict[str, bool],
        medications: list[tuple[str, str]],
    ) -> list[Path]:
        filenames: list[str] = []
        if flags["diabetes"]:
            filenames.append("5481_QD_BYT_DaiThaoDuong_Type2.md")
        if flags["hypertension"]:
            filenames.append("3192_QD_BYT_TangHuyetAp.md")
        if flags["dyslipidemia"] or flags["neuropathy"]:
            filenames.append("3879_QD_BYT_NoiTiet_ChuyenHoa.md")
        if flags["obesity"]:
            filenames.append("2892_QD_BYT_BeoPhi.md")
        if flags["fatty_liver"]:
            filenames.append("BYT_GanNhiemMo_ThongTinChuyenMon.md")
        if medications or flags["diabetes"] or flags["hypertension"]:
            filenames.append("DuocThuQuocGia_ChuyenLuanThuoc.md")
        return [self.guidelines_dir / name for name in dict.fromkeys(filenames)]

    @staticmethod
    def _clinical_basis(
        flags: dict[str, bool],
        medications: list[tuple[str, str]],
    ) -> list[ClinicalBasisItem]:
        basis: list[ClinicalBasisItem] = []

        def add(
            basis_id: str,
            source_title: str,
            source_reference: str,
            section: str,
            applied_content: str,
            applies_to: list[Literal["medication", "diet", "exercise", "warning"]],
        ) -> None:
            basis.append(
                ClinicalBasisItem(
                    basis_id=basis_id,
                    source_title=source_title,
                    source_reference=source_reference,
                    section=section,
                    applied_content=applied_content,
                    applies_to=applies_to,
                )
            )

        if flags["diabetes"]:
            add(
                "BYT-5481-MUCTIEU",
                "Quyết định 5481/QĐ-BYT - Đái tháo đường típ 2",
                "data/guidelines/5481_QD_BYT_DaiThaoDuong_Type2.md",
                "Phần 4 - Nguyên tắc và mục tiêu điều trị",
                "Mục tiêu HbA1c chung dưới 7%; mục tiêu cần được bác sĩ cá thể hóa theo tuổi và bệnh đồng mắc.",
                ["medication", "diet", "exercise"],
            )
            add(
                "BYT-5481-METFORMIN",
                "Quyết định 5481/QĐ-BYT - Đái tháo đường típ 2",
                "data/guidelines/5481_QD_BYT_DaiThaoDuong_Type2.md",
                "Phụ lục 01 - Metformin",
                "Liều thường dùng 500-2000 mg/ngày; giảm liều khi eGFR 30-45 và chống chỉ định khi eGFR dưới 30 mL/phút/1,73 m².",
                ["medication"],
            )
            add(
                "BYT-5481-HADUONG",
                "Quyết định 5481/QĐ-BYT - Đái tháo đường típ 2",
                "data/guidelines/5481_QD_BYT_DaiThaoDuong_Type2.md",
                "Phần 6 - Xử trí hạ đường huyết",
                "Áp dụng quy tắc 15-15 khi đường huyết dưới 3,9 mmol/L hoặc có triệu chứng phù hợp.",
                ["warning"],
            )
        if flags["hypertension"]:
            add(
                "BYT-3192-MUCTIEU",
                "Quyết định 3192/QĐ-BYT - Tăng huyết áp",
                "data/guidelines/3192_QD_BYT_TangHuyetAp.md",
                "Mục 2 - Nguyên tắc và mục tiêu điều trị",
                "Mục tiêu chung dưới 140/90 mmHg; nhóm có đái tháo đường hoặc bệnh thận mạn hướng tới dưới 130/80 mmHg.",
                ["medication", "warning"],
            )
            add(
                "BYT-3192-LOISONG",
                "Quyết định 3192/QĐ-BYT - Tăng huyết áp",
                "data/guidelines/3192_QD_BYT_TangHuyetAp.md",
                "Mục 3 - Thay đổi lối sống",
                "Giảm muối, hạn chế rượu bia và vận động mức vừa 30-60 phút mỗi ngày nếu dung nạp.",
                ["diet", "exercise"],
            )
        if flags["dyslipidemia"]:
            add(
                "BYT-3879-LIPID",
                "Quyết định 3879/QĐ-BYT - Nội tiết, chuyển hóa",
                "data/guidelines/3879_QD_BYT_NoiTiet_ChuyenHoa.md",
                "Rối loạn chuyển hóa lipid máu - trang 255-260",
                "Tăng vận động; hạn chế bia rượu, mỡ động vật và chất béo bão hòa; thuốc cần dựa trên lipid máu và phân tầng nguy cơ.",
                ["medication", "diet", "exercise"],
            )
        if flags["neuropathy"]:
            add(
                "BYT-3879-BANCHAN",
                "Quyết định 3879/QĐ-BYT - Nội tiết, chuyển hóa",
                "data/guidelines/3879_QD_BYT_NoiTiet_ChuyenHoa.md",
                "Bệnh lý bàn chân do đái tháo đường - trang 222-227",
                "Quan sát và vệ sinh bàn chân hằng ngày; tránh đi chân đất; khám sớm khi có vết thương hoặc dấu nhiễm trùng.",
                ["exercise", "warning"],
            )
        if flags["obesity"]:
            add(
                "BYT-2892-BEOPHI",
                "Quyết định 2892/QĐ-BYT - Bệnh béo phì",
                "data/guidelines/2892_QD_BYT_BeoPhi.md",
                "Nguyên tắc điều trị cá nhân hóa",
                "Nền tảng là dinh dưỡng, hoạt động thể lực phù hợp và thay đổi hành vi; không tự động thêm thuốc khi thiếu dữ liệu đánh giá béo phì.",
                ["medication", "diet", "exercise"],
            )
        if flags["fatty_liver"]:
            add(
                "BYT-GAN-NHIEM-MO",
                "Thông tin chuyên môn Bộ Y tế - Gan nhiễm mỡ",
                "data/guidelines/BYT_GanNhiemMo_ThongTinChuyenMon.md",
                "Nguyên tắc lối sống và kiểm soát nguyên nhân",
                "Tránh rượu bia, hạn chế nhiều đường và mỡ, vận động thường xuyên và kiểm soát bệnh chuyển hóa đi kèm.",
                ["diet", "exercise"],
            )

        medication_corpus = " ".join(item for item, _ in medications).casefold()
        if "metformin" in medication_corpus:
            add(
                "DUOCTHU-METFORMIN",
                "Dược thư Quốc gia Việt Nam - Metformin",
                "data/guidelines/DuocThuQuocGia_ChuyenLuanThuoc.md",
                "Chuyên luận Metformin hydrochlorid",
                "Đối chiếu chỉ định, cách dùng cùng bữa ăn, chức năng thận và nguy cơ nhiễm toan lactic.",
                ["medication"],
            )
        if "amlodip" in medication_corpus:
            add(
                "DUOCTHU-AMLODIPIN",
                "Dược thư Quốc gia Việt Nam - Amlodipin",
                "data/guidelines/DuocThuQuocGia_ChuyenLuanThuoc.md",
                "Chuyên luận Amlodipin",
                "Đối chiếu liều một lần mỗi ngày, khả năng dung nạp và phù ngoại biên.",
                ["medication"],
            )
        return basis

    @staticmethod
    def _guideline_label(files: list[Path]) -> str:
        return (
            "Hướng dẫn chuyên môn phù hợp với bệnh lý đã được đối chiếu."
            if files
            else "Chưa xác định được hướng dẫn chuyên môn phù hợp từ bản tóm tắt đã duyệt."
        )

    def _guideline_context(self, files: list[Path]) -> str:
        contexts: list[str] = []
        for path in files:
            try:
                contexts.append(path.read_text(encoding="utf-8")[:7000])
            except OSError as exc:
                logger.warning("Không đọc được guideline {}: {}", path.name, exc)
        return "\n\n".join(contexts)

    @staticmethod
    def _numeric_observation(observations: list[str], label: str) -> float | None:
        """Lấy giá trị gần nhất đã xuất hiện trong bản tóm tắt được duyệt."""
        matches: list[float] = []
        for text in observations:
            label_match = re.search(re.escape(label), text, flags=re.IGNORECASE)
            if not label_match:
                continue
            tail = text[label_match.end():]
            if label.casefold() == "egfr":
                value_matches = re.finditer(
                    r"([0-9]+(?:[.,][0-9]+)?)\s*mL/min",
                    tail,
                    flags=re.IGNORECASE,
                )
            else:
                value_matches = re.finditer(r"([0-9]+(?:[.,][0-9]+)?)", tail)
            for match in value_matches:
                try:
                    matches.append(float(match.group(1).replace(",", ".")))
                except ValueError:
                    continue
        return matches[-1] if matches else None

    @staticmethod
    def _allergies(memory: PatientMemory) -> list[str]:
        allergies: list[str] = []
        for item in memory.items:
            lowered = item.text.casefold()
            if "dị ứng" in lowered and item.text not in allergies:
                allergies.append(_vietnamize(item.text))
        return allergies

    def _medication_schedule(
        self,
        patient: PatientSummary,
        flags: dict[str, bool],
        medications: list[tuple[str, str]],
        observations: list[str],
        allergies: list[str],
        blocking_reasons: list[str],
    ) -> tuple[str, str, str, bool, list[str]]:
        if blocking_reasons:
            message = "Bác sĩ cần xử lý các điểm dữ liệu còn mâu thuẫn hoặc chưa xác minh trước khi ghi cách dùng."
            return message, message, "Không đề xuất thuốc hoặc liều khi dữ liệu còn mâu thuẫn/chưa được xác minh.", False, []

        if not medications:
            proposals: list[str] = []
            notes: list[str] = []
            safety_flags: list[str] = []
            allergy_corpus = " ".join(allergies).casefold()

            if flags["diabetes"] and "metformin" not in allergy_corpus:
                egfr = self._numeric_observation(observations, "eGFR")
                if egfr is None or egfr >= 45:
                    proposals.append("Metformin 500 mg x 1 lần/ngày, ngay sau bữa sáng")
                    if egfr is None:
                        notes.append("Chỉ duyệt Metformin sau khi xác nhận eGFR từ 45 mL/phút/1,73 m² trở lên.")
                    else:
                        notes.append(f"eGFR đã duyệt: {egfr:g} mL/phút/1,73 m².")
                elif egfr >= 30:
                    notes.append(
                        f"Chưa đề xuất Metformin vì eGFR {egfr:g} mL/phút/1,73 m²; bác sĩ cần cân nhắc riêng và giảm liều nếu sử dụng."
                    )
                else:
                    notes.append(
                        f"Không dùng Metformin vì eGFR {egfr:g} mL/phút/1,73 m², thuộc mức chống chỉ định trong guideline."
                    )

            if flags["hypertension"] and "amlodip" not in allergy_corpus:
                dose = "2,5 mg" if patient.age is not None and patient.age >= 65 else "5 mg"
                proposals.append(f"Amlodipin {dose} x 1 lần/ngày, vào buổi sáng")

            if not proposals:
                message = "Chưa đủ điều kiện an toàn để Agent đề xuất thuốc mới; bác sĩ cần hoàn thiện dữ liệu lâm sàng."
                return message, message, " ".join(notes) or message, False, safety_flags

            proposed_text = "; ".join(proposals)
            safety_flags.append("Có thuốc mới do Agent đề xuất từ guideline; bắt buộc bác sĩ kiểm tra chống chỉ định, tương tác và ký duyệt.")
            note = (
                "ĐỀ XUẤT THUỐC KHỞI TRỊ – CHỜ BÁC SĨ DUYỆT: "
                + proposed_text
                + ". Đây chưa phải đơn thuốc có hiệu lực. "
                + " ".join(notes)
            ).strip()
            return proposed_text, "Chưa đề xuất thuốc dùng buổi tối.", note, True, safety_flags

        morning: list[str] = []
        evening: list[str] = []
        unspecified: list[str] = []
        for medication, source_text in medications:
            if "2 lần/ngày" in source_text or "hai lần/ngày" in source_text:
                morning.append(medication)
                evening.append(medication)
            elif "buổi sáng" in source_text or "sáng" in source_text:
                morning.append(medication)
            elif "buổi tối" in source_text or "tối" in source_text:
                evening.append(medication)
            else:
                unspecified.append(medication)

        morning_text = "; ".join(morning) or "Bác sĩ bổ sung thuốc và cách dùng buổi sáng nếu có."
        evening_text = "; ".join(evening) or "Bác sĩ bổ sung thuốc và cách dùng buổi tối nếu có."
        note = "Thuốc trong bản tóm tắt đã duyệt: " + "; ".join(item for item, _ in medications) + "."
        if unspecified:
            note += " Chưa tự xếp thời điểm dùng cho: " + "; ".join(unspecified) + "."
        note += " Chỉ dùng theo đơn bác sĩ đã chốt."
        return morning_text, evening_text, note, False, []

    def _medication_assessment(
        self,
        flags: dict[str, bool],
        medications: list[tuple[str, str]],
        observations: list[str],
        blocking_reasons: list[str],
        medication_note: str,
    ) -> tuple[Literal["yes", "no", "undetermined"], str, str]:
        """Đánh giá chỉ định trước, sau đó mới nêu hướng xử trí thuốc.

        Đây là luật có thể kiểm thử từ bản tóm tắt đã duyệt và guideline nội bộ;
        không dùng LLM để tự suy đoán một đơn thuốc.
        """
        if blocking_reasons:
            return (
                "undetermined",
                "Chưa thể kết luận an toàn về thuốc vì hồ sơ còn dữ liệu cần xác minh.",
                "Xử lý mâu thuẫn hoặc dữ liệu còn mở trước khi đề xuất thuốc.",
            )

        treated_conditions: list[str] = []
        if flags["diabetes"]:
            treated_conditions.append("đái tháo đường típ 2")
        if flags["hypertension"]:
            treated_conditions.append("tăng huyết áp")
        if flags["dyslipidemia"]:
            treated_conditions.append("rối loạn lipid máu")
        if flags["obesity"]:
            treated_conditions.append("béo phì")
        if flags["neuropathy"]:
            treated_conditions.append("bệnh lý thần kinh ngoại biên")
        if flags["fatty_liver"]:
            treated_conditions.append("gan nhiễm mỡ")
        if not treated_conditions:
            return (
                "undetermined",
                "Bản tóm tắt chưa có bệnh lý phù hợp với các phác đồ thuốc hiện có trong hệ thống.",
                "Bác sĩ xác nhận chẩn đoán và chọn guideline phù hợp trước khi kê thuốc.",
            )

        condition_text = " và ".join(treated_conditions)
        if not medications:
            if not flags["diabetes"] and not flags["hypertension"]:
                return (
                    "undetermined",
                    f"Hồ sơ xác nhận {condition_text}, nhưng chưa đủ dữ liệu để kết luận cần thuốc đặc hiệu.",
                    "Ưu tiên can thiệp lối sống theo căn cứ đã ánh xạ; bác sĩ bổ sung chỉ số chuyên biệt và đánh giá nguy cơ trước khi chọn thuốc.",
                )
            return (
                "yes",
                f"Có chỉ định xem xét điều trị bằng thuốc do hồ sơ đã xác nhận {condition_text}.",
                medication_note,
            )

        findings: list[str] = []
        recommendations: list[str] = []
        medication_names = "; ".join(item for item, _ in medications)
        medication_corpus = medication_names.casefold()

        if flags["diabetes"]:
            hba1c = self._numeric_observation(observations, "HbA1c")
            egfr = self._numeric_observation(observations, "eGFR")
            has_diabetes_drug = any(
                name in medication_corpus
                for name in ("metformin", "insulin", "gliclazid", "glimepirid", "sitagliptin", "empagliflozin")
            )
            if hba1c is None:
                findings.append("chưa có HbA1c đủ rõ để đánh giá mức kiểm soát")
                recommendations.append("xác nhận HbA1c và eGFR trước khi khởi trị hoặc chỉnh thuốc đái tháo đường")
            elif hba1c >= 7.0:
                findings.append(f"HbA1c {hba1c:g}% cao hơn mục tiêu chung dưới 7%")
                if has_diabetes_drug:
                    recommendations.append(
                        "rà soát tuân thủ, khả năng dung nạp và eGFR; cân nhắc tăng cường Metformin trong khoảng liều của phác đồ hoặc phối hợp thuốc khác"
                    )
                elif egfr is not None and egfr >= 45:
                    recommendations.append("cân nhắc khởi trị Metformin 500 mg một lần/ngày cùng hoặc ngay sau bữa ăn")
                elif egfr is not None and egfr < 30:
                    recommendations.append("không dùng Metformin do eGFR dưới 30; bác sĩ chọn nhóm thuốc khác sau đánh giá trực tiếp")
                else:
                    recommendations.append("chưa khởi trị Metformin cho đến khi xác nhận eGFR và chống chỉ định")
            else:
                findings.append(f"HbA1c {hba1c:g}% đang đạt mục tiêu chung dưới 7%")
                recommendations.append(
                    "tiếp tục phác đồ đái tháo đường hiện tại nếu người bệnh dung nạp"
                    if has_diabetes_drug
                    else "bác sĩ xác nhận lý do chưa dùng thuốc và mục tiêu HbA1c cá thể hóa"
                )

        if flags["hypertension"]:
            systolic = self._numeric_observation(observations, "huyết áp tâm thu")
            diastolic = self._numeric_observation(observations, "huyết áp tâm trương")
            has_antihypertensive = any(
                name in medication_corpus
                for name in ("amlodip", "losartan", "telmisartan", "enalapril", "perindopril", "nifedip", "thiazid")
            )
            if systolic is None or diastolic is None:
                findings.append("chưa đủ cặp huyết áp gần nhất để đánh giá mục tiêu")
                recommendations.append("bổ sung kết quả đo chuẩn trước khi khởi trị hoặc chỉnh thuốc huyết áp")
            else:
                high_risk_target = flags["diabetes"] or flags["ckd"]
                target_met = (
                    systolic < (130 if high_risk_target else 140)
                    and diastolic < (80 if high_risk_target else 90)
                )
                target_text = "dưới 130/80 mmHg" if high_risk_target else "dưới 140/90 mmHg"
                if target_met:
                    findings.append(f"huyết áp {systolic:g}/{diastolic:g} mmHg đạt mục tiêu {target_text}")
                    recommendations.append(
                        "tiếp tục phác đồ huyết áp hiện tại nếu người bệnh dung nạp"
                        if has_antihypertensive
                        else "tiếp tục theo dõi; bác sĩ xác nhận có cần thuốc duy trì hay không"
                    )
                else:
                    findings.append(f"huyết áp {systolic:g}/{diastolic:g} mmHg chưa đạt mục tiêu {target_text}")
                    recommendations.append(
                        "rà soát tuân thủ và cân nhắc điều chỉnh hoặc phối hợp thuốc hạ áp"
                        if has_antihypertensive
                        else "cân nhắc khởi trị Amlodipin 5 mg một lần/ngày sau khi bác sĩ kiểm tra chống chỉ định và nguy cơ"
                    )

        if flags["dyslipidemia"]:
            findings.append("chẩn đoán rối loạn lipid máu nhưng bản tóm tắt chưa đủ lipid máu và phân tầng nguy cơ")
            recommendations.append("bổ sung LDL-C, HDL-C, triglycerid và nguy cơ tim mạch trước khi chọn statin hoặc thuốc hạ lipid")
        if flags["obesity"]:
            findings.append("béo phì cần kế hoạch dinh dưỡng, vận động và thay đổi hành vi cá thể hóa")
            recommendations.append("không tự động thêm thuốc giảm cân khi chưa có BMI, vòng eo, chống chỉ định và đánh giá trực tiếp")
        if flags["fatty_liver"]:
            recommendations.append("không tự động thêm thuốc gan; ưu tiên kiểm soát chuyển hóa và đánh giá nguyên nhân")
        if flags["neuropathy"] and not any(name in medication_corpus for name in ("gabapentin", "pregabalin", "duloxetin")):
            recommendations.append("đánh giá mức độ đau và cảm giác bàn chân trước khi chọn thuốc điều trị triệu chứng thần kinh")

        assessment = (
            f"Có chỉ định tiếp tục điều trị thuốc cho {condition_text}. "
            + ("; ".join(findings) + "." if findings else "")
        )
        recommendation = (
            "ĐỀ XUẤT THEO PHÁC ĐỒ – CHỜ BÁC SĨ DUYỆT: "
            + "; ".join(dict.fromkeys(recommendations))
            + f". Thuốc đang ghi nhận: {medication_names}."
        )
        return "yes", assessment, recommendation

    @staticmethod
    def _safety_flags(review: ReviewResponse, medications: list[tuple[str, str]]) -> list[str]:
        warnings: list[str] = []
        if not medications:
            warnings.append("Chưa có thuốc trong bản tóm tắt đã duyệt.")
        for conflict in review.conflicts:
            if conflict.status not in {"resolved", "reviewed"}:
                warnings.append(conflict.description or "Còn mâu thuẫn dữ liệu cần bác sĩ xác nhận.")
        for item in review.data_quality_flags:
            if item.status == "open":
                warnings.append(item.message)
        return list(dict.fromkeys(item for item in warnings if item))

    def _personalization_summary(
        self,
        patient: PatientSummary,
        flags: dict[str, bool],
        observations: list[str],
    ) -> str:
        focus_map = (
            ("diabetes", "kiểm soát đường huyết"),
            ("hypertension", "kiểm soát huyết áp"),
            ("ckd", "an toàn chức năng thận"),
            ("dyslipidemia", "nguy cơ lipid máu"),
            ("obesity", "kiểm soát cân nặng"),
            ("neuropathy", "bảo vệ bàn chân"),
            ("fatty_liver", "giảm gánh nặng chuyển hóa cho gan"),
        )
        focuses = [label for key, label in focus_map if flags.get(key)]
        metrics: list[str] = []
        hba1c = self._numeric_observation(observations, "HbA1c")
        systolic = self._numeric_observation(observations, "huyết áp tâm thu")
        diastolic = self._numeric_observation(observations, "huyết áp tâm trương")
        egfr = self._numeric_observation(observations, "eGFR")
        if hba1c is not None:
            metrics.append(f"HbA1c {hba1c:g}%")
        if systolic is not None and diastolic is not None:
            metrics.append(f"huyết áp {systolic:g}/{diastolic:g} mmHg")
        if egfr is not None:
            metrics.append(f"eGFR {egfr:g} mL/phút/1,73 m²")
        age_text = f"{patient.age} tuổi" if patient.age is not None else "chưa rõ tuổi"
        focus_text = ", ".join(focuses) if focuses else "rà soát điều trị theo chẩn đoán đã duyệt"
        metric_text = "; ".join(metrics) if metrics else "chưa có đủ chỉ số mục tiêu trong bản tóm tắt"
        return f"Cá nhân hóa cho người bệnh {age_text}: trọng tâm {focus_text}. Dữ liệu quyết định: {metric_text}."

    def _deterministic_plan(
        self,
        patient: PatientSummary,
        flags: dict[str, bool],
        medications: list[tuple[str, str]],
        observations: list[str],
        allergies: list[str],
        blocking_reasons: list[str],
        guideline_label: str,
        clinical_basis: list[ClinicalBasisItem],
    ) -> tuple[CarePlanDraft, bool, list[str]]:
        morning, evening, medication_note, proposed_new_medication, proposal_flags = self._medication_schedule(
            patient,
            flags,
            medications,
            observations,
            allergies,
            blocking_reasons,
        )
        medication_need, medication_assessment, medication_recommendation = self._medication_assessment(
            flags,
            medications,
            observations,
            blocking_reasons,
            medication_note,
        )
        personalization_summary = self._personalization_summary(patient, flags, observations)

        good: list[str] = []
        bad: list[str] = []
        if flags["diabetes"]:
            good.append("Ăn đúng bữa; chia lượng tinh bột đều giữa các bữa; ưu tiên rau, đạm nạc và thực phẩm ít chế biến.")
            bad.append("Hạn chế nước ngọt, bánh kẹo và không dồn nhiều tinh bột vào một bữa.")
        if flags["hypertension"]:
            bad.append("Giảm muối, món kho mặn, đồ muối chua và nước chấm.")
        if flags["ckd"]:
            good.append("Lượng đạm, kali và nước thực hiện theo chỉ định riêng của bác sĩ.")
            bad.append("Không tự dùng muối thay thế chứa kali hoặc tự tăng lượng nước uống.")
        if flags["dyslipidemia"]:
            good.append("Ưu tiên cá, đậu, hạt và dầu thực vật với khẩu phần phù hợp.")
            bad.append("Hạn chế mỡ động vật, nội tạng và thực phẩm nhiều chất béo bão hòa.")
        if flags["obesity"]:
            good.append("Dùng khẩu phần có kiểm soát, ghi lại bữa ăn và duy trì thay đổi hành vi lâu dài.")
            bad.append("Không nhịn đói hoặc áp dụng chế độ giảm cân cực đoan.")
        if flags["fatty_liver"]:
            good.append("Ưu tiên bữa ăn ít chế biến để hỗ trợ kiểm soát đường huyết và cân nặng.")
            bad.append("Tránh rượu bia; hạn chế đồ uống nhiều đường và món nhiều mỡ.")
        if not good:
            good.append("Ăn đa dạng, đúng bữa; ưu tiên rau, đạm phù hợp và thực phẩm ít chế biến.")
        if not bad:
            bad.append("Hạn chế rượu bia, nước ngọt và thực phẩm chế biến sẵn.")

        exercise_parts: list[str] = []
        if flags["hypertension"]:
            exercise_parts.append("Vận động mức vừa 30-60 phút mỗi ngày nếu dung nạp; có thể chia thành các buổi ngắn.")
        elif flags["obesity"]:
            exercise_parts.append("Tăng hoạt động thể lực từng bước theo khả năng và duy trì đều trong tuần.")
        else:
            exercise_parts.append("Vận động vừa sức và duy trì đều trong tuần; có thể chia thành các buổi ngắn.")
        if flags["neuropathy"]:
            exercise_parts.append("Ưu tiên bài tập ít gây tì đè; quan sát bàn chân hằng ngày, mang giày dép vừa chân và không đi chân đất.")
        if flags["fatty_liver"]:
            exercise_parts.append("Duy trì vận động thường xuyên để hỗ trợ kiểm soát chuyển hóa và gan nhiễm mỡ.")
        exercise_parts.append("Dừng tập khi đau ngực, khó thở, choáng hoặc có tổn thương bàn chân.")
        exercise = " ".join(exercise_parts)

        monitoring: list[str] = []
        if flags["diabetes"]:
            monitoring.append("Theo dõi đường huyết theo lịch; nếu đường huyết dưới 3,9 mmol/L hoặc có run tay, vã mồ hôi, dùng 15 g đường tác dụng nhanh và kiểm tra lại sau 15 phút.")
        if flags["hypertension"]:
            monitoring.append("Đo và ghi lại huyết áp đúng kỹ thuật; huyết áp từ 180/110 mmHg kèm đau ngực, khó thở hoặc triệu chứng thần kinh cần cấp cứu.")
        if flags["neuropathy"]:
            monitoring.append("Khám sớm khi bàn chân có vết xước, phỏng nước, sưng nóng, đổi màu hoặc dấu nhiễm trùng.")
        monitoring.append("Gọi 115 khi đau ngực, khó thở, yếu liệt, rối loạn ý thức hoặc co giật.")

        basis_ids = {
            section: [item.basis_id for item in clinical_basis if section in item.applies_to]
            for section in ("medication", "diet", "exercise", "warning")
        }

        return CarePlanDraft(
            doctor_greeting=(
                f"Bác {patient.pseudonym}, hướng dẫn này tập trung vào các vấn đề riêng trong hồ sơ đã duyệt. "
                "Không tự thay đổi thuốc khi chưa trao đổi với bác sĩ."
            ),
            personalization_summary=personalization_summary,
            medication_need=medication_need,
            medication_assessment=medication_assessment,
            medication_recommendation=medication_recommendation,
            medication_basis_ids=basis_ids["medication"],
            morning_meds=morning,
            evening_meds=evening,
            medication_note=medication_note,
            diet_good=" ".join(good),
            diet_bad=" ".join(bad),
            diet_basis_ids=basis_ids["diet"],
            exercise=exercise,
            exercise_basis_ids=basis_ids["exercise"],
            emergency_warning=" ".join(monitoring),
            warning_basis_ids=basis_ids["warning"],
            follow_up="Tái khám theo lịch bác sĩ ghi trên phiếu; khám sớm hơn khi triệu chứng hoặc chỉ số xấu đi.",
            follow_up_days=None,
            guideline_citation=guideline_label,
        ), proposed_new_medication, proposal_flags

    @staticmethod
    def _acceptable_vietnamese(value: str, max_length: int) -> bool:
        if not value.strip() or len(value) > max_length:
            return False
        forbidden = (
            "the patient", "should take", "once daily", "twice daily", "diet plan",
            "exercise plan", "follow-up", "grounded", "source:", "active medication",
        )
        lowered = value.casefold()
        return not any(phrase in lowered for phrase in forbidden)

    async def _try_llm_rewrite(
        self,
        base_plan: CarePlanDraft,
        memory: PatientMemory,
        guideline_context: str,
    ) -> CarePlanDraft | None:
        if self.settings.agent_generation_backend not in {"openai", "llm"}:
            return None
        api_key = self.settings.llm_api_key or os.environ.get("LLM_API_KEY", "")
        if not api_key:
            return None

        payload: dict[str, Any] = {
            "model": self.settings.llm_model_name or "mistral-small-latest",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Bạn là agent hỗ trợ bệnh lý cho bác sĩ. Chỉ dùng BẢN TÓM TẮT ĐÃ KÝ DUYỆT và GUIDELINE. "
                        "Viết ngắn gọn, dễ hiểu, hoàn toàn bằng tiếng Việt; mỗi mục tối đa hai câu. Không thêm thuốc, liều, chẩn đoán, "
                        "chỉ số hoặc lịch tái khám mới. Trả duy nhất JSON đúng cấu trúc BẢN NHÁP."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "ban_tom_tat_da_duyet": [
                                {"nhom": item.category, "noi_dung": item.text}
                                for item in memory.items
                            ],
                            "guideline": guideline_context,
                            "ban_nhap": base_plan.model_dump(mode="json"),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 2600,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post(
                    f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"].strip()
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                raw = re.sub(r"^json\s*", "", raw).strip()
            candidate = CarePlanDraft.model_validate(json.loads(raw))
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Không thể biên tập phác đồ bằng LLM: {}", exc)
            return None

        # Thuốc, lời dặn, tái khám và thông tin guideline không cho LLM ghi đè.
        candidate.doctor_greeting = base_plan.doctor_greeting
        candidate.personalization_summary = base_plan.personalization_summary
        candidate.medication_need = base_plan.medication_need
        candidate.medication_assessment = base_plan.medication_assessment
        candidate.medication_recommendation = base_plan.medication_recommendation
        candidate.medication_basis_ids = base_plan.medication_basis_ids
        candidate.morning_meds = base_plan.morning_meds
        candidate.evening_meds = base_plan.evening_meds
        candidate.medication_note = base_plan.medication_note
        candidate.diet_basis_ids = base_plan.diet_basis_ids
        candidate.exercise_basis_ids = base_plan.exercise_basis_ids
        candidate.warning_basis_ids = base_plan.warning_basis_ids
        candidate.follow_up = base_plan.follow_up
        candidate.follow_up_days = None
        candidate.guideline_citation = base_plan.guideline_citation
        limits = {
            "diet_good": 320,
            "diet_bad": 320,
            "exercise": 360,
            "emergency_warning": 450,
        }
        for field_name, limit in limits.items():
            if not self._acceptable_vietnamese(getattr(candidate, field_name), limit):
                setattr(candidate, field_name, getattr(base_plan, field_name))
        return candidate

    @staticmethod
    def _citation_ids(memory: PatientMemory) -> list[str]:
        citation_ids: list[str] = []
        for item in memory.items:
            for citation in item.citations:
                if citation.citation_id not in citation_ids:
                    citation_ids.append(citation.citation_id)
        return citation_ids

    async def generate_care_plan(
        self,
        *,
        patient: PatientSummary,
        approved_review: ReviewResponse,
        approved_memory: PatientMemory,
    ) -> CarePlanResponse:
        if approved_review.patient_id != patient.patient_id or approved_review.status != "approved":
            raise ValueError("Phác đồ chỉ được tạo từ bản tóm tắt đã ký duyệt của đúng bệnh nhân.")
        if approved_memory.patient_id != patient.patient_id:
            raise ValueError("Bản tóm tắt đã duyệt không thuộc bệnh nhân hiện tại.")
        if approved_memory.source_review_version_id != approved_review.review_version_id:
            raise ValueError("Bản tóm tắt đã duyệt không khớp phiên bản review.")

        conditions = self._conditions(approved_memory)
        medications = self._medications(approved_memory)
        all_observations = [_vietnamize(text) for text in self._items(approved_memory, "recent_results")]
        observations = self._observations(approved_memory)
        allergies = self._allergies(approved_memory)
        condition_flags = self._condition_flags(conditions)
        guideline_files = self._guideline_files(condition_flags, medications)
        clinical_basis = self._clinical_basis(condition_flags, medications)
        guideline_label = (
            f"Đã đối chiếu {len(clinical_basis)} căn cứ chuyên môn áp dụng trực tiếp cho ca bệnh."
            if clinical_basis
            else self._guideline_label(guideline_files)
        )
        safety_flags = self._safety_flags(approved_review, medications)
        open_conflicts = [
            item.description
            for item in approved_review.conflicts
            if item.status not in {"resolved", "reviewed"} and item.description
        ]
        open_quality_flags = [item.message for item in approved_review.data_quality_flags if item.status == "open"]
        conflicts = [item.description for item in approved_review.conflicts if item.description]
        base_plan, proposed_new_medication, proposal_flags = self._deterministic_plan(
            patient,
            condition_flags,
            medications,
            all_observations,
            allergies,
            open_conflicts + open_quality_flags,
            guideline_label,
            clinical_basis,
        )
        safety_flags.extend(flag for flag in proposal_flags if flag not in safety_flags)
        llm_plan = await self._try_llm_rewrite(
            base_plan,
            approved_memory,
            self._guideline_context(guideline_files),
        )

        return CarePlanResponse(
            status="needs_review" if safety_flags or proposed_new_medication else "draft",
            generation_mode="llm_grounded" if llm_plan else "deterministic_grounded",
            agent_type="Agent hỗ trợ bệnh lý",
            data_watermark=approved_review.data_watermark,
            disclaimer=(
                "Bản nháp hỗ trợ bác sĩ xây dựng hướng dẫn điều trị và chăm sóc. "
                "Bác sĩ cần chỉnh sửa, kiểm tra và chốt trước khi phát hành."
            ),
            safety_flags=safety_flags,
            guideline_citations=[
                f"{item.source_title} - {item.section}"
                for item in clinical_basis
            ] or [guideline_label],
            evidence_citation_ids=self._citation_ids(approved_memory),
            clinical_basis=clinical_basis,
            data_summary=CarePlanDataSummary(
                conditions=conditions,
                medications=[item for item, _ in medications],
                latest_observations=observations,
                allergies=allergies,
                conflicts=conflicts,
            ),
            plan=llm_plan or base_plan,
        )


care_plan_agent = ClinicalCarePlanAgent()
