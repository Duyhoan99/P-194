"""Generate a monochrome, print-ready Vietnamese patient care-plan PDF."""

from __future__ import annotations

import html
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.clinical.canonical import PatientSummary
from src.clinical.care_plan_agent import CarePlanDataSummary, CarePlanDraft
from src.clinical.pdf_generator import FONT_BOLD, FONT_ITALIC, FONT_REGULAR

BLACK = colors.black
DARK = colors.Color(0.14, 0.14, 0.14)
MID = colors.Color(0.36, 0.36, 0.36)
LINE = colors.Color(0.72, 0.72, 0.72)
LIGHT_LINE = colors.Color(0.86, 0.86, 0.86)
SURFACE = colors.Color(0.96, 0.96, 0.96)
WHITE = colors.white

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 16 * mm
RIGHT_MARGIN = 16 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN


def _safe(value: object | None) -> str:
    text = str(value or "").strip()
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    return html.escape(text, quote=False).replace("\n", "<br/>")


def _date(value: str | None) -> str:
    if not value:
        return "Chưa ghi nhận"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return value


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "clinic": ParagraphStyle(
            "CareClinic",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=12,
            textColor=DARK,
        ),
        "meta": ParagraphStyle(
            "CareMeta",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=8,
            leading=11,
            textColor=MID,
        ),
        "title": ParagraphStyle(
            "CareTitle",
            parent=base["Title"],
            fontName=FONT_BOLD,
            fontSize=17,
            leading=21,
            alignment=TA_CENTER,
            textColor=BLACK,
            spaceAfter=2 * mm,
        ),
        "status": ParagraphStyle(
            "CareStatus",
            parent=base["Normal"],
            fontName=FONT_ITALIC,
            fontSize=8.3,
            leading=11,
            alignment=TA_CENTER,
            textColor=MID,
        ),
        "label": ParagraphStyle(
            "CareLabel",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=8,
            leading=11,
            textColor=MID,
        ),
        "value": ParagraphStyle(
            "CareValue",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=12.5,
            textColor=DARK,
        ),
        "value_bold": ParagraphStyle(
            "CareValueBold",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=12.5,
            textColor=BLACK,
        ),
        "section": ParagraphStyle(
            "CareSection",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=10.5,
            leading=14,
            textColor=BLACK,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "CareBody",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=9.2,
            leading=13.5,
            textColor=DARK,
            alignment=TA_LEFT,
        ),
        "body_bold": ParagraphStyle(
            "CareBodyBold",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=9.2,
            leading=13.5,
            textColor=BLACK,
        ),
        "signature_title": ParagraphStyle(
            "CareSignatureTitle",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=9.2,
            leading=13.5,
            textColor=BLACK,
            alignment=TA_CENTER,
        ),
        "signature_name": ParagraphStyle(
            "CareSignatureName",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=9.2,
            leading=13.5,
            textColor=BLACK,
            alignment=TA_CENTER,
        ),
        "signature_line": ParagraphStyle(
            "CareSignatureLine",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=12.5,
            textColor=DARK,
            alignment=TA_CENTER,
        ),
        "small": ParagraphStyle(
            "CareSmall",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=7.5,
            leading=10,
            textColor=MID,
        ),
    }


def _paragraph(value: object | None, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_safe(value) or "Chưa có nội dung.", style)


def _final_medication_instruction(value: str) -> str:
    """Do not leak clinician-facing placeholders into the patient handout."""
    text = str(value or "").strip()
    lowered = text.casefold()
    internal_markers = (
        "bác sĩ bổ sung",
        "chưa đề xuất",
        "chờ bác sĩ",
        "agent đề xuất",
        "chưa đủ điều kiện",
    )
    if not text or any(marker in lowered for marker in internal_markers):
        return "........................................................................................"
    return text


def _qr_drawing(value: str, size: float = 23 * mm) -> Drawing:
    """Create a standards-compliant vector QR with a clear quiet zone."""
    qr = QrCodeWidget(value=value, barLevel="M")
    x0, y0, x1, y1 = qr.getBounds()
    width, height = x1 - x0, y1 - y0
    scale = size / max(width, height)
    drawing = Drawing(
        size,
        size,
        transform=[scale, 0, 0, scale, -x0 * scale, -y0 * scale],
    )
    drawing.add(qr)
    return drawing


def _section_box(
    number: int,
    title: str,
    content: list[object],
    styles: dict[str, ParagraphStyle],
) -> list[object]:
    heading = Table(
        [[Paragraph(f"{number}. {html.escape(title)}", styles["section"])]],
        colWidths=[CONTENT_WIDTH - 10 * mm],
    )
    heading.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
                ("LINEBELOW", (0, 0), (-1, -1), 0.8, BLACK),
            ]
        )
    )
    # Keep only the heading together. The body is allowed to flow naturally
    # across pages so a long evidence block never leaves most of a page empty.
    return [KeepTogether([heading, Spacer(1, 1.5 * mm)]), *content, Spacer(1, 1.5 * mm)]


def _page_footer(canvas, doc) -> None:
    canvas.saveState()
    if doc.page > 1:
        canvas.setFont(FONT_BOLD, 7.5)
        canvas.setFillColor(DARK)
        canvas.drawString(LEFT_MARGIN, PAGE_HEIGHT - 8 * mm, "PHIẾU HƯỚNG DẪN ĐIỀU TRỊ VÀ CHĂM SÓC TẠI NHÀ")
        patient_id = str(doc.title).rsplit(" - ", 1)[-1]
        canvas.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 8 * mm, f"Mã bệnh nhân: {patient_id}")
        canvas.setStrokeColor(LIGHT_LINE)
        canvas.setLineWidth(0.5)
        canvas.line(LEFT_MARGIN, PAGE_HEIGHT - 10.5 * mm, PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 10.5 * mm)
    canvas.setStrokeColor(LIGHT_LINE)
    canvas.setLineWidth(0.5)
    canvas.line(LEFT_MARGIN, 10 * mm, PAGE_WIDTH - RIGHT_MARGIN, 10 * mm)
    canvas.setFont(FONT_REGULAR, 7.5)
    canvas.setFillColor(MID)
    canvas.drawString(LEFT_MARGIN, 6.5 * mm, "Tài liệu hỗ trợ chăm sóc - không thay thế chỉ định chuyên môn của bác sĩ.")
    canvas.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, 6.5 * mm, f"Trang {doc.page}")
    canvas.restoreState()


def build_care_plan_pdf(
    *,
    patient: PatientSummary,
    plan: CarePlanDraft,
    data_summary: CarePlanDataSummary,
    doctor_sign_name: str,
    share_url: str | None = None,
    generated_at: datetime | None = None,
) -> bytes:
    """Return an A4 PDF containing only the clinician-facing care guidance."""
    styles = _styles()
    created = generated_at or datetime.now()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=10 * mm,
        bottomMargin=13 * mm,
        title=f"Hướng dẫn điều trị - {patient.patient_id}",
        author="Hệ thống hỗ trợ lâm sàng P-194",
        subject="Phiếu hướng dẫn điều trị và chăm sóc tại nhà",
    )

    gender = {"female": "Nữ", "male": "Nam", "other": "Khác", "unknown": "Chưa rõ"}.get(
        patient.sex,
        "Chưa rõ",
    )
    diagnoses = "; ".join(data_summary.conditions) or patient.primary_condition or "Chưa ghi nhận"
    signature_name = doctor_sign_name.strip()
    if not signature_name or signature_name.casefold() in {"chưa ký duyệt", "chưa xác nhận"}:
        signature_name = "........................................"

    story: list[object] = []
    clinic_left = [
        Paragraph("HỆ THỐNG HỖ TRỢ LÂM SÀNG P-194", styles["clinic"]),
        Paragraph("PHÒNG KHÁM ĐA KHOA KỸ THUẬT CAO P-194", styles["clinic"]),
    ]
    clinic_right = [
        Paragraph(f"<b>Mã bệnh nhân:</b> {_safe(patient.patient_id)}", styles["meta"]),
        Paragraph(f"Ngày xuất: {created.strftime('%d/%m/%Y')}", styles["meta"]),
    ]
    header = Table([[clinic_left, clinic_right]], colWidths=[CONTENT_WIDTH * 0.68, CONTENT_WIDTH * 0.32])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
                ("LINEBELOW", (0, 0), (-1, -1), 1, BLACK),
            ]
        )
    )
    story.extend(
        [
            header,
            Spacer(1, 3 * mm),
            Paragraph("PHIẾU HƯỚNG DẪN ĐIỀU TRỊ VÀ CHĂM SÓC TẠI NHÀ", styles["title"]),
            Paragraph(
                "BẢN HƯỚNG DẪN ĐÃ ĐƯỢC BÁC SĨ KIỂM TRA VÀ KÝ DUYỆT"
                if share_url
                else "BẢN NHÁP - CẦN BÁC SĨ KIỂM TRA VÀ KÝ DUYỆT TRƯỚC KHI PHÁT HÀNH",
                styles["status"],
            ),
            Spacer(1, 3 * mm),
        ]
    )

    patient_rows = [
        [
            Paragraph("HỌ VÀ TÊN", styles["label"]),
            _paragraph(patient.pseudonym, styles["value_bold"]),
            Paragraph("TUỔI / GIỚI", styles["label"]),
            _paragraph(f"{patient.age or 'Chưa rõ'} tuổi / {gender}", styles["value"]),
        ],
        [
            Paragraph("LẦN KHÁM GẦN NHẤT", styles["label"]),
            _paragraph(_date(patient.last_encounter_at), styles["value"]),
            Paragraph("CHẨN ĐOÁN", styles["label"]),
            _paragraph(diagnoses, styles["value_bold"]),
        ],
    ]
    patient_table = Table(
        patient_rows,
        colWidths=[29 * mm, 52 * mm, 32 * mm, CONTENT_WIDTH - 113 * mm],
    )
    patient_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LIGHT_LINE),
                ("BACKGROUND", (0, 0), (0, -1), SURFACE),
                ("BACKGROUND", (2, 0), (2, -1), SURFACE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ]
        )
    )
    story.extend([patient_table, Spacer(1, 3 * mm)])

    greeting = Table(
        [
            [Paragraph("LỜI DẶN CỦA BÁC SĨ", styles["body_bold"])],
            [_paragraph(plan.doctor_greeting, styles["body"])],
        ],
        colWidths=[CONTENT_WIDTH],
    )
    greeting.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ]
        )
    )
    story.extend([KeepTogether([greeting]), Spacer(1, 3 * mm)])

    medication_rows = [
        [
            Paragraph("LẦN DÙNG 1 / BUỔI SÁNG", styles["label"]),
            _paragraph(_final_medication_instruction(plan.morning_meds), styles["value"]),
        ],
        [
            Paragraph("LẦN DÙNG 2 / BUỔI TỐI", styles["label"]),
            _paragraph(_final_medication_instruction(plan.evening_meds), styles["value"]),
        ],
    ]
    medication_table = Table(medication_rows, colWidths=[46 * mm, CONTENT_WIDTH - 56 * mm])
    medication_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LIGHT_LINE),
                ("BACKGROUND", (0, 0), (0, -1), SURFACE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ]
        )
    )
    story.extend(
        _section_box(
            1,
            "THUỐC VÀ CÁCH DÙNG",
            [
                medication_table,
                Spacer(1, 1.5 * mm),
                Paragraph(
                    "Chỉ dùng thuốc theo đơn bác sĩ đã chốt; không tự bỏ thuốc, đổi liều hoặc uống dồn liều.",
                    styles["small"],
                ),
            ],
            styles,
        )
    )

    diet_rows = [
        [Paragraph("NÊN ĂN VÀ UỐNG ĐỦ", styles["label"]), _paragraph(plan.diet_good, styles["value"])],
        [Paragraph("CẦN KIÊNG VÀ HẠN CHẾ", styles["label"]), _paragraph(plan.diet_bad, styles["value"])],
    ]
    diet_table = Table(diet_rows, colWidths=[46 * mm, CONTENT_WIDTH - 56 * mm])
    diet_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LIGHT_LINE),
                ("BACKGROUND", (0, 0), (0, -1), SURFACE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ]
        )
    )
    story.extend(
        _section_box(
            2,
            "CHẾ ĐỘ ĂN UỐNG VÀ KIÊNG CỮ",
            [diet_table],
            styles,
        )
    )
    story.extend(
        _section_box(
            3,
            "VẬN ĐỘNG VÀ THÓI QUEN SỐNG",
            [
                _paragraph(plan.exercise, styles["body"]),
            ],
            styles,
        )
    )

    emergency_content: list[object] = [_paragraph(plan.emergency_warning, styles["body"]), Spacer(1, 2 * mm)]
    emergency_content.append(
        Table(
            [
                [Paragraph("TÁI KHÁM", styles["label"]), _paragraph(plan.follow_up, styles["value_bold"])],
            ],
            colWidths=[46 * mm, CONTENT_WIDTH - 56 * mm],
            style=TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, LIGHT_LINE),
                    ("BACKGROUND", (0, 0), (0, -1), SURFACE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ]
            ),
        )
    )
    story.extend(_section_box(4, "CẢNH BÁO VÀ XỬ TRÍ CẤP CỨU", emergency_content, styles))

    if share_url:
        qr_cell = Table(
            [
                [_qr_drawing(share_url, 19 * mm)],
                [Paragraph("<b>QUÉT ĐỂ NGHE LỜI DẶN</b><br/>Camera / Zalo", styles["small"])],
            ],
            colWidths=[39 * mm],
        )
        qr_cell.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        sign_width = (CONTENT_WIDTH - 43 * mm) / 2
        signature = Table(
            [
                [
                    qr_cell,
                    Paragraph("NGƯỜI BỆNH / NGƯỜI NHÀ", styles["signature_title"]),
                    Paragraph("BÁC SĨ ĐIỀU TRỊ", styles["signature_title"]),
                ],
                [
                    "",
                    Paragraph("<br/>(Ký và ghi rõ họ tên)", styles["status"]),
                    Paragraph("<br/>(Ký và ghi rõ họ tên)", styles["status"]),
                ],
                [
                    "",
                    Paragraph("........................................", styles["signature_line"]),
                    Paragraph(_safe(signature_name), styles["signature_name"]),
                ],
            ],
            colWidths=[43 * mm, sign_width, sign_width],
        )
        signature_style = [
            ("SPAN", (0, 0), (0, 2)),
            ("BOX", (0, 0), (0, 2), 0.8, BLACK),
            ("LEFTPADDING", (0, 0), (0, 2), 2 * mm),
            ("RIGHTPADDING", (0, 0), (0, 2), 2 * mm),
        ]
    else:
        signature = Table(
            [
                [
                    Paragraph("NGƯỜI BỆNH / NGƯỜI NHÀ", styles["signature_title"]),
                    Paragraph("BÁC SĨ ĐIỀU TRỊ", styles["signature_title"]),
                ],
                [Paragraph("<br/><br/>(Ký và ghi rõ họ tên)", styles["status"]), Paragraph("<br/><br/>(Ký và ghi rõ họ tên)", styles["status"])],
                [
                    Paragraph("........................................", styles["signature_line"]),
                    Paragraph(_safe(signature_name), styles["signature_name"]),
                ],
            ],
            colWidths=[CONTENT_WIDTH / 2, CONTENT_WIDTH / 2],
        )
        signature_style = []
    signature.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEABOVE", (0, 0), (-1, 0), 0.8, BLACK),
                ("TOPPADDING", (0, 0), (-1, 0), 2 * mm),
                *signature_style,
            ]
        )
    )
    story.extend([Spacer(1, 2 * mm), KeepTogether([signature])])

    document.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    pdf_content = buffer.getvalue()
    buffer.close()
    return pdf_content
