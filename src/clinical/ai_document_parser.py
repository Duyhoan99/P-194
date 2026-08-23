"""AI Document Clinical Parser.

Uses LLM runtime (OpenAI or Gemini) or regex deterministic fallback to parse
extracted markdown documents into structured clinical entities (Patient ID, dates,
LOINC observation codes, conditions, and medications).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from src.agents.llm_client import get_llm_runtime

logger = logging.getLogger(__name__)

# Standard LOINC codes for common clinical metrics
LOINC_MAP: dict[str, tuple[str, str, str]] = {
    # canonical_key: (code, display_name, canonical_unit)
    "hba1c": ("4548-4", "HbA1c", "%"),
    "glucose": ("2339-0", "Glucose", "mmol/L"),
    "creatinine": ("2160-0", "Creatinine", "µmol/L"),
    "egfr": ("33914-3", "eGFR", "mL/min/1.73m2"),
    "systolic bp": ("8480-6", "BP Systolic", "mmHg"),
    "systolic": ("8480-6", "BP Systolic", "mmHg"),
    "diastolic bp": ("8462-4", "BP Diastolic", "mmHg"),
    "diastolic": ("8462-4", "BP Diastolic", "mmHg"),
    "triglyceride": ("2571-8", "Triglyceride", "mmol/L"),
    "ldl-c": ("13457-7", "LDL-C", "mmol/L"),
    "ldl": ("13457-7", "LDL-C", "mmol/L"),
    "hdl-c": ("2085-9", "HDL-C", "mmol/L"),
    "hdl": ("2085-9", "HDL-C", "mmol/L"),
    "alt": ("1742-6", "ALT", "U/L"),
    "ast": ("1920-8", "AST", "U/L"),
    "uric acid": ("3084-1", "Uric Acid", "µmol/L"),
    "hemoglobin": ("718-7", "Hemoglobin", "g/L"),
}


@dataclass
class ParsedObservation:
    name: str
    code: str
    value: float
    unit: str
    flag: str | None = None
    reference_range: str | None = None


@dataclass
class ParsedCondition:
    name: str
    code: str | None = None
    recorded_date: str | None = None


@dataclass
class ParsedMedication:
    name: str
    dose: str | None = None
    status: str = "active"


@dataclass
class ParsedClinicalDocument:
    patient_id: str | None = None
    patient_name: str | None = None
    gender: str | None = None
    birth_date: str | None = None
    document_id: str | None = None
    document_date: str | None = None
    document_title: str | None = None
    markdown_content: str = ""
    conditions: list[ParsedCondition] = field(default_factory=list)
    observations: list[ParsedObservation] = field(default_factory=list)
    medications: list[ParsedMedication] = field(default_factory=list)
    raw_dict: dict[str, Any] = field(default_factory=dict)


_PARSE_PROMPT = """Bạn là chuyên gia phân tích tài liệu y tế lâm sàng.
Nhiệm vụ của bạn là đọc nội dung Markdown của tài liệu y tế (phiếu xét nghiệm, đơn thuốc, tóm tắt bệnh án) và trích xuất thông tin theo cấu trúc JSON.

Quy tắc trích xuất:
1. Thông tin bệnh nhân:
   - patient_id: Mã bệnh nhân (ví dụ PAT-001, PAT-002, nếu có).
   - patient_name: Tên bệnh nhân (ví dụ: Nguyễn Demo An).
   - gender: Giới tính (male/female/unknown).
   - birth_date: Ngày sinh (YYYY-MM-DD nếu có).
2. Thông tin tài liệu:
   - document_id: Mã tài liệu (ví dụ: DOC-PAT001-LAB-002).
   - document_date: Ngày xét nghiệm / ngày lập phiếu (YYYY-MM-DD).
   - document_title: Tiêu đề tài liệu.
3. Chẩn đoán / Tiền sử bệnh (conditions):
   - name: Tên bệnh (ví dụ: Đái tháo đường type 2, Tăng huyết áp).
   - code: Mã SNOMED hoặc ICD nếu có (ví dụ 44054006, 38341003).
   - recorded_date: Ngày ghi nhận (YYYY-MM-DD).
4. Các chỉ số xét nghiệm & Sinh hiệu (observations):
   - name: Tên xét nghiệm (HbA1c, Glucose, Creatinine, eGFR, Systolic BP, Diastolic BP, ALT, LDL-C, HDL-C, Triglyceride, Uric Acid, Hemoglobin...).
   - code: Mã LOINC tương ứng (ví dụ: HbA1c là "4548-4", Glucose là "2339-0", Creatinine là "2160-0", eGFR là "33914-3", Systolic BP là "8480-6", Diastolic BP là "8462-4").
   - value: Giá trị dạng số thực (float, ví dụ 7.3, 8.2, 88, 72, 138, 86).
   - unit: Đơn vị đo (ví dụ %, mmol/L, µmol/L, mL/min/1.73m2, mmHg, U/L, g/L).
   - flag: Cờ bất thường nếu có (H: Cao, L: Thấp, hoặc null).
   - reference_range: Khoảng tham chiếu nếu có.
5. Thuốc (medications) nếu có.

Định dạng JSON trả về:
{
  "patient_id": "PAT-001",
  "patient_name": "Nguyễn Demo An",
  "gender": "female",
  "birth_date": "1965-04-12",
  "document_id": "DOC-PAT001-LAB-002",
  "document_date": "2026-08-17",
  "document_title": "PHIẾU KẾT QUẢ XÉT NGHIỆM",
  "conditions": [
    {"name": "Đái tháo đường type 2", "code": "44054006", "recorded_date": "2023-01-10"}
  ],
  "observations": [
    {"name": "HbA1c", "code": "4548-4", "value": 7.3, "unit": "%", "flag": "H", "reference_range": "4.0 - 6.0"}
  ],
  "medications": []
}

Chỉ trả về JSON duy nhất, không thêm văn bản ngoài JSON.
"""


def _normalize_loinc(name: str, given_code: str | None) -> tuple[str, str, str]:
    """Resolve LOINC code, display name, and standard unit."""
    name_clean = name.strip().lower()
    for key, (code, display, unit) in LOINC_MAP.items():
        if key in name_clean:
            return code, display, unit
    if given_code:
        return given_code, name, ""
    return name, name, ""


def _deterministic_regex_parse(markdown_text: str) -> ParsedClinicalDocument:
    """Fallback regex extractor for offline or unit test usage."""
    doc = ParsedClinicalDocument(markdown_content=markdown_text)

    # 1. Patient ID
    m_pid = re.search(r"(?:Mã bệnh nhân|Ma benh nhan|Patient ID|patient_id)\s*[:=]\s*([A-Za-z0-9_-]+)", markdown_text, re.IGNORECASE)
    if m_pid:
        doc.patient_id = m_pid.group(1).strip()

    # 2. Patient Name
    m_name = re.search(r"(?:Tên synthetic|Tên bệnh nhân|Họ và tên|Ho va ten|Patient Name)\s*[:=]\s*([^\n\r,;|]+?)(?=\s+(?:Mã bệnh nhân|Ma benh nhan|Gioi tinh|Giới tính|Tuổi|Tuoi|SN|DOB|$))", markdown_text, re.IGNORECASE)
    if m_name:
        doc.patient_name = m_name.group(1).strip()
    else:
        m_name2 = re.search(r"(?:Tên synthetic|Tên bệnh nhân|Họ và tên|Ho va ten|Patient Name)\s*[:=]\s*([^\n\r,;|]+)", markdown_text, re.IGNORECASE)
        if m_name2:
            doc.patient_name = m_name2.group(1).strip()

    # 3. Gender & Birth date
    m_gender = re.search(r"(?:Giới tính|Gioi tinh|Sex|Gender)\s*[:=]\s*(Nam|Nữ|Male|Female|Nu)", markdown_text, re.IGNORECASE)
    if m_gender:
        g = m_gender.group(1).lower()
        doc.gender = "male" if g in ("nam", "male") else "female"

    m_dob = re.search(r"(?:SN|DOB|Ngày sinh|Ngay sinh|Sinh năm)\s*[:=]?\s*(\d{4}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4})", markdown_text, re.IGNORECASE)
    if m_dob:
        raw_dob = m_dob.group(1)
        if len(raw_dob) == 4:
            doc.birth_date = f"{raw_dob}-01-01"
        else:
            parts = re.split(r"[/.-]", raw_dob)
            if len(parts) == 3:
                doc.birth_date = f"{parts[2]}-{int(parts[1]):02d}-{int(parts[0]):02d}"

    # 4. Document ID
    m_docid = re.search(r"(?:Mã tài liệu|Document ID|doc_id)\s*[:=]\s*([A-Za-z0-9_-]+)", markdown_text, re.IGNORECASE)
    if m_docid:
        doc.document_id = m_docid.group(1).strip()

    # 5. Document Date
    m_date = re.search(r"(?:Ngày tài liệu|Ngày xét nghiệm|Date|Ngày khám|Ngay kham)\s*[:=]\s*(\d{4}-\d{2}-\d{2})", markdown_text, re.IGNORECASE)
    if m_date:
        doc.document_date = m_date.group(1)
    else:
        m_date_vn = re.search(r"(?:Ngày khám|Ngay kham|Ngày|Ngay|Date)?\s*[:=]?\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", markdown_text, re.IGNORECASE)
        if m_date_vn:
            d, m, y = m_date_vn.groups()
            doc.document_date = f"{y}-{int(m):02d}-{int(d):02d}"

    # 6. Conditions / Diagnosis
    m_cond = re.search(r"(?:Chẩn đoán|Chan doan|Diagnosis|Conditions?)\s*[:=]\s*([^\n\r]+)", markdown_text, re.IGNORECASE)
    if m_cond:
        cond_str = m_cond.group(1).strip()
        for c_item in re.split(r"[,;]+", cond_str):
            c_clean = c_item.strip()
            if c_clean and len(c_clean) > 2:
                code_m = re.search(r"\((?:ICD[-:]?\s*)?([A-Z0-9.]+)\)", c_clean)
                code_val = code_m.group(1) if code_m else None
                doc.conditions.append(ParsedCondition(name=c_clean, code=code_val, recorded_date=doc.document_date))

    # 7. Blood Pressure (e.g. 145/92 mmHg)
    m_bp = re.search(r"(?:Huyết áp|Huyet ap|Blood Pressure|BP)\s*(?:\([^)]*\))?\s*[:|]?\s*(\d{2,3})\s*[/]\s*(\d{2,3})", markdown_text, re.IGNORECASE)
    if m_bp:
        try:
            sys_val = float(m_bp.group(1))
            dia_val = float(m_bp.group(2))
            doc.observations.append(ParsedObservation(name="BP Systolic", code="8480-6", value=sys_val, unit="mmHg"))
            doc.observations.append(ParsedObservation(name="BP Diastolic", code="8462-4", value=dia_val, unit="mmHg"))
        except Exception:
            pass

    # 8. Extract Observations from table rows or lines
    obs_patterns = [
        (r"HbA1c(?:\s+[^0-9:|\n\r]+?)?\s*[:|]?\s*([0-9.]+)\s*(?:%|percent)?", "HbA1c", "4548-4", "%"),
        (r"Glucose(?:\s+[^0-9:|\n\r]+?)?\s*[:|]?\s*([0-9.]+)\s*(?:mmol/L)?", "Glucose", "2339-0", "mmol/L"),
        (r"Creatinine(?:\s+[^0-9:|\n\r]+?)?\s*[:|]?\s*([0-9.]+)\s*(?:µmol/L|umol/L)?", "Creatinine", "2160-0", "µmol/L"),
        (r"eGFR(?:\s+[^0-9:|\n\r]+?)?\s*[:|]?\s*([0-9.]+)\s*(?:mL/min|mL/min/1.73m2)?", "eGFR", "33914-3", "mL/min/1.73m2"),
        (r"Systolic BP\s*[:|]?\s*([0-9.]+)\s*(?:mmHg)?", "BP Systolic", "8480-6", "mmHg"),
        (r"Diastolic BP\s*[:|]?\s*([0-9.]+)\s*(?:mmHg)?", "BP Diastolic", "8462-4", "mmHg"),
        (r"ALT(?:\s+[^0-9:|\n\r]+?)?\s*[:|]?\s*([0-9.]+)\s*(?:U/L)?", "ALT", "1742-6", "U/L"),
        (r"AST(?:\s+[^0-9:|\n\r]+?)?\s*[:|]?\s*([0-9.]+)\s*(?:U/L)?", "AST", "1920-8", "U/L"),
        (r"LDL(?:-C)?(?:\s+[^0-9:|\n\r]+?)?\s*[:|]?\s*([0-9.]+)\s*(?:mmol/L)?", "LDL-C", "13457-7", "mmol/L"),
        (r"HDL(?:-C)?(?:\s+[^0-9:|\n\r]+?)?\s*[:|]?\s*([0-9.]+)\s*(?:mmol/L)?", "HDL-C", "2085-9", "mmol/L"),
        (r"Triglyceride(?:\s+[^0-9:|\n\r]+?)?\s*[:|]?\s*([0-9.]+)\s*(?:mmol/L)?", "Triglyceride", "2571-8", "mmol/L"),
        (r"Uric Acid(?:\s+[^0-9:|\n\r]+?)?\s*[:|]?\s*([0-9.]+)\s*(?:µmol/L|umol/L)?", "Uric Acid", "3084-1", "µmol/L"),
        (r"Hemoglobin(?:\s+[^0-9:|\n\r]+?)?\s*[:|]?\s*([0-9.]+)\s*(?:g/L)?", "Hemoglobin", "718-7", "g/L"),
    ]

    for pat, display_name, code, default_unit in obs_patterns:
        # Don't add duplicate if BP already extracted
        if display_name in ("BP Systolic", "BP Diastolic") and any(o.code == code for o in doc.observations):
            continue
        m = re.search(pat, markdown_text, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1))
                if not any(o.code == code for o in doc.observations):
                    doc.observations.append(
                        ParsedObservation(
                            name=display_name,
                            code=code,
                            value=val,
                            unit=default_unit,
                        )
                    )
            except Exception:
                pass

    # 9. Extract Medications from prescription section or lines
    med_section_match = re.search(r"(?:DON THUOC|ĐƠN THUỐC|PRESCRIPTION|Thuốc điều trị)(.*?)(?:III\.|LOI DAN|LỜI DẶN|BENH NHAN KY|BỆNH NHÂN KÝ|$)", markdown_text, re.IGNORECASE | re.DOTALL)
    med_text = med_section_match.group(1) if med_section_match else markdown_text
    for line in med_text.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("STT") or line_clean.startswith("ST") or "Ten thuoc" in line_clean or "Tên thuốc" in line_clean:
            continue
        # Pattern 1: e.g. "1 Metformin 1000 mg (Glucophage) 60 vien Uong 1 vien x 2 lan/ngay"
        m_med = re.match(r"^\d+\s+([A-Za-z0-9\s()/-]+?(?:\d+\s*(?:mg|g|mcg|ml|IU|vien|viên))(?:\s*\([^)]*\))?)\s+(\d+\s*(?:vien|viên|goi|gói|chai|ong|ống|ml|hop|hộp))?\s*(.*)$", line_clean, re.IGNORECASE)
        if m_med:
            med_name = m_med.group(1).strip()
            med_dose = m_med.group(3).strip() if m_med.group(3) else None
            doc.medications.append(ParsedMedication(name=med_name, dose=med_dose))
        else:
            # Pattern 2: simple line with dosage e.g. "Metformin 500 mg: Uống 1 viên..."
            m_med2 = re.match(r"^(?:[•\-*\d.]+\s+)?([A-Za-z0-9\s()/-]+?(?:\d+\s*(?:mg|g|mcg|ml|IU))(?:\s*\([^)]*\))?)\s*[:;-]?\s*(.*)$", line_clean, re.IGNORECASE)
            if m_med2 and len(m_med2.group(1).strip()) > 3:
                med_name = m_med2.group(1).strip()
                med_dose = m_med2.group(2).strip() if m_med2.group(2) else None
                # Exclude false positives from lab tests
                if not any(k in med_name.lower() for k in ["hba1c", "glucose", "egfr", "creatinine", "huyet ap", "blood pressure", "khoang tham chieu", "danh gia"]):
                    doc.medications.append(ParsedMedication(name=med_name, dose=med_dose))

    return doc


def parse_clinical_markdown(markdown_text: str) -> ParsedClinicalDocument:
    """Parse medical markdown text into a ParsedClinicalDocument using LLM with regex fallback."""
    if not markdown_text.strip():
        return ParsedClinicalDocument(markdown_content=markdown_text)

    runtime = get_llm_runtime()
    parsed_json: dict[str, Any] | None = None

    if runtime.available:
        try:
            from src.config import get_settings
            settings = get_settings()
            api_key = settings.llm_api_key
            model_name = settings.llm_model_name
            base_url = settings.llm_base_url or None

            if model_name and model_name.lower().startswith("gemini"):
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Content(role="user", parts=[
                            types.Part.from_text(text=_PARSE_PROMPT),
                            types.Part.from_text(text=markdown_text),
                        ])
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    )
                )
                raw = response.text or "{}"
                parsed_json = json.loads(raw)
            elif api_key:
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url=base_url)
                response = client.chat.completions.create(
                    model=model_name,
                    temperature=0.0,
                    messages=[
                        {"role": "system", "content": _PARSE_PROMPT},
                        {"role": "user", "content": markdown_text},
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=4096,
                )
                raw = response.choices[0].message.content or "{}"
                parsed_json = json.loads(raw)
        except Exception as exc:
            logger.warning("LLM parsing of markdown failed; using deterministic fallback: %s", exc)

    if not parsed_json or not isinstance(parsed_json, dict):
        return _deterministic_regex_parse(markdown_text)

    # Construct ParsedClinicalDocument from LLM JSON
    pid = parsed_json.get("patient_id")
    if pid:
        pid = str(pid).strip().upper().replace("PAT", "PAT-").replace("--", "-")

    pname = parsed_json.get("patient_name")
    gender = parsed_json.get("gender")
    bdate = parsed_json.get("birth_date")
    doc_id = parsed_json.get("document_id")
    doc_date = parsed_json.get("document_date")
    doc_title = parsed_json.get("document_title")

    conditions = []
    for cond in parsed_json.get("conditions", []):
        if isinstance(cond, dict) and cond.get("name"):
            conditions.append(
                ParsedCondition(
                    name=str(cond["name"]).strip(),
                    code=str(cond.get("code")) if cond.get("code") else None,
                    recorded_date=str(cond.get("recorded_date")) if cond.get("recorded_date") else None,
                )
            )

    observations = []
    for obs in parsed_json.get("observations", []):
        if isinstance(obs, dict) and obs.get("name") and obs.get("value") is not None:
            try:
                val = float(obs["value"])
                name = str(obs["name"]).strip()
                code, display, std_unit = _normalize_loinc(name, obs.get("code"))
                unit = str(obs.get("unit") or std_unit)
                observations.append(
                    ParsedObservation(
                        name=display,
                        code=code,
                        value=val,
                        unit=unit,
                        flag=str(obs.get("flag")) if obs.get("flag") else None,
                        reference_range=str(obs.get("reference_range")) if obs.get("reference_range") else None,
                    )
                )
            except Exception:
                continue

    medications = []
    for med in parsed_json.get("medications", []):
        if isinstance(med, dict) and med.get("name"):
            medications.append(
                ParsedMedication(
                    name=str(med["name"]).strip(),
                    dose=str(med.get("dose")) if med.get("dose") else None,
                    status=str(med.get("status") or "active"),
                )
            )

    return ParsedClinicalDocument(
        patient_id=pid,
        patient_name=pname,
        gender=gender,
        birth_date=bdate,
        document_id=doc_id,
        document_date=doc_date,
        document_title=doc_title,
        markdown_content=markdown_text,
        conditions=conditions,
        observations=observations,
        medications=medications,
        raw_dict=parsed_json,
    )
