"""Generate a restrained, print-ready Vietnamese clinical summary PDF.

The exported document intentionally contains only the approved clinical content.
Evidence citations remain available in the review application but are not printed.
"""

from __future__ import annotations

import html
import os
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.clinical.canonical import PatientSummary, ReviewResponse

NAVY = colors.HexColor("#172033")
SLATE = colors.HexColor("#475569")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#D9E0E8")
SURFACE = colors.HexColor("#F6F8FA")
TEAL = colors.HexColor("#0F766E")
TEAL_LIGHT = colors.HexColor("#ECFDF5")
AMBER = colors.HexColor("#B45309")
AMBER_LIGHT = colors.HexColor("#FFF7ED")
RED = colors.HexColor("#B42318")
RED_LIGHT = colors.HexColor("#FEF3F2")
WHITE = colors.white

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 18 * mm
RIGHT_MARGIN = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN


def _font_candidates() -> list[dict[str, str]]:
    configured = os.getenv("CLINICAL_PDF_FONT_DIR")
    candidates: list[dict[str, str]] = []
    if configured:
        root = Path(configured)
        candidates.append(
            {
                "regular": str(root / "DejaVuSans.ttf"),
                "bold": str(root / "DejaVuSans-Bold.ttf"),
                "italic": str(root / "DejaVuSans-Oblique.ttf"),
            }
        )

    candidates.extend(
        [
            {
                "regular": r"C:\Windows\Fonts\arial.ttf",
                "bold": r"C:\Windows\Fonts\arialbd.ttf",
                "italic": r"C:\Windows\Fonts\ariali.ttf",
            },
            {
                "regular": r"C:\Windows\Fonts\DejaVuSans.ttf",
                "bold": r"C:\Windows\Fonts\DejaVuSans-Bold.ttf",
                "italic": r"C:\Windows\Fonts\DejaVuSans-Oblique.ttf",
            },
            {
                "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "italic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            },
            {
                "regular": "/usr/share/fonts/dejavu/DejaVuSans.ttf",
                "bold": "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
                "italic": "/usr/share/fonts/dejavu/DejaVuSans-Oblique.ttf",
            },
        ]
    )
    return candidates


def _register_fonts() -> tuple[str, str, str]:
    """Register a Vietnamese-capable font family on Windows and Linux."""
    for candidate in _font_candidates():
        if not all(Path(path).is_file() for path in candidate.values()):
            continue
        try:
            pdfmetrics.registerFont(TTFont("ClinicalSans", candidate["regular"]))
            pdfmetrics.registerFont(TTFont("ClinicalSans-Bold", candidate["bold"]))
            pdfmetrics.registerFont(TTFont("ClinicalSans-Italic", candidate["italic"]))
            pdfmetrics.registerFontFamily(
                "ClinicalSans",
                normal="ClinicalSans",
                bold="ClinicalSans-Bold",
                italic="ClinicalSans-Italic",
                boldItalic="ClinicalSans-Bold",
            )
            return "ClinicalSans", "ClinicalSans-Bold", "ClinicalSans-Italic"
        except Exception:
            continue

    # Docker installs DejaVu Sans; this remains a last-resort fallback.
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


FONT_REGULAR, FONT_BOLD, FONT_ITALIC = _register_fonts()


def _safe(value: object | None) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=False).replace("\n", "<br/>")


def _format_date(value: str | None, *, include_time: bool = False) -> str:
    if not value:
        return "Chưa ghi nhận"
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%d/%m/%Y - %H:%M") if include_time else parsed.strftime("%d/%m/%Y")
    except ValueError:
        return raw


def _clean_claim_text(text: str) -> str:
    replacements = {
        "Status: finished": "Đã hoàn thành khám",
        "Status: active": "Đang duy trì",
        "Status: completed": "Đã kết thúc đợt",
        "status: active": "Đang duy trì",
        "status: completed": "Đã hoàn thành",
    }
    result = str(text or "").strip()
    for source, target in replacements.items():
        result = result.replace(source, target)
    medical_terms = {
        " (Type 2 diabetes mellitus)": "",
        " (Hypertension)": "",
        " (Chronic kidney disease)": "",
        " (Obesity)": "",
        "Type 2 diabetes mellitus": "Đái tháo đường típ 2",
        "Hypertension": "Tăng huyết áp",
        "Chronic kidney disease": "Bệnh thận mạn",
        "Obesity": "Béo phì",
        "type 2": "típ 2",
    }
    for source, target in medical_terms.items():
        result = result.replace(source, target)
    return result


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ClinicalTitle",
            parent=base["Title"],
            fontName=FONT_BOLD,
            fontSize=17,
            leading=21,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=2 * mm,
        ),
        "subtitle": ParagraphStyle(
            "ClinicalSubtitle",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=13,
            textColor=MUTED,
        ),
        "label": ParagraphStyle(
            "ClinicalLabel",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=7.2,
            leading=10,
            textColor=MUTED,
        ),
        "value": ParagraphStyle(
            "ClinicalValue",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=8.8,
            leading=12,
            textColor=NAVY,
        ),
        "value_bold": ParagraphStyle(
            "ClinicalValueBold",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=12,
            textColor=NAVY,
        ),
        "section": ParagraphStyle(
            "ClinicalSection",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=10.2,
            leading=13,
            textColor=NAVY,
        ),
        "section_number": ParagraphStyle(
            "ClinicalSectionNumber",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=11,
            textColor=WHITE,
            alignment=TA_CENTER,
        ),
        "body": ParagraphStyle(
            "ClinicalBody",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=9.2,
            leading=14,
            textColor=NAVY,
            leftIndent=4 * mm,
            firstLineIndent=-3 * mm,
            spaceAfter=1.6 * mm,
        ),
        "note": ParagraphStyle(
            "ClinicalNote",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=8.8,
            leading=13,
            textColor=NAVY,
        ),
        "note_label": ParagraphStyle(
            "ClinicalNoteLabel",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=8.2,
            leading=11,
            textColor=TEAL,
            spaceAfter=1 * mm,
        ),
        "small": ParagraphStyle(
            "ClinicalSmall",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
        ),
        "approval": ParagraphStyle(
            "ClinicalApproval",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=10,
            leading=13,
            textColor=TEAL,
        ),
    }


def _page_chrome(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(TEAL)
    canvas.rect(0, PAGE_HEIGHT - 3 * mm, PAGE_WIDTH, 3 * mm, stroke=0, fill=1)

    canvas.setFont(FONT_BOLD, 8.2)
    canvas.setFillColor(NAVY)
    canvas.drawString(LEFT_MARGIN, PAGE_HEIGHT - 12 * mm, "HỒ SƠ LÂM SÀNG")
    canvas.setFont(FONT_REGULAR, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 12 * mm, "TÀI LIỆU Y KHOA BẢO MẬT")
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(LEFT_MARGIN, PAGE_HEIGHT - 16 * mm, PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 16 * mm)

    canvas.line(LEFT_MARGIN, 14 * mm, PAGE_WIDTH - RIGHT_MARGIN, 14 * mm)
    canvas.setFont(FONT_REGULAR, 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(LEFT_MARGIN, 9 * mm, "Bản tóm tắt điều trị đã được phê duyệt")
    canvas.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, 9 * mm, f"Trang {doc.page}")
    canvas.restoreState()


def _info_table(data: list[list[Paragraph]]) -> Table:
    table = Table(data, colWidths=[27 * mm, 59 * mm, 27 * mm, 61 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _section_heading(number: int, title: str, styles: dict[str, ParagraphStyle]) -> Table:
    table = Table(
        [[Paragraph(f"{number:02d}", styles["section_number"]), Paragraph(_safe(title), styles["section"])]],
        colWidths=[12 * mm, CONTENT_WIDTH - 12 * mm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), TEAL),
                ("BACKGROUND", (1, 0), (1, 0), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 2),
                ("RIGHTPADDING", (0, 0), (0, 0), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (1, 0), (1, 0), 8),
            ]
        )
    )
    return table


def _notice_box(
    label: str,
    text: str,
    styles: dict[str, ParagraphStyle],
    *,
    background=TEAL_LIGHT,
    border=colors.HexColor("#A7D9D2"),
    label_color=TEAL,
) -> Table:
    label_style = ParagraphStyle(f"NoticeLabel-{label}", parent=styles["note_label"], textColor=label_color)
    table = Table(
        [[Paragraph(_safe(label), label_style)], [Paragraph(_safe(text), styles["note"])]],
        colWidths=[CONTENT_WIDTH],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.7, border),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def generate_review_pdf(review: ReviewResponse, patient: PatientSummary | None = None) -> bytes:
    """Return an A4 PDF containing the approved summary without citations."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=21 * mm,
        bottomMargin=19 * mm,
        title=f"Bản tóm tắt điều trị - {review.patient_id}",
        author="Clinical Review Copilot",
        subject="Bản tóm tắt điều trị đã được bác sĩ phê duyệt",
    )
    styles = _styles()
    story: list = []

    story.append(Paragraph("BẢN TÓM TẮT ĐIỀU TRỊ", styles["title"]))
    story.append(
        Paragraph(
            "Phiếu tổng hợp thông tin lâm sàng đã được bác sĩ kiểm tra và phê duyệt.",
            styles["subtitle"],
        )
    )
    story.append(Spacer(1, 5 * mm))

    patient_name = patient.pseudonym if patient else review.patient_id
    patient_age = f"{patient.age} tuổi" if patient and patient.age is not None else "Chưa ghi nhận"
    if patient and patient.sex == "male":
        patient_sex = "Nam"
    elif patient and patient.sex == "female":
        patient_sex = "Nữ"
    elif patient and patient.sex == "other":
        patient_sex = "Khác"
    else:
        patient_sex = "Chưa ghi nhận"
    primary_condition = _clean_claim_text(
        (patient.primary_condition if patient else None) or "Chưa ghi nhận"
    )
    coverage_start = _format_date(review.coverage.start_date)
    coverage_end = _format_date(review.coverage.end_date)

    label = styles["label"]
    value = styles["value"]
    value_bold = styles["value_bold"]
    story.append(
        _info_table(
            [
                [Paragraph("HỌ VÀ TÊN", label), Paragraph(_safe(patient_name), value_bold),
                 Paragraph("MÃ BỆNH NHÂN", label), Paragraph(_safe(review.patient_id), value_bold)],
                [Paragraph("TUỔI", label), Paragraph(_safe(patient_age), value),
                 Paragraph("GIỚI TÍNH", label), Paragraph(_safe(patient_sex), value)],
                [Paragraph("CHẨN ĐOÁN CHÍNH", label), Paragraph(_safe(primary_condition), value),
                 Paragraph("TRẠNG THÁI", label),
                 Paragraph("<font color='#0F766E'><b>ĐÃ PHÊ DUYỆT</b></font>", value)],
                [Paragraph("KHOẢNG DỮ LIỆU", label),
                 Paragraph(f"{_safe(coverage_start)} đến {_safe(coverage_end)}", value),
                 Paragraph("SỐ LƯỢT KHÁM", label), Paragraph(str(review.coverage.encounter_count), value)],
                [Paragraph("PHIÊN BẢN", label), Paragraph(f"v{review.version}", value),
                 Paragraph("NGÀY PHÊ DUYỆT", label),
                 Paragraph(_safe(_format_date(review.approved_at or review.updated_at)), value)],
            ]
        )
    )
    story.append(Spacer(1, 6 * mm))

    section_titles = {
        "patient_overview": "Tổng quan diễn tiến bệnh nhân",
        "active_conditions": "Vấn đề lâm sàng và chẩn đoán",
        "current_medications": "Thuốc và phác đồ điều trị",
        "recent_results": "Kết quả cận lâm sàng gần đây",
        "changes_to_review": "Thay đổi cần theo dõi",
        "data_gaps": "Thông tin cần bổ sung",
    }

    for section_number, section in enumerate(review.sections, start=1):
        title = section_titles.get(section.section_code, section.title or "Nội dung lâm sàng")
        opening: list = [_section_heading(section_number, title, styles), Spacer(1, 2.5 * mm)]
        if section.clinician_text and section.clinician_text.strip():
            opening.extend(
                [_notice_box("Ghi chú của bác sĩ", section.clinician_text.strip(), styles), Spacer(1, 2.5 * mm)]
            )

        # Deduplicate claims and clean trend statements
        raw_claims = section.claims or []
        clean_claims = []
        seen_claim_keys = set()
        for clm in raw_claims:
            clm_text = _clean_claim_text(clm.text or "")
            if ";" in clm_text and "diễn tiến" in clm_text.lower():
                parts = [p.strip() for p in clm_text.split(";")]
                seen_parts = set()
                uniq_parts = []
                for p in parts:
                    norm_p = re.sub(r"(\d+)\.0(?=\s|$|[^\d])", r"\1", p).lower().strip()
                    if norm_p not in seen_parts:
                        seen_parts.add(norm_p)
                        uniq_parts.append(p)
                clm_text = "; ".join(uniq_parts)
                if not clm_text.endswith("."):
                    clm_text += "."

            t = clm_text.lower().replace("\n", " ").strip()
            sec_code = section.section_code or ""
            if sec_code == "current_medications" or "thuốc" in t:
                clean_med = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", t)
                clean_med = re.sub(r"thuốc(?:\s+hiện\s+tại)?:\s*", "", clean_med)
                clean_med = re.sub(r"(?:trạng thái|ghi nhận|đang duy trì|đang sử dụng|active|stopped|discontinued).*", "", clean_med)
                clean_med = re.sub(r"\(.*?\)", "", clean_med).strip()
                med_match = re.search(r"^([a-z\s]+?\d+(?:\.\d+)?\s*(?:mg|g|ml|mcg|ui|iu)?)", clean_med)
                if med_match:
                    drug_key = re.sub(r"\s+", " ", med_match.group(1)).strip()
                    norm_key = f"med:{drug_key}"
                else:
                    norm_key = f"med:{clean_med[:30].strip()}"
            elif sec_code == "recent_results" or "xét nghiệm" in t:
                date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", t)
                date_key = date_match.group(1) if date_match else "no_date"
                without_date = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", t)
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

                norm_key = f"lab:{test_key}:{date_key}:{val_norm}"
            elif sec_code == "active_conditions" or "chẩn đoán" in t:
                cond_clean = re.sub(r"\(.*?\)", "", t)
                cond_clean = re.sub(r"chẩn đoán/tình trạng bệnh:\s*", "", cond_clean)
                cond_clean = re.sub(r"ghi nhận\s+\d{4}-\d{2}-\d{2}", "", cond_clean).strip()
                norm_key = f"cond:{cond_clean}"
            else:
                norm_key = re.sub(r"(\d+)\.0(?=\s|$|[^\d])", r"\1", clm_text).lower().strip()
                norm_key = re.sub(r"\s+", " ", norm_key)

            if norm_key not in seen_claim_keys:
                seen_claim_keys.add(norm_key)
                clean_claims.append((clm_text, clm.status))

        if clean_claims:
            first_text, first_status_code = clean_claims[0]
            first_status = ""
            if first_status_code != "verified":
                first_status = " <font color='#B45309'><b>[Cần kiểm tra]</b></font>"
            opening.append(
                Paragraph(f"- {_safe(first_text)}{first_status}", styles["body"])
            )
            story.append(KeepTogether(opening))

            for c_text, c_status_code in clean_claims[1:]:
                status = ""
                if c_status_code != "verified":
                    status = " <font color='#B45309'><b>[Cần kiểm tra]</b></font>"
                story.append(Paragraph(f"- {_safe(c_text)}{status}", styles["body"]))
        else:
            opening.append(Paragraph("Chưa ghi nhận thông tin trong mục này.", styles["note"]))
            story.append(KeepTogether(opening))

        story.append(Spacer(1, 3.5 * mm))

    severity_labels = {
        "low": "thấp",
        "moderate": "trung bình",
        "high": "cao",
        "unknown": "chưa xác định",
    }
    interaction_items = [
        f"Tương tác thuốc - mức {severity_labels.get(item.severity, item.severity)}: {item.description}"
        for item in review.drug_interactions
        if item.status not in {"not_applicable", "superseded"}
    ]
    conflict_items = [
        f"Mâu thuẫn dữ liệu: {item.description}" + (" (đã xử lý)" if item.status == "resolved" else "")
        for item in review.conflicts
    ]
    warning_items = interaction_items + conflict_items
    if warning_items:
        warning_text = "<br/>".join(f"- {_safe(item)}" for item in warning_items)
        warning_label_style = ParagraphStyle(
            "ClinicalWarningLabel", parent=styles["note_label"], textColor=RED
        )
        warning_box = Table(
            [[Paragraph("CẢNH BÁO VÀ ĐIỂM CẦN LƯU Ý", warning_label_style)],
             [Paragraph(warning_text, styles["note"])]],
            colWidths=[CONTENT_WIDTH],
            hAlign="LEFT",
        )
        warning_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), RED_LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#FDA29B")),
                    ("TEXTCOLOR", (0, 0), (0, 0), RED),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.extend([KeepTogether([warning_box]), Spacer(1, 4 * mm)])

    quality_items = [item.message for item in review.data_quality_flags if item.status not in {"verified", "dismissed"}]
    if quality_items:
        quality_text = "\n".join(f"- {item}" for item in quality_items)
        story.extend(
            [
                _notice_box(
                    "Thông tin cần kiểm tra thêm",
                    quality_text,
                    styles,
                    background=AMBER_LIGHT,
                    border=colors.HexColor("#FED7AA"),
                    label_color=AMBER,
                ),
                Spacer(1, 4 * mm),
            ]
        )

    approval_time = _format_date(review.approved_at or review.updated_at, include_time=True)
    approval_content = [
        [Paragraph("ĐÃ PHÊ DUYỆT", styles["approval"])],
        [Paragraph(
            "Bác sĩ lâm sàng xác nhận đã kiểm tra nội dung tóm tắt và chịu trách nhiệm chuyên môn đối với quyết định điều trị.",
            styles["note"],
        )],
        [Paragraph(
            f"Thời gian phê duyệt: <b>{_safe(approval_time)}</b><br/>"
            f"Mã phiên bản: {_safe(review.review_version_id)}",
            styles["small"],
        )],
    ]
    approval_box = Table(approval_content, colWidths=[CONTENT_WIDTH], hAlign="LEFT")
    approval_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), TEAL_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.9, colors.HexColor("#7DD3C7")),
                ("LINEBEFORE", (0, 0), (0, -1), 3, TEAL),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(KeepTogether([approval_box]))
    story.append(Spacer(1, 2.5 * mm))
    story.append(
        Paragraph(
            _safe(review.disclaimer or "Tài liệu phục vụ theo dõi và điều trị. Bác sĩ chịu trách nhiệm cho mọi quyết định chuyên môn."),
            styles["small"],
        )
    )

    doc.build(story, onFirstPage=_page_chrome, onLaterPages=_page_chrome)
    pdf_content = buffer.getvalue()
    buffer.close()
    return pdf_content
