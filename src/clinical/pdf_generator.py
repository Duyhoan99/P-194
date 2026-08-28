"""Generate a print-ready Vietnamese clinical summary PDF in clean monochrome format.

Follows the standard Vietnamese Bản Tóm Tắt Bệnh Án layout:
  I.   Thông tin hành chính
  II.  Chẩn đoán & vấn đề lâm sàng
  III. Thuốc điều trị
  IV.  Kết quả cận lâm sàng (theo từng chỉ số & ngày xét nghiệm)
  V.   Điểm cần theo dõi / Cảnh báo  (chỉ in nếu có nội dung)

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
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.clinical.canonical import PatientSummary, ReviewResponse

# ── Monochrome / Grayscale Palette ──────────────────────────────────────────
BLACK       = colors.HexColor("#0F172A")
DARK        = colors.HexColor("#1E293B")
SLATE       = colors.HexColor("#334155")
MUTED       = colors.HexColor("#64748B")
LINE_DARK   = colors.HexColor("#475569")
LINE        = colors.HexColor("#94A3B8")
LINE_LIGHT  = colors.HexColor("#E2E8F0")
SURFACE     = colors.HexColor("#F1F5F9")
SURFACE_ALT = colors.HexColor("#F8FAFC")
WHITE       = colors.white

PAGE_WIDTH, PAGE_HEIGHT = A4
LM = 16 * mm   # left margin
RM = 16 * mm   # right margin
CW = PAGE_WIDTH - LM - RM   # content width


# ── Font registration ─────────────────────────────────────────────────────────
def _font_candidates() -> list[dict[str, str]]:
    configured = os.getenv("CLINICAL_PDF_FONT_DIR")
    candidates: list[dict[str, str]] = []
    if configured:
        root = Path(configured)
        candidates.append({
            "regular": str(root / "DejaVuSans.ttf"),
            "bold":    str(root / "DejaVuSans-Bold.ttf"),
            "italic":  str(root / "DejaVuSans-Oblique.ttf"),
        })
    candidates.extend([
        {"regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "bold":    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "italic":  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"},
        {"regular": "/usr/share/fonts/dejavu/DejaVuSans.ttf",
         "bold":    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
         "italic":  "/usr/share/fonts/dejavu/DejaVuSans-Oblique.ttf"},
        {"regular": r"C:\Windows\Fonts\arial.ttf",
         "bold":    r"C:\Windows\Fonts\arialbd.ttf",
         "italic":  r"C:\Windows\Fonts\ariali.ttf"},
        {"regular": r"C:\Windows\Fonts\DejaVuSans.ttf",
         "bold":    r"C:\Windows\Fonts\DejaVuSans-Bold.ttf",
         "italic":  r"C:\Windows\Fonts\DejaVuSans-Oblique.ttf"},
    ])
    return candidates


def _register_fonts() -> tuple[str, str, str]:
    for c in _font_candidates():
        reg = c.get("regular", "")
        if not Path(reg).is_file():
            continue
        bold = c.get("bold", "")
        bold_path = bold if Path(bold).is_file() else reg
        italic = c.get("italic", "")
        italic_path = italic if Path(italic).is_file() else reg
        try:
            pdfmetrics.registerFont(TTFont("CS", reg))
            pdfmetrics.registerFont(TTFont("CS-B", bold_path))
            pdfmetrics.registerFont(TTFont("CS-I", italic_path))
            pdfmetrics.registerFontFamily("CS", normal="CS", bold="CS-B",
                                          italic="CS-I", boldItalic="CS-B")
            return "CS", "CS-B", "CS-I"
        except Exception:
            continue
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


FONT, FONT_B, FONT_I = _register_fonts()
FONT_REGULAR, FONT_BOLD, FONT_ITALIC = FONT, FONT_B, FONT_I


# ── Helpers ───────────────────────────────────────────────────────────────────
def _safe(v: object | None) -> str:
    if v is None:
        return ""
    return html.escape(str(v), quote=False).replace("\n", "<br/>")


def _fmt_date(v: str | None, *, time: bool = False) -> str:
    if not v:
        return "Chưa ghi nhận"
    raw = v.strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M") if time else dt.strftime("%d/%m/%Y")
    except ValueError:
        return raw


_MED_REPLACEMENTS = {
    " (Type 2 diabetes mellitus)": "",
    " (Hypertension)": "",
    " (Chronic kidney disease)": "",
    "Type 2 diabetes mellitus": "Đái tháo đường típ 2",
    "Hypertension": "Tăng huyết áp",
    "Chronic kidney disease": "Bệnh thận mạn",
    "Status: finished": "Đã hoàn thành",
    "Status: active": "Đang duy trì",
    "Status: completed": "Đã kết thúc đợt",
    "status: active": "Đang duy trì",
    "status: completed": "Đã hoàn thành",
    "type 2": "típ 2",
}


def _clean(text: str) -> str:
    result = str(text or "").strip()
    for src, tgt in _MED_REPLACEMENTS.items():
        result = result.replace(src, tgt)
    return result


def _clean_lab_val(v: str) -> str:
    v = v.strip().rstrip(".")
    v = re.sub(r"(\d+)\.0(?=\s|$|[^\d])", r"\1", v)
    v = v.replace("mm[Hg]", "mmHg")
    return _clean(v)


# ── Styles ────────────────────────────────────────────────────────────────────
def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "doc_title": ParagraphStyle("DocTitle", parent=base["Normal"],
            fontName=FONT_B, fontSize=15, leading=19,
            textColor=BLACK, alignment=TA_LEFT, spaceAfter=1*mm),
        "doc_sub": ParagraphStyle("DocSub", parent=base["Normal"],
            fontName=FONT, fontSize=8.5, leading=12,
            textColor=MUTED, spaceAfter=2.5*mm),
        "lbl": ParagraphStyle("Lbl", parent=base["Normal"],
            fontName=FONT_B, fontSize=7, leading=10, textColor=MUTED),
        "val": ParagraphStyle("Val", parent=base["Normal"],
            fontName=FONT, fontSize=8.5, leading=11.5, textColor=BLACK),
        "val_b": ParagraphStyle("ValB", parent=base["Normal"],
            fontName=FONT_B, fontSize=8.8, leading=12, textColor=BLACK),
        "sec_hdr_num": ParagraphStyle("SecHdrNum", parent=base["Normal"],
            fontName=FONT_B, fontSize=9, leading=12,
            textColor=WHITE, alignment=TA_CENTER),
        "sec_hdr_title": ParagraphStyle("SecHdrTitle", parent=base["Normal"],
            fontName=FONT_B, fontSize=9, leading=12,
            textColor=BLACK, alignment=TA_LEFT),
        "body": ParagraphStyle("Body", parent=base["BodyText"],
            fontName=FONT, fontSize=9, leading=13.5,
            textColor=BLACK, leftIndent=5*mm, firstLineIndent=-4*mm,
            spaceAfter=1*mm),
        "body_b": ParagraphStyle("BodyB", parent=base["BodyText"],
            fontName=FONT_B, fontSize=9, leading=13.5,
            textColor=BLACK, leftIndent=5*mm, firstLineIndent=-4*mm,
            spaceAfter=1*mm),
        "lab_metric": ParagraphStyle("LabMetric", parent=base["Normal"],
            fontName=FONT_B, fontSize=9, leading=13,
            textColor=BLACK, leftIndent=5*mm, firstLineIndent=-4*mm,
            spaceBefore=1.2*mm, spaceAfter=0.5*mm),
        "lab_point": ParagraphStyle("LabPoint", parent=base["Normal"],
            fontName=FONT, fontSize=8.5, leading=12,
            textColor=DARK, leftIndent=9*mm, firstLineIndent=-3*mm,
            spaceAfter=0.5*mm),
        "note": ParagraphStyle("Note", parent=base["BodyText"],
            fontName=FONT, fontSize=8.5, leading=12.5,
            textColor=DARK),
        "note_lbl": ParagraphStyle("NoteLbl", parent=base["BodyText"],
            fontName=FONT_B, fontSize=8, leading=11,
            textColor=BLACK, spaceAfter=1*mm),
        "small": ParagraphStyle("Small", parent=base["Normal"],
            fontName=FONT, fontSize=7, leading=10, textColor=MUTED),
        "appr_title": ParagraphStyle("ApprTitle", parent=base["Normal"],
            fontName=FONT_B, fontSize=9.5, leading=13, textColor=BLACK),
    }


# ── Page chrome (Monochrome) ──────────────────────────────────────────────────
def _chrome(canvas, doc) -> None:
    canvas.saveState()

    # Header text
    canvas.setFont(FONT_B, 7.8)
    canvas.setFillColor(DARK)
    canvas.drawString(LM, PAGE_HEIGHT - 10*mm, "HỒ SƠ LÂM SÀNG — TÀI LIỆU BẢO MẬT")
    canvas.setFont(FONT, 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_WIDTH - RM, PAGE_HEIGHT - 10*mm, f"Trang {doc.page}")

    # Header line
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(LM, PAGE_HEIGHT - 13*mm, PAGE_WIDTH - RM, PAGE_HEIGHT - 13*mm)

    # Footer line
    canvas.line(LM, 13*mm, PAGE_WIDTH - RM, 13*mm)
    canvas.setFont(FONT_I, 6.8)
    canvas.setFillColor(MUTED)
    canvas.drawString(LM, 8*mm, "Bản tóm tắt điều trị được phê duyệt — chỉ phục vụ rà soát lâm sàng")
    canvas.restoreState()


# ── Layout helpers ────────────────────────────────────────────────────────────
def _info_grid(rows: list[list], styles: dict) -> Table:
    """2-column label/value grid for patient identity block."""
    col_w = [27*mm, CW/2 - 27*mm - 3*mm, 27*mm, CW/2 - 27*mm - 3*mm]
    t = Table(rows, colWidths=col_w, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE_ALT),
        ("BOX",        (0, 0), (-1, -1), 0.6, LINE_DARK),
        ("INNERGRID",  (0, 0), (-1, -1), 0.3, LINE_LIGHT),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",   (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3.5),
    ]))
    return t


def _sec_header(roman: str, title: str, styles: dict) -> Table:
    """Monochrome section header: dark badge with Roman numeral + light gray title box."""
    t = Table(
        [[Paragraph(roman, styles["sec_hdr_num"]),
          Paragraph(_safe(title), styles["sec_hdr_title"])]],
        colWidths=[10*mm, CW - 10*mm], hAlign="LEFT",
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), DARK),
        ("BACKGROUND", (1, 0), (1, 0), SURFACE),
        ("BOX",  (0, 0), (-1, -1), 0.6, LINE_DARK),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE_DARK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (0, 0), 2),
        ("RIGHTPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (1, 0), (1, 0), 7),
    ]))
    return t


def _notice_box(label: str, text: str, styles: dict) -> Table:
    """Monochrome notice/warning box with subtle gray fill and bold border."""
    lbl_style = styles["note_lbl"]
    t = Table(
        [[Paragraph(_safe(label), lbl_style)],
         [Paragraph(_safe(text), styles["note"])]],
        colWidths=[CW], hAlign="LEFT",
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), SURFACE_ALT),
        ("BOX",          (0, 0), (-1, -1), 0.6, LINE_DARK),
        ("LINEBEFORE",   (0, 0), (0, -1), 2.5, BLACK),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    return t


# ── Claim normalisation helpers ───────────────────────────────────────────────
_NOISE_PREFIXES = re.compile(
    r"^(thuốc(?:\s+hiện\s+tại)?:\s*|"
    r"chẩn\s+đoán/tình\s+trạng\s+bệnh:\s*|"
    r"xét\s+nghiệm:\s*|"
    r"diễn\s+tiến\s+)", re.IGNORECASE
)

_STATUS_SUFFIXES = re.compile(
    r"\s*(?::\s*trạng\s+thái:\s*đang\s+sử\s+dụng|"
    r":\s*đang\s+sử\s+dụng|\(đang\s+sử\s+dụng\))", re.IGNORECASE
)

_DATE_INLINE = re.compile(r"\s*ngày\s+\d{4}-\d{2}-\d{2}", re.IGNORECASE)
_FRAGMENT_ONLY = re.compile(r"^\d+(?:\.\d+)?\s*(?:mg|g|ml|mcg|ui|iu)?$", re.IGNORECASE)


def _strip_prefix(text: str) -> str:
    """Remove verbose boilerplate prefixes from claim text."""
    t = _NOISE_PREFIXES.sub("", text.strip())
    t = _STATUS_SUFFIXES.sub("", t)
    return t.strip()


def _is_fragment(text: str) -> bool:
    """True for bare dose fragments like '50 mg', '500 mg'."""
    return bool(_FRAGMENT_ONLY.match(text.strip()))


_LOINC_MAP = {
    "33914-3": "eGFR", "8480-6": "Huyết áp tâm thu",
    "8462-4": "Huyết áp tâm trương", "1742-6": "ALT",
    "13457-7": "LDL-C", "718-7": "Hemoglobin",
    "29463-7": "Cân nặng", "8867-4": "Nhịp tim",
    "4548-4": "HbA1c", "2339-0": "Đường huyết",
    "2160-0": "Creatinine",
    "glucose": "Đường huyết", "đường huyết": "Đường huyết",
    "hba1c": "HbA1c", "creatinine": "Creatinine",
    "egfr": "eGFR", "ldl-c": "LDL-C", "ldl": "LDL-C",
    "ldl cholesterol": "LDL-C", "alt": "ALT", "hemoglobin": "Hemoglobin",
    "huyết áp tâm thu": "Huyết áp tâm thu",
    "huyết áp tâm trương": "Huyết áp tâm trương",
    "nhịp tim": "Nhịp tim", "heart rate": "Nhịp tim",
    "cân nặng": "Cân nặng", "body weight": "Cân nặng",
}


def _trend_display_name(raw: str) -> str:
    """Map LOINC codes / generic names to Vietnamese display names."""
    key = raw.strip()
    return _LOINC_MAP.get(key, _LOINC_MAP.get(key.lower(), key))


def _dedup_key_med(text: str) -> str:
    t = text.lower()
    t = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", t)
    t = re.sub(r"thuốc(?:\s+hiện\s+tại)?:\s*", "", t)
    t = re.sub(r"(?:trạng thái|ghi nhận|đang sử dụng|active|stopped|discontinued).*", "", t)
    t = re.sub(r"\(.*?\)", "", t).strip()
    m = re.search(r"^([a-zàáâãèéêìíòóôõùúăđ\s]+?\d+(?:\.\d+)?\s*(?:mg|g|ml|mcg|ui|iu)?)",
                  t, re.UNICODE | re.IGNORECASE)
    return f"med:{m.group(1).strip()}" if m else f"med:{t[:35]}"


def _dedup_key_cond(text: str) -> str:
    t = text.lower()
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"chẩn đoán/tình trạng bệnh:\s*", "", t)
    t = re.sub(r"ghi nhận\s+\d{4}-\d{2}-\d{2}", "", t).strip()
    return f"cond:{t}"


def _fmt_med(raw: str) -> str | None:
    cleaned = _strip_prefix(raw)
    if _is_fragment(cleaned):
        return None
    cleaned = _DATE_INLINE.sub("", cleaned).strip()
    cleaned = _clean(cleaned)
    return cleaned if cleaned else None


# ── Section metadata & configuration ──────────────────────────────────────────

_ROMAN = ["I", "II", "III", "IV", "V", "VI"]

_SECTION_META: dict[str, tuple[str, str]] = {
    "active_conditions":  ("CHẨN ĐOÁN VÀ VẤN ĐỀ LÂM SÀNG",
                           "Các bệnh lý đang được theo dõi và điều trị"),
    "current_medications":("THUỐC VÀ PHÁC ĐỒ ĐIỀU TRỊ",
                           "Danh mục thuốc hiện tại được kê đơn"),
    "recent_results":     ("KẾT QUẢ CẬN LÂM SÀNG",
                           "Diễn tiến các chỉ số xét nghiệm theo ngày"),
    "changes_to_review":  ("ĐIỂM CẦN THEO DÕI VÀ XEM XÉT",
                           "Thay đổi hoặc mâu thuẫn dữ liệu cần bác sĩ xác nhận"),
    "data_gaps":          ("THÔNG TIN CẦN BỔ SUNG",
                           "Các trường dữ liệu còn thiếu hoặc cần cập nhật"),
}

_MANDATORY_SECTIONS = {"active_conditions", "current_medications", "recent_results"}

_SECTION_ORDER = [
    "active_conditions",
    "current_medications",
    "recent_results",
    "changes_to_review",
    "data_gaps",
]

_PRIORITY_METRICS = [
    "HbA1c", "Đường huyết", "Creatinine", "eGFR",
    "Huyết áp tâm thu", "Huyết áp tâm trương",
    "LDL-C", "ALT", "Hemoglobin", "Cân nặng", "Nhịp tim"
]


# ── Main PDF generator ────────────────────────────────────────────────────────

def generate_review_pdf(review: ReviewResponse, patient: PatientSummary | None = None) -> bytes:
    """Return a monochrome A4 PDF: standard Vietnamese clinical summary (Bản Tóm Tắt Bệnh Án)."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=LM, rightMargin=RM,
        topMargin=18*mm, bottomMargin=18*mm,
        title=f"Bản tóm tắt bệnh án — {review.patient_id}",
        author="Clinical Review Copilot",
        subject="Bản tóm tắt điều trị đã được bác sĩ phê duyệt",
    )
    S = _styles()
    story: list = []

    # ── I. Header & Identity Block ────────────────────────────────────────────
    story.append(Paragraph("BẢN TÓM TẮT BỆNH ÁN", S["doc_title"]))
    story.append(Paragraph(
        "Phiếu tổng hợp lâm sàng — đã được bác sĩ kiểm tra và phê duyệt", S["doc_sub"]))

    pname  = patient.pseudonym if patient else review.patient_id
    page   = f"{patient.age} tuổi" if patient and patient.age is not None else "—"
    sex_map = {"male": "Nam", "female": "Nữ", "other": "Khác"}
    psex   = sex_map.get(patient.sex, "—") if patient else "—"
    pcond  = _clean((patient.primary_condition if patient else None) or "—")
    cov_s  = _fmt_date(review.coverage.start_date)
    cov_e  = _fmt_date(review.coverage.end_date)
    appr_d = _fmt_date(review.approved_at or review.updated_at)
    lbl, val, val_b = S["lbl"], S["val"], S["val_b"]

    story.append(_info_grid([
        [Paragraph("HỌ VÀ TÊN", lbl),       Paragraph(_safe(pname), val_b),
         Paragraph("MÃ BỆNH NHÂN", lbl),     Paragraph(_safe(review.patient_id), val_b)],
        [Paragraph("NGÀY SINH / TUỔI", lbl), Paragraph(_safe(page), val),
         Paragraph("GIỚI TÍNH", lbl),        Paragraph(_safe(psex), val)],
        [Paragraph("CHẨN ĐOÁN CHÍNH", lbl),  Paragraph(_safe(pcond), val),
         Paragraph("TRẠNG THÁI HỒ SƠ", lbl), Paragraph("<b>ĐÃ PHÊ DUYỆT</b>", val_b)],
        [Paragraph("KHOẢNG DỮ LIỆU", lbl),
         Paragraph(f"{_safe(cov_s)} — {_safe(cov_e)}", val),
         Paragraph("NGÀY PHÊ DUYỆT", lbl),   Paragraph(_safe(appr_d), val)],
        [Paragraph("PHIÊN BẢN", lbl),
         Paragraph(f"v{review.version} &nbsp;|&nbsp; {_safe(review.review_version_id)}", val),
         Paragraph("SỐ LƯỢT KHÁM", lbl),
         Paragraph(str(review.coverage.encounter_count), val)],
    ], S))
    story.append(Spacer(1, 4*mm))

    # ── II–VI. Clinical sections ───────────────────────────────────────────────
    section_lookup: dict[str, list] = {}
    for sec in (review.sections or []):
        section_lookup.setdefault(sec.section_code, []).extend(sec.claims or [])
    clinician_notes: dict[str, str | None] = {
        sec.section_code: sec.clinician_text for sec in (review.sections or [])
    }

    sec_num = 0
    for sec_code in _SECTION_ORDER:
        raw_claims = section_lookup.get(sec_code, [])

        if sec_code == "recent_results":
            # ── CẬN LÂM SÀNG: Group by metric & list dates/values ───────────────
            grouped: dict[str, dict[str, str]] = {}
            for clm in raw_claims:
                raw = (clm.text or "").strip()
                raw_l = raw.lower()
                if "diễn tiến" in raw_l or "trend" in raw_l:
                    c_idx = raw.find(":")
                    if c_idx > 0:
                        m_raw = re.sub(r"^(?:diễn tiến|trend)\s+", "", raw[:c_idx], flags=re.IGNORECASE).strip()
                        m_name = _trend_display_name(m_raw)
                        rest = raw[c_idx+1:].strip()
                        parts = [p.strip().rstrip(".") for p in rest.split(";") if p.strip()]
                        for p in parts:
                            m = re.search(r"^(.*?)\s*\((\d{4}-\d{2}-\d{2})\)$", p)
                            if m:
                                val = _clean_lab_val(m.group(1))
                                date = m.group(2)
                                grouped.setdefault(m_name, {})[date] = val
                else:
                    m1 = re.match(r"^(?:xét nghiệm:\s*)?(.+?)\s+ngày\s+(\d{4}-\d{2}-\d{2})[:\s]+(?:kết quả[:\s]+)?(.+)$", raw, re.IGNORECASE)
                    if m1:
                        m_name = _trend_display_name(m1.group(1))
                        date = m1.group(2)
                        val = _clean_lab_val(m1.group(3))
                        grouped.setdefault(m_name, {})[date] = val
                    else:
                        m2 = re.match(r"^(?:xét nghiệm:\s*)?(.+?):\s*(.+?)\s*\((\d{4}-\d{2}-\d{2})\)$", raw, re.IGNORECASE)
                        if m2:
                            m_name = _trend_display_name(m2.group(1))
                            val = _clean_lab_val(m2.group(2))
                            date = m2.group(3)
                            grouped.setdefault(m_name, {})[date] = val

            if not grouped and sec_code not in _MANDATORY_SECTIONS:
                continue

            sec_num += 1
            roman = _ROMAN[sec_num - 1] if sec_num <= len(_ROMAN) else str(sec_num)
            title, subtitle = _SECTION_META.get(sec_code, (sec_code.upper(), ""))

            opening: list = [
                _sec_header(roman, title, S),
                Spacer(1, 1*mm),
            ]
            if subtitle:
                opening.append(Paragraph(_safe(subtitle), S["small"]))
                opening.append(Spacer(1, 1.5*mm))

            note_text = clinician_notes.get(sec_code) or ""
            if note_text.strip():
                opening.extend([
                    _notice_box("Ghi chú của bác sĩ", note_text.strip(), S),
                    Spacer(1, 2*mm),
                ])

            story.append(KeepTogether(opening))

            sorted_metrics = sorted(
                grouped.keys(),
                key=lambda k: (_PRIORITY_METRICS.index(k) if k in _PRIORITY_METRICS else 999, k)
            )

            if sorted_metrics:
                for m_name in sorted_metrics:
                    dates_map = grouped[m_name]
                    metric_flowables = [
                        Paragraph(f"• <b>{_safe(m_name)}:</b>", S["lab_metric"])
                    ]
                    for d in sorted(dates_map.keys()):
                        metric_flowables.append(
                            Paragraph(f"+ Ngày {_safe(d)} : Kết quả là {_safe(dates_map[d])}", S["lab_point"])
                        )
                    if len(dates_map) <= 8:
                        story.append(KeepTogether(metric_flowables))
                    else:
                        story.extend(metric_flowables)
            else:
                story.append(Paragraph("<i>Chưa ghi nhận thông tin trong mục này.</i>", S["note"]))

            story.append(Spacer(1, 3.5*mm))

        elif sec_code == "current_medications":
            # ── THUỐC ĐIỀU TRỊ: Deduplicate & show full doses ───────────────────
            priority: dict[str, tuple[str, str]] = {}
            for clm in raw_claims:
                raw = clm.text or ""
                fmt = _fmt_med(raw)
                if not fmt:
                    continue
                k = _dedup_key_med(fmt)
                has_dose = bool(re.search(r"\d+\s*(?:mg|g|ml|mcg)", fmt, re.IGNORECASE))
                is_old = bool(re.search(r"đã hoàn thành|completed|stopped|discontinued", raw, re.IGNORECASE))
                if k not in priority:
                    priority[k] = (fmt, clm.status)
                else:
                    existing, _ = priority[k]
                    existing_has_dose = bool(re.search(r"\d+\s*(?:mg|g|ml|mcg)", existing, re.IGNORECASE))
                    if has_dose and not existing_has_dose and not is_old:
                        priority[k] = (fmt, clm.status)

            bare_names: set[str] = set()
            for k, (fmt, _) in priority.items():
                m = re.match(r"^([a-zA-ZÀ-ỹ\s]+?)(?:\s+\d)", fmt, re.IGNORECASE)
                if m:
                    bare_names.add(m.group(1).strip().lower())

            med_list: list[tuple[str, str]] = []
            for k, (fmt, status) in priority.items():
                has_dose = bool(re.search(r"\d+\s*(?:mg|g|ml|mcg)", fmt, re.IGNORECASE))
                if not has_dose and fmt.strip().lower() in bare_names:
                    continue
                is_old = bool(re.search(r"đã hoàn thành|completed|stopped|discontinued|2025-|2024-", fmt, re.IGNORECASE))
                if is_old:
                    drug_m = re.match(r"^([a-zA-ZÀ-ỹ\s]+)", fmt)
                    if drug_m:
                        drug_base = drug_m.group(1).strip().lower()
                        if any(drug_base in f.lower() and "đã hoàn thành" not in f.lower() and "completed" not in f.lower() for f, _ in med_list):
                            continue
                med_list.append((fmt, status))

            if not med_list and sec_code not in _MANDATORY_SECTIONS:
                continue

            sec_num += 1
            roman = _ROMAN[sec_num - 1] if sec_num <= len(_ROMAN) else str(sec_num)
            title, subtitle = _SECTION_META.get(sec_code, (sec_code.upper(), ""))

            opening = [
                _sec_header(roman, title, S),
                Spacer(1, 1*mm),
            ]
            if subtitle:
                opening.append(Paragraph(_safe(subtitle), S["small"]))
                opening.append(Spacer(1, 1.5*mm))

            note_text = clinician_notes.get(sec_code) or ""
            if note_text.strip():
                opening.extend([
                    _notice_box("Ghi chú của bác sĩ", note_text.strip(), S),
                    Spacer(1, 2*mm),
                ])

            if med_list:
                first_text, first_status = med_list[0]
                tag = " <b>[Cần kiểm tra]</b>" if first_status != "verified" else ""
                opening.append(Paragraph(f"• {_safe(first_text)}{tag}", S["body"]))
                story.append(KeepTogether(opening))
                for c_text, c_status in med_list[1:]:
                    tg = " <b>[Cần kiểm tra]</b>" if c_status != "verified" else ""
                    story.append(Paragraph(f"• {_safe(c_text)}{tg}", S["body"]))
            else:
                opening.append(Paragraph("<i>Chưa ghi nhận thông tin trong mục này.</i>", S["note"]))
                story.append(KeepTogether(opening))

            story.append(Spacer(1, 3.5*mm))

        else:
            # ── CHẨN ĐOÁN & CÁC MỤC KHÁC ───────────────────────────────────────
            seen: set[str] = set()
            claim_items: list[tuple[str, str]] = []
            for clm in raw_claims:
                t = _clean(_strip_prefix(clm.text or ""))
                if not t:
                    continue
                k = _dedup_key_cond(t) if sec_code == "active_conditions" else t.lower().strip()
                if k not in seen:
                    seen.add(k)
                    claim_items.append((t, clm.status))

            if not claim_items and sec_code not in _MANDATORY_SECTIONS:
                continue

            sec_num += 1
            roman = _ROMAN[sec_num - 1] if sec_num <= len(_ROMAN) else str(sec_num)
            title, subtitle = _SECTION_META.get(sec_code, (sec_code.upper(), ""))

            opening = [
                _sec_header(roman, title, S),
                Spacer(1, 1*mm),
            ]
            if subtitle:
                opening.append(Paragraph(_safe(subtitle), S["small"]))
                opening.append(Spacer(1, 1.5*mm))

            note_text = clinician_notes.get(sec_code) or ""
            if note_text.strip():
                opening.extend([
                    _notice_box("Ghi chú của bác sĩ", note_text.strip(), S),
                    Spacer(1, 2*mm),
                ])

            if claim_items:
                first_text, first_status = claim_items[0]
                tag = " <b>[Cần kiểm tra]</b>" if first_status != "verified" else ""
                opening.append(Paragraph(f"• {_safe(first_text)}{tag}", S["body"]))
                story.append(KeepTogether(opening))
                for c_text, c_status in claim_items[1:]:
                    tg = " <b>[Cần kiểm tra]</b>" if c_status != "verified" else ""
                    story.append(Paragraph(f"• {_safe(c_text)}{tg}", S["body"]))
            else:
                opening.append(Paragraph("<i>Chưa ghi nhận thông tin trong mục này.</i>", S["note"]))
                story.append(KeepTogether(opening))

            story.append(Spacer(1, 3.5*mm))

    # ── Drug interactions / conflicts warning box ─────────────────────────────
    sev = {"low": "thấp", "moderate": "trung bình", "high": "cao", "unknown": "chưa xác định"}
    warns = [
        f"⚠ Tương tác thuốc ({sev.get(i.severity, i.severity)}): {i.description}"
        for i in review.drug_interactions
        if i.status not in {"not_applicable", "superseded"}
    ] + [
        f"⚠ Mâu thuẫn dữ liệu: {c.description}" +
        (" (đã xử lý)" if c.status == "resolved" else "")
        for c in review.conflicts
    ]
    if warns:
        warn_text = "<br/>".join(_safe(w) for w in warns)
        sec_num += 1
        roman = _ROMAN[sec_num - 1] if sec_num <= len(_ROMAN) else str(sec_num)
        story.append(KeepTogether([
            _sec_header(roman, "CẢNH BÁO LÂM SÀNG", S),
            Spacer(1, 1.5*mm),
            _notice_box("Cảnh báo và điểm cần lưu ý", warn_text, S),
            Spacer(1, 3.5*mm),
        ]))

    # ── Data quality flags ────────────────────────────────────────────────────
    quality = [i.message for i in review.data_quality_flags
               if i.status not in {"verified", "dismissed"}]
    if quality:
        q_text = "<br/>".join(f"• {_safe(q)}" for q in quality)
        story.extend([
            _notice_box("Thông tin cần kiểm tra thêm", q_text, S),
            Spacer(1, 3.5*mm),
        ])

    # ── Approval block ────────────────────────────────────────────────────────
    appr_time = _fmt_date(review.approved_at or review.updated_at, time=True)
    story.append(HRFlowable(width=CW, thickness=0.5, color=LINE))
    story.append(Spacer(1, 2.5*mm))
    appr_box = Table([
        [Paragraph("✓  ĐÃ PHÊ DUYỆT BỞI BÁC SĨ LÂM SÀNG", S["appr_title"])],
        [Paragraph(
            "Bác sĩ xác nhận đã kiểm tra nội dung tóm tắt và chịu trách nhiệm "
            "chuyên môn đối với mọi quyết định điều trị.",
            S["note"])],
        [Paragraph(
            f"Thời gian phê duyệt: <b>{_safe(appr_time)}</b> &nbsp;|&nbsp; "
            f"Mã phiên bản: {_safe(review.review_version_id)}",
            S["small"])],
    ], colWidths=[CW], hAlign="LEFT")
    appr_box.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), SURFACE_ALT),
        ("BOX",          (0, 0), (-1, -1), 0.7, LINE_DARK),
        ("LINEBEFORE",   (0, 0), (0, -1), 3, BLACK),
        ("LEFTPADDING",  (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    story.append(KeepTogether([appr_box]))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        _safe(review.disclaimer or
              "Tài liệu phục vụ theo dõi và điều trị lâm sàng. "
              "Bác sĩ chịu trách nhiệm cho mọi quyết định chuyên môn."),
        S["small"]))

    doc.build(story, onFirstPage=_chrome, onLaterPages=_chrome)
    pdf_content = buf.getvalue()
    buf.close()
    return pdf_content
