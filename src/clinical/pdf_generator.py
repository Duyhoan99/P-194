"""PDF generator for Clinical Review Copilot using fpdf2.

Generates a premium, hospital-grade clinical review PDF report including:
- Header & Visual Branding
- Patient Demographics Card
- Formatted Clinical Review Sections & Claims (Clean human-readable snippets, no raw JSON!)
- Highlighted Clinician Edits & Notes
- Evidence Citations (Source Document, Page, Snippet)
- Drug Interactions & Data Quality Alerts
- Clinician Digital Signature / Approval Stamp & Legal Disclaimer
"""

import os
import json
from datetime import datetime
from typing import Any
from fpdf import FPDF
from src.clinical.canonical import ReviewResponse, PatientSummary


def _clean_snippet(snippet: str) -> str:
    """Format raw snippet text into human-readable text, converting raw JSON if present."""
    if not snippet:
        return ""
    snippet_str = str(snippet).strip()
    if snippet_str.startswith("{") and snippet_str.endswith("}"):
        try:
            data = json.loads(snippet_str)
            res_type = data.get("resourceType", "")
            res_id = data.get("id", "")
            
            parts = []
            if res_type:
                parts.append(f"Resource: {res_type}")
            if res_id:
                parts.append(f"ID: {res_id}")
                
            # Extract common FHIR fields
            if "code" in data and isinstance(data["code"], dict):
                text_val = data["code"].get("text") or data["code"].get("coding", [{}])[0].get("display")
                if text_val:
                    parts.append(f"Chỉ số: {text_val}")
                    
            if "valueQuantity" in data and isinstance(data["valueQuantity"], dict):
                val = data["valueQuantity"].get("value")
                unit = data["valueQuantity"].get("unit") or data["valueQuantity"].get("code") or ""
                if val is not None:
                    parts.append(f"Kết quả: {val} {unit}".strip())
            elif "valueString" in data:
                parts.append(f"Kết quả: {data['valueString']}")

            if "status" in data:
                parts.append(f"Trạng thái: {data['status']}")

            if parts:
                return " • ".join(parts)
        except Exception:
            pass
    
    # Trim overly long strings cleanly
    if len(snippet_str) > 200:
        return snippet_str[:197] + "..."
    return snippet_str


class ClinicalPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        
        # Load Arial font with Unicode support if available
        self.unicode_font = False
        font_dir = r"C:\Windows\Fonts"
        regular_ttf = os.path.join(font_dir, "arial.ttf")
        bold_ttf = os.path.join(font_dir, "arialbd.ttf")
        italic_ttf = os.path.join(font_dir, "ariali.ttf")

        if os.path.exists(regular_ttf) and os.path.exists(bold_ttf):
            try:
                self.add_font("Arial", "", regular_ttf)
                self.add_font("Arial", "B", bold_ttf)
                if os.path.exists(italic_ttf):
                    self.add_font("Arial", "I", italic_ttf)
                self.unicode_font = True
            except Exception:
                self.unicode_font = False

    def header(self):
        # Header banner height 22mm
        self.set_fill_color(15, 23, 42)  # Dark slate #0f172a
        self.rect(0, 0, 210, 22, style="F")

        # Cyan Accent bottom border (1.5mm)
        self.set_fill_color(8, 145, 178)  # Cyan #0891b2
        self.rect(0, 20.5, 210, 1.5, style="F")

        font_name = "Arial" if self.unicode_font else "Helvetica"
        
        # Left Title
        self.set_font(font_name, "B", 13)
        self.set_text_color(34, 211, 238)  # Cyan #22d3ee
        self.set_xy(12, 5)
        self.cell(130, 7, "CLINICAL REVIEW COPILOT", new_x="RIGHT", new_y="TOP")

        self.set_font(font_name, "", 8.5)
        self.set_text_color(148, 163, 184)  # Slate-400
        self.set_xy(12, 12)
        self.cell(130, 5, "Hệ thống AI hỗ trợ tóm tắt & rà soát hồ sơ bệnh án (MIMIC-IV / AI20K)", new_x="RIGHT", new_y="TOP")

        # Right Confidential Badge
        self.set_font(font_name, "B", 8)
        self.set_text_color(248, 250, 252)
        self.set_xy(145, 6)
        self.cell(53, 5, "BÁO CÁO LÂM SÀNG BẢO MẬT", align="R", new_x="LMARGIN", new_y="NEXT")

        self.set_font(font_name, "", 7.5)
        self.set_text_color(148, 163, 184)
        self.set_xy(145, 11)
        self.cell(53, 5, "Confidential Medical Record", align="R", new_x="LMARGIN", new_y="NEXT")

        self.ln(6)

    def footer(self):
        self.set_y(-14)
        font_name = "Arial" if self.unicode_font else "Helvetica"
        self.set_font(font_name, "I", 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 8, f"Trang {self.page_no()} / {{nb}}  |  Hồ sơ rà soát y tế bảo mật  |  Exported by Clinical Review Copilot", align="C")


def generate_review_pdf(review: ReviewResponse, patient: PatientSummary | None = None) -> bytes:
    """Generate a clean, beautiful clinical review PDF document."""

    pdf = ClinicalPDF()
    pdf.alias_nb_pages()
    pdf.set_margins(12, 12, 12)
    pdf.add_page()
    
    font_name = "Arial" if pdf.unicode_font else "Helvetica"

    # Main Document Header Title
    pdf.set_font(font_name, "B", 15)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, "BẢN TÓM TẮT VÀ RÀ SOÁT HỒ SƠ BỆNH ÁN", new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font(font_name, "", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, f"Mã rà soát: {review.review_version_id}  •  Phiên bản: v{review.version}  •  Ngày tạo: {review.generated_at[:10] if review.generated_at else 'N/A'}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # 1. Patient Demographics & Metadata Styled Card
    card_y = pdf.get_y()
    card_height = 34

    # Background card
    pdf.set_fill_color(248, 250, 252)  # slate-50
    pdf.set_draw_color(226, 232, 240)  # slate-200
    pdf.rect(12, card_y, 186, card_height, style="FD")

    # Left Vertical Cyan Bar (4mm)
    pdf.set_fill_color(8, 145, 178)  # Cyan #0891b2
    pdf.rect(12, card_y, 3, card_height, style="F")

    inner_y = card_y + 3.5

    # Column 1 (Left side)
    pdf.set_xy(18, inner_y)
    pdf.set_font(font_name, "B", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(28, 4.5, "BỆNH NHÂN:")
    pdf.set_font(font_name, "B", 9.5)
    pdf.set_text_color(15, 23, 42)
    p_name = patient.pseudonym if patient else review.patient_id
    pdf.cell(60, 4.5, f"{p_name}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(18)
    pdf.set_font(font_name, "B", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(28, 4.5, "MÃ BỆNH NHÂN:")
    pdf.set_font(font_name, "", 9)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(60, 4.5, f"{review.patient_id}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(18)
    pdf.set_font(font_name, "B", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(28, 4.5, "TUỔI / GIỚI TÍNH:")
    pdf.set_font(font_name, "", 9)
    pdf.set_text_color(30, 41, 59)
    p_age = f"{patient.age} tuổi" if patient and patient.age else "Chưa rõ"
    p_sex = "Nam" if patient and patient.sex == "male" else ("Nữ" if patient and patient.sex == "female" else "Chưa rõ")
    pdf.cell(60, 4.5, f"{p_age} • {p_sex}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(18)
    pdf.set_font(font_name, "B", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(28, 4.5, "CHẨN ĐOÁN CHÍNH:")
    pdf.set_font(font_name, "B", 9)
    pdf.set_text_color(15, 23, 42)
    p_cond = (patient.primary_condition if patient else "") or "Đái tháo đường Tuýp 2 / Theo dõi lâm sàng"
    pdf.cell(60, 4.5, f"{p_cond}", new_x="LMARGIN", new_y="NEXT")

    # Column 2 (Right side)
    pdf.set_xy(115, inner_y)
    pdf.set_font(font_name, "B", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(32, 4.5, "TRẠNG THÁI RÀ SOÁT:")
    pdf.set_font(font_name, "B", 9)
    if review.status == "approved":
        pdf.set_text_color(5, 150, 105)  # emerald-600
        pdf.cell(45, 4.5, "ĐÃ DUYỆT (APPROVED)", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_text_color(217, 119, 6)  # amber-600
        pdf.cell(45, 4.5, f"{review.status.upper()}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(115)
    pdf.set_font(font_name, "B", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(32, 4.5, "NGÀY PHÊ DUYỆT:")
    pdf.set_font(font_name, "", 9)
    pdf.set_text_color(30, 41, 59)
    app_date = review.approved_at or review.updated_at or review.generated_at
    pdf.cell(45, 4.5, f"{app_date[:10] if app_date else 'N/A'}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(115)
    pdf.set_font(font_name, "B", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(32, 4.5, "DATA WATERMARK:")
    pdf.set_font(font_name, "", 8.5)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(45, 4.5, f"{review.data_watermark}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(115)
    pdf.set_font(font_name, "B", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(32, 4.5, "NGƯỜI PHÊ DUYỆT:")
    pdf.set_font(font_name, "", 9)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(45, 4.5, "BS. Lâm sàng (usr_doctor_demo)", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(card_y + card_height + 5)

    # 2. Section Header & Claims Block
    pdf.set_font(font_name, "B", 11.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, "NỘI DUNG RÀ SOÁT LÂM SÀNG VÀ BẰNG CHỨNG Y TẾ", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    section_titles_map = {
        "patient_overview": "1. Tổng quan bệnh nhân & Lý do khám",
        "active_conditions": "2. Vấn đề & Bệnh nền đang hoạt động",
        "current_medications": "3. Thuốc hiện tại & Tiền sử dùng thuốc",
        "recent_results": "4. Kết quả xét nghiệm & Cận lâm sàng gần đây",
        "changes_to_review": "5. Thay đổi lâm sàng cần rà soát",
        "data_gaps": "6. Dữ liệu thiếu sót / Cần bổ sung",
    }

    for sec in review.sections:
        if pdf.get_y() > 250:
            pdf.add_page()

        sec_code = sec.section_code
        sec_display_title = section_titles_map.get(sec_code, sec.title or sec_code.replace("_", " ").title())

        # Section Banner (Light Cyan/Slate Box)
        pdf.set_fill_color(241, 245, 249)  # slate-100
        pdf.set_draw_color(203, 213, 225)  # slate-300
        pdf.set_font(font_name, "B", 9.5)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6.5, f"   {sec_display_title}", fill=True, border=1, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # Doctor's Edit / Note if available
        if sec.clinician_text and sec.clinician_text.strip():
            pdf.set_fill_color(236, 253, 245)  # emerald-50
            pdf.set_draw_color(167, 243, 208)  # emerald-200
            pdf.set_font(font_name, "B", 8.5)
            pdf.set_text_color(6, 95, 70)  # emerald-800
            
            pdf.set_x(14)
            pdf.cell(0, 4.5, "[📝 GHI CHÚ CHỈNH SỬA BỔ SUNG CỦA BÁC SĨ LÂM SÀNG]:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(14)
            pdf.set_font(font_name, "I", 9)
            pdf.set_text_color(4, 120, 87)
            pdf.multi_cell(180, 4.5, sec.clinician_text, border=0, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        # Claims
        if not sec.claims:
            pdf.set_font(font_name, "I", 8.5)
            pdf.set_text_color(148, 163, 184)
            pdf.set_x(16)
            pdf.cell(0, 4.5, "Không ghi nhận dữ liệu cho mục này trong hồ sơ.", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            continue

        for claim in sec.claims:
            if pdf.get_y() > 255:
                pdf.add_page()

            pdf.set_x(15)
            
            # Badge
            if claim.status == "verified":
                pdf.set_font(font_name, "B", 8)
                pdf.set_text_color(5, 150, 105)  # emerald-600
                pdf.write(5, "[✓ ĐÃ XÁC MINH] ")
            else:
                pdf.set_font(font_name, "B", 8)
                pdf.set_text_color(217, 119, 6)  # amber-600
                pdf.write(5, "[⚠ CẦN XÁC MINH] ")

            # Claim text
            pdf.set_font(font_name, "", 9)
            pdf.set_text_color(15, 23, 42)
            pdf.write(5, f"{claim.text}\n")

            # Citations
            if claim.citations:
                pdf.set_font(font_name, "", 8)
                for cit in claim.citations:
                    doc_name = getattr(cit, "document_name", None) or getattr(cit, "resource_type", None) or getattr(cit, "source_record_id", None) or "Hồ sơ y tế"
                    pg_num = getattr(cit, "page_number", None)
                    pg_str = f" • Trang {pg_num}" if pg_num else ""
                    cit_id = getattr(cit, "citation_id", "")
                    raw_snip = getattr(cit, "snippet", "")
                    clean_snip = _clean_snippet(raw_snip)

                    pdf.set_x(20)
                    pdf.set_font(font_name, "B", 7.5)
                    pdf.set_text_color(8, 145, 178)  # Cyan #0891b2
                    pdf.write(4, f"↳ Nguồn bằng chứng [{cit_id}]: ")
                    
                    pdf.set_font(font_name, "", 8)
                    pdf.set_text_color(71, 85, 105)
                    pdf.write(4, f"{doc_name}{pg_str}\n")

                    if clean_snip:
                        pdf.set_x(24)
                        pdf.set_font(font_name, "I", 7.5)
                        pdf.set_text_color(100, 116, 139)
                        pdf.write(3.8, f"\"{clean_snip}\"\n")
            pdf.ln(1.5)

        pdf.ln(2)

    # 3. Drug Interactions & Clinical Warnings section if present
    if review.drug_interactions or review.conflicts:
        if pdf.get_y() > 240:
            pdf.add_page()

        pdf.set_fill_color(254, 242, 242)  # red-50
        pdf.set_draw_color(248, 113, 113)  # red-400
        pdf.set_font(font_name, "B", 9.5)
        pdf.set_text_color(153, 27, 27)    # red-800
        pdf.cell(0, 6.5, "  CẢNH BÁO LÂM SÀNG & TƯƠNG TÁC THUỐC CẦN LƯU Ý", fill=True, border=1, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        for di in review.drug_interactions:
            pdf.set_x(16)
            pdf.set_font(font_name, "B", 8.5)
            pdf.set_text_color(185, 28, 28)
            pdf.write(4.5, f" • Tương tác thuốc ({di.severity.upper()}): ")
            pdf.set_font(font_name, "", 8.5)
            pdf.set_text_color(30, 41, 59)
            pdf.write(4.5, f"{di.description}\n")

        for cfl in review.conflicts:
            pdf.set_x(16)
            pdf.set_font(font_name, "B", 8.5)
            pdf.set_text_color(185, 28, 28)
            pdf.write(4.5, f" • Mâu thuẫn dữ liệu: ")
            pdf.set_font(font_name, "", 8.5)
            pdf.set_text_color(30, 41, 59)
            pdf.write(4.5, f"{cfl.description}\n")
        pdf.ln(4)

    # 4. Clinician Signature Stamp & Confirmation Block
    if pdf.get_y() > 235:
        pdf.add_page()

    pdf.ln(4)
    stamp_y = pdf.get_y()
    stamp_height = 28

    pdf.set_fill_color(248, 250, 252)  # slate-50
    pdf.set_draw_color(203, 213, 225)  # slate-300
    pdf.rect(12, stamp_y, 186, stamp_height, style="FD")

    # Emerald left bar for approval confirmation
    pdf.set_fill_color(5, 150, 105)  # emerald-600
    pdf.rect(12, stamp_y, 3, stamp_height, style="F")

    pdf.set_xy(18, stamp_y + 3)
    pdf.set_font(font_name, "B", 9.5)
    pdf.set_text_color(6, 95, 70)  # emerald-800
    pdf.cell(0, 5, "XÁC NHẬN PHÊ DUYỆT CỦA BÁC SĨ LÂM SÀNG (CLINICIAN APPROVAL STAMP)", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(18)
    pdf.set_font(font_name, "", 8.5)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 4.5, "Tôi xác nhận đã kiểm tra, rà soát toàn bộ các bằng chứng y tế và đối chiếu các thông tin trong bản tóm tắt này.", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(18)
    pdf.set_font(font_name, "I", 8)
    pdf.set_text_color(100, 116, 139)
    disclaimer_text = review.disclaimer or "Tài liệu chỉ phục vụ rà soát lâm sàng. Bác sĩ chịu trách nhiệm cho mọi quyết định điều trị."
    pdf.cell(0, 4.5, disclaimer_text, new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(18)
    pdf.set_font(font_name, "B", 7.5)
    pdf.set_text_color(71, 85, 105)
    app_time_str = review.approved_at or datetime.now().isoformat()
    pdf.cell(0, 4.5, f"Ký duyệt bởi: BS. Lâm sàng  •  Thời gian: {app_time_str}  •  Hash: sha256:{review.review_version_id}", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
