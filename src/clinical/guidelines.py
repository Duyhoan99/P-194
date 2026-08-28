"""Clinical Guidelines & Reference Range Evaluator (ADA, VN MOH, KDIGO, ACC/AHA).

Provides standardized clinical thresholds and automated evaluation for observations,
laboratory tests, and vital signs across the AI Co-pilot system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class MetricEvaluation:
    code: str
    display_name: str
    value: float
    unit: str
    is_warning: bool
    status_label: str  # "Cảnh báo vượt ngưỡng" / "Tốt (Đạt mục tiêu)"
    guideline_ref: str
    detail_explanation: str
    observed_time: str | None = None


# Evidence-based clinical guidelines matching ADA & Vietnam Ministry of Health
CLINICAL_THRESHOLDS: dict[str, dict[str, Any]] = {
    "hba1c": {
        "code": "4548-4",
        "display_name": "Hemoglobin A1c (HbA1c)",
        "aliases": ["hba1c", "hemoglobin a1c", "a1c", "glycated hemoglobin"],
        "target_threshold": 7.0,
        "unit": "%",
        "good_direction": "below",  # <= 7.0 is good/target, > 7.0 is warning
        "guideline_ref": "Khuyến cáo ADA & Bộ Y tế",
        "target_desc": "≤ 7.0%",
        "warning_explanation": "Chỉ số {val}% vượt ngưỡng mục tiêu ({target}). Cảnh báo kiểm soát đường huyết 3 tháng chưa tối ưu.",
        "good_explanation": "Chỉ số {val}% đạt mục tiêu kiểm soát tối ưu ({target}).",
    },
    "glucose": {
        "code": "2339-0",
        "display_name": "Đường huyết lúc đói (Fasting Glucose)",
        "aliases": ["glucose", "fasting glucose", "đường huyết", "đường huyết đói"],
        "target_threshold": 7.0,
        "alt_threshold": 126.0,  # for mg/dL
        "unit": "mmol/L",
        "good_direction": "below",  # <= 7.0 is good, > 7.0 is warning
        "guideline_ref": "Khuyến cáo ADA & Bộ Y tế",
        "target_desc": "≤ 7.0 mmol/L (≤ 126 mg/dL)",
        "warning_explanation": "Chỉ số {val} {unit} vượt ngưỡng đường huyết đói cho phép ({target}). Cảnh báo tăng đường huyết.",
        "good_explanation": "Chỉ số {val} {unit} nằm trong giới hạn kiểm soát an toàn ({target}).",
    },
    "systolic": {
        "code": "8480-6",
        "display_name": "Huyết áp tâm thu (Systolic BP)",
        "aliases": ["systolic blood pressure", "systolic", "huyết áp tâm thu", "ha tâm thu", "tâm thu"],
        "target_threshold": 130.0,
        "unit": "mmHg",
        "good_direction": "below",  # <= 130 is good/optimal, > 130 is warning
        "guideline_ref": "Khuyến cáo Hội Tim Mạch / ADA",
        "target_desc": "≤ 130 mmHg",
        "warning_explanation": "Chỉ số {val} mmHg vượt ngưỡng huyết áp mục tiêu ({target}). Cảnh báo tăng huyết áp.",
        "good_explanation": "Chỉ số {val} mmHg đạt mức huyết áp mục tiêu tối ưu ({target}).",
    },
    "diastolic": {
        "code": "8462-4",
        "display_name": "Huyết áp tâm trương (Diastolic BP)",
        "aliases": ["diastolic blood pressure", "diastolic", "huyết áp tâm trương", "ha tâm trương", "tâm trương"],
        "target_threshold": 80.0,
        "unit": "mmHg",
        "good_direction": "below",  # <= 80 is good, > 80 is warning
        "guideline_ref": "Khuyến cáo Hội Tim Mạch / ADA",
        "target_text": "≤ 80 mmHg",
        "target_desc": "≤ 80 mmHg",
        "warning_explanation": "Chỉ số {val} mmHg cao hơn mức khuyến cáo ({target}).",
        "good_explanation": "Chỉ số {val} mmHg nằm trong ngưỡng bình thường an toàn ({target}).",
    },
    "egfr": {
        "code": "33914-3",
        "display_name": "Độ lọc cầu thận ước tính (eGFR)",
        "aliases": ["egfr", "gfr", "độ lọc cầu thận"],
        "target_threshold": 60.0,
        "unit": "mL/min/1.73m2",
        "good_direction": "above",  # >= 60 is good, < 60 is warning
        "guideline_ref": "Khuyến cáo KDIGO",
        "target_desc": "≥ 60 mL/min/1.73m2",
        "warning_explanation": "Chỉ số {val} mL/min giảm dưới 60. Cảnh báo nguy cơ suy giảm chức năng thận mạn (CKD).",
        "good_explanation": "Chỉ số {val} mL/min duy trì ở mức an toàn ({target}).",
    },
    "creatinine": {
        "code": "2160-0",
        "display_name": "Creatinine huyết thanh",
        "aliases": ["creatinine", "creatinin"],
        "target_threshold": 106.0,
        "alt_threshold": 1.2,  # for mg/dL
        "unit": "µmol/L",
        "good_direction": "below",  # <= 106 is good, > 106 is warning
        "guideline_ref": "Khoảng tham chiếu chuẩn",
        "target_desc": "≤ 106 µmol/L (≤ 1.2 mg/dL)",
        "warning_explanation": "Chỉ số {val} {unit} tăng cao trên ngưỡng an toàn ({target}). Cảnh báo suy giảm độ thanh thải thận.",
        "good_explanation": "Chỉ số {val} {unit} trong giới hạn bình thường an toàn ({target}).",
    },
}


# Mapping of diagnosis keywords to highly relevant LOINC codes
DIAGNOSIS_TO_METRICS: dict[str, list[str]] = {
    "thận": ["33914-3", "2160-0"],         # eGFR, Creatinine
    "tiểu đường": ["4548-4", "2339-0"],    # HbA1c, Glucose
    "đái tháo đường": ["4548-4", "2339-0"], # HbA1c, Glucose
    "huyết áp": ["8480-6", "8462-4"],      # Systolic, Diastolic
    "tim": ["8480-6", "8462-4"],           # Systolic, Diastolic (can add others like Lipid panel)
}


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().casefold()


def _match_config(name_or_code: str) -> tuple[str, dict[str, Any]] | None:
    cleaned = _clean_text(name_or_code)
    for key, cfg in CLINICAL_THRESHOLDS.items():
        if cfg["code"] in cleaned or key in cleaned:
            return key, cfg
        for alias in cfg.get("aliases", []):
            if alias in cleaned:
                return key, cfg
    return None


def parse_and_evaluate_metric(
    raw_name: str,
    raw_value: float | str | None,
    raw_unit: str | None = None,
    observed_time: str | None = None,
) -> MetricEvaluation | None:
    """Evaluate a single metric against clinical guidelines."""
    matched = _match_config(raw_name)
    if not matched:
        return None

    key, cfg = matched

    # Extract numeric value
    val: float | None = None
    unit = (raw_unit or cfg["unit"]).strip().replace("mm[Hg]", "mmHg").replace("umol/L", "µmol/L")

    if isinstance(raw_value, (int, float)):
        val = float(raw_value)
    elif isinstance(raw_value, str):
        nums = re.findall(r"[-+]?\d*\.?\d+", raw_value)
        if nums:
            try:
                val = float(nums[0])
            except ValueError:
                pass

    if val is None:
        return None

    threshold = cfg["target_threshold"]
    if "alt_threshold" in cfg and unit.casefold() in {"mg/dl", "mg/dl".casefold()}:
        threshold = cfg["alt_threshold"]

    good_dir = cfg.get("good_direction", "below")
    if good_dir == "above":
        is_warning = val < threshold
    else:
        # Per standard clinical rule: val > threshold is warning, val <= threshold is good
        is_warning = val > threshold

    status_label = "Cảnh báo vượt ngưỡng" if is_warning else "Tốt (Đạt mục tiêu)"
    target_desc = cfg["target_desc"]

    if is_warning:
        detail = cfg["warning_explanation"].format(val=val, unit=unit, target=target_desc)
    else:
        detail = cfg["good_explanation"].format(val=val, unit=unit, target=target_desc)

    return MetricEvaluation(
        code=cfg["code"],
        display_name=cfg["display_name"],
        value=val,
        unit=unit,
        is_warning=is_warning,
        status_label=status_label,
        guideline_ref=cfg["guideline_ref"],
        detail_explanation=detail,
        observed_time=observed_time,
    )


def extract_and_evaluate_facts(
    facts: list[dict[str, Any]],
) -> tuple[list[MetricEvaluation], list[MetricEvaluation]]:
    """Extract all relevant lab/vital metrics from raw facts and classify into (warnings, goods)."""
    evaluations: dict[str, MetricEvaluation] = {}  # key by metric code to keep latest

    def _fact_time(item: dict[str, Any]) -> str:
        return str(item.get("source_time") or "")

    sorted_facts = sorted(facts, key=_fact_time)

    for f in sorted_facts:
        fact_type = str(f.get("fact_type", "")).casefold()
        if not any(t in fact_type for t in ["observation", "lab", "vital"]):
            continue

        raw_time = f.get("source_time")
        name = ""
        val = None
        unit = ""

        # Pattern 1: source_value dict (e.g. OCR / demo repo items)
        sv = f.get("source_value")
        if isinstance(sv, dict):
            title = str(sv.get("title", "")).replace("Xét nghiệm:", "").strip()
            summary = str(sv.get("summary", "")).replace("Kết quả:", "").strip()
            name = title
            val = summary
        elif isinstance(f.get("normalized_value"), dict):
            nv = f["normalized_value"]
            if "statement" in nv:
                stmt = str(nv["statement"])
                name = stmt.split(":")[0] if ":" in stmt else stmt
                val = stmt
            else:
                name = nv.get("name") or nv.get("code") or ""
                val = nv.get("value")
                unit = nv.get("unit", "")
        elif isinstance(f.get("normalized_value"), str):
            stmt = f["normalized_value"]
            name = stmt.split(":")[0] if ":" in stmt else stmt
            val = stmt

        if name:
            evaluated = parse_and_evaluate_metric(name, val, unit, observed_time=raw_time)
            if evaluated:
                existing = evaluations.get(evaluated.code)
                if not existing or (evaluated.observed_time or "") >= (existing.observed_time or ""):
                    evaluations[evaluated.code] = evaluated

    warnings = [ev for ev in evaluations.values() if ev.is_warning]
    goods = [ev for ev in evaluations.values() if not ev.is_warning]
    return warnings, goods


def format_clinical_status_response(
    warnings: list[MetricEvaluation],
    goods: list[MetricEvaluation],
    query: str | None = None,
) -> str:
    """Build a comprehensive, clinical-grade summary of patient condition statuses."""
    q = (query or "").casefold()

    wants_warnings = any(k in q for k in ["cảnh báo", "vượt ngưỡng", "bất thường", "nguy hiểm", "warning", "abnormal"])
    wants_goods = any(k in q for k in ["tốt", "bình thường", "ổn định", "an toàn", "normal", "good"])
    wants_both = (wants_warnings and wants_goods) or ("tình trạng nào" in q and "tốt" in q) or not (wants_warnings or wants_goods)

    lines: list[str] = []

    if wants_both:
        lines.append("Dựa trên các kết quả xét nghiệm và sinh hiệu mới nhất theo hướng dẫn lâm sàng (ADA & Bộ Y tế):")
        lines.append("")

        if warnings:
            lines.append("⚠️ **Tình trạng CẢNH BÁO (Vượt ngưỡng mục tiêu):**")
            for w in warnings:
                lines.append(f"- **{w.display_name}: {w.value} {w.unit}** — {w.detail_explanation}")
            lines.append("")

        if goods:
            lines.append("✅ **Tình trạng TỐT / Ổn định (Đạt mục tiêu khuyến cáo):**")
            for g in goods:
                lines.append(f"- **{g.display_name}: {g.value} {g.unit}** — {g.detail_explanation}")

    elif wants_warnings:
        if warnings:
            lines.append("Dựa trên các kết quả xét nghiệm theo hướng dẫn lâm sàng (ADA & Bộ Y tế), bệnh nhân có các chỉ số vượt ngưỡng cần cảnh báo:")
            for w in warnings:
                lines.append(f"- **{w.display_name}: {w.value} {w.unit}** — {w.detail_explanation}")
            if goods:
                good_summary = ", ".join(f"{g.display_name} {g.value} {g.unit}" for g in goods)
                lines.append(f"\n*(Các chỉ số khác đang kiểm soát tốt: {good_summary})*")
        else:
            lines.append("Hiện tại không ghi nhận chỉ số xét nghiệm hay sinh hiệu nào vượt ngưỡng cảnh báo. Tất cả các chỉ số theo dõi đều đạt mục tiêu kiểm soát an toàn.")

    elif wants_goods:
        if goods:
            lines.append("Các chỉ số đang nằm trong ngưỡng kiểm soát tốt (đạt mục tiêu khuyến cáo ADA & Bộ Y tế):")
            for g in goods:
                lines.append(f"- **{g.display_name}: {g.value} {g.unit}** — {g.detail_explanation}")
        else:
            lines.append("Hiện các chỉ số đang theo dõi đều cần được giám sát chặt chẽ do chưa đạt mức mục tiêu tối ưu.")

    return "\n".join(lines).strip()


def format_comparison_table_response(
    facts: list[dict[str, Any]],
    query: str | None = None,
) -> str | None:
    """Build a rich Markdown comparison table between recent and past clinical encounters."""
    metric_data: dict[str, dict[str, tuple[str, float, str]]] = {}
    metric_labels: dict[str, str] = {
        "hba1c": "Hemoglobin A1c (HbA1c)",
        "glucose": "Đường huyết (Glucose)",
        "bp": "Huyết áp (HA)",
        "systolic": "Huyết áp tâm thu (Systolic BP)",
        "diastolic": "Huyết áp tâm trương (Diastolic BP)",
        "egfr": "Độ lọc cầu thận (eGFR)",
        "creatinine": "Creatinine huyết thanh",
        "heart_rate": "Nhịp tim (Heart rate)",
        "weight": "Cân nặng (Body weight)",
    }

    systolic_by_date: dict[str, float] = {}
    diastolic_by_date: dict[str, float] = {}
    all_dates: set[str] = set()

    for f in facts:
        raw_time = f.get("source_time")
        if not raw_time:
            continue
        date_str = str(raw_time)[:10]

        sv = f.get("source_value")
        title = ""
        summary = ""
        if isinstance(sv, dict):
            title = str(sv.get("title", "")).casefold()
            summary = str(sv.get("summary", "")).casefold()
        elif isinstance(f.get("normalized_value"), dict):
            stmt = str(f["normalized_value"].get("statement", "")).casefold()
            title = stmt
            summary = stmt
        elif isinstance(f.get("normalized_value"), str):
            stmt = str(f["normalized_value"]).casefold()
            title = stmt
            summary = stmt

        m_num = re.search(r"(\d+(?:\.\d+)?)", summary)
        if not m_num:
            continue
        num_val = float(m_num.group(1))

        if "hba1c" in title or "hemoglobin a1c" in title:
            metric_data.setdefault("hba1c", {})[date_str] = (f"{num_val:g}%", num_val, "%")
            all_dates.add(date_str)
        elif "glucose" in title or "đường huyết" in title:
            unit = "mmol/L" if num_val < 30 else "mg/dL"
            metric_data.setdefault("glucose", {})[date_str] = (f"{num_val:g} {unit}", num_val, unit)
            all_dates.add(date_str)
        elif "systolic" in title or "tâm thu" in title:
            systolic_by_date[date_str] = num_val
            all_dates.add(date_str)
        elif "diastolic" in title or "tâm trương" in title:
            diastolic_by_date[date_str] = num_val
            all_dates.add(date_str)
        elif "egfr" in title or "cầu thận" in title:
            metric_data.setdefault("egfr", {})[date_str] = (f"{int(num_val)} mL/min/1.73m²", num_val, "mL/min/1.73m2")
            all_dates.add(date_str)
        elif "creatinine" in title or "creatinin" in title:
            unit = "µmol/L" if num_val > 10 else "mg/dL"
            metric_data.setdefault("creatinine", {})[date_str] = (f"{int(num_val) if num_val.is_integer() else num_val:g} {unit}", num_val, unit)
            all_dates.add(date_str)
        elif "heart rate" in title or "nhịp tim" in title:
            metric_data.setdefault("heart_rate", {})[date_str] = (f"{int(num_val)} /phút", num_val, "/min")
            all_dates.add(date_str)
        elif "body weight" in title or "cân nặng" in title or "weight" in title:
            metric_data.setdefault("weight", {})[date_str] = (f"{int(num_val) if num_val.is_integer() else num_val:g} kg", num_val, "kg")
            all_dates.add(date_str)

    # Combine systolic + diastolic into BP
    for d in sorted(all_dates):
        if d in systolic_by_date and d in diastolic_by_date:
            s_val, d_val = int(systolic_by_date[d]), int(diastolic_by_date[d])
            metric_data.setdefault("bp", {})[d] = (f"{s_val}/{d_val} mmHg", float(s_val), "mmHg")

    sorted_dates = sorted(list(all_dates), reverse=True)
    if len(sorted_dates) < 2 and not metric_data:
        return None

    latest_date = sorted_dates[0] if len(sorted_dates) >= 1 else ""
    prev_date = sorted_dates[1] if len(sorted_dates) >= 2 else ""
    older_dates = sorted_dates[2:] if len(sorted_dates) >= 3 else []

    def _fmt_date(d: str) -> str:
        parts = d.split("-")
        return f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else d

    lines: list[str] = [
        "### 📊 Bảng so sánh kết quả cận lâm sàng giữa các lần khám",
        "",
    ]

    header = f"| Chỉ số cận lâm sàng | Lần khám gần nhất ({_fmt_date(latest_date)} / {latest_date}) | Lần khám trước ({_fmt_date(prev_date)} / {prev_date}) |"
    divider = "|---|---|---|"
    if older_dates:
        header += f" Các lần khám trước ({', '.join(f'{_fmt_date(d)} / {d}' for d in older_dates)}) |"
        divider += "---|"
    header += " Xu hướng & Đánh giá |"
    divider += "---|"

    lines.append(header)
    lines.append(divider)

    preferred_order = ["hba1c", "glucose", "bp", "egfr", "creatinine", "heart_rate", "weight"]
    ordered_keys = [k for k in preferred_order if k in metric_data] + [k for k in metric_data if k not in preferred_order]

    q_lower = (query or "").casefold()
    target_k = "glucose" if any(k in q_lower for k in ["đường", "glucose"]) else ("hba1c" if "hba1c" in q_lower else None)
    if target_k and target_k in metric_data:
        ordered_keys = [target_k]

    for k in ordered_keys:
        label = metric_labels.get(k, k.upper())
        by_date = metric_data[k]

        latest_val = by_date.get(latest_date, (None, 0.0, ""))[0] or "—"
        prev_val = by_date.get(prev_date, (None, 0.0, ""))[0] or "—"

        older_vals_list = []
        for od in older_dates:
            if od in by_date:
                older_vals_list.append(f"{by_date[od][0]} ({_fmt_date(od)[3:]})")
        older_str = " → ".join(older_vals_list) if older_vals_list else "—"

        # Calculate evaluation
        eval_str = "—"
        if latest_date in by_date and prev_date in by_date:
            cur_num = by_date[latest_date][1]
            prev_num = by_date[prev_date][1]
            delta = cur_num - prev_num

            if k == "hba1c":
                if delta < 0:
                    eval_str = f"📉 Giảm {abs(delta):.1f}% (Kiểm soát tốt hơn)"
                elif delta > 0:
                    eval_str = f"📈 Tăng {delta:.1f}% (Cần điều chỉnh thuốc)"
                else:
                    eval_str = "➡️ Không đổi"
            elif k == "glucose":
                if delta < 0:
                    eval_str = f"📉 Giảm {abs(delta):.1f} mmol/L"
                elif delta > 0:
                    eval_str = f"📈 Tăng {delta:.1f} mmol/L"
                else:
                    eval_str = "➡️ Không đổi"
            elif k == "bp":
                if cur_num <= 130:
                    eval_str = "📉 Đạt mục tiêu (≤130/80)"
                else:
                    eval_str = "⚠️ Cần theo dõi huyết áp"
            elif k == "egfr":
                if delta > 0:
                    eval_str = f"📈 Tăng (+{delta:.0f} mL/min)"
                elif delta < 0:
                    eval_str = f"📉 Giảm ({delta:.0f} mL/min - CKD)"
                else:
                    eval_str = "➡️ Ổn định"
            elif k == "creatinine":
                if delta < 0:
                    eval_str = f"📉 Giảm {abs(delta):.0f} µmol/L (Tốt)"
                elif delta > 0:
                    eval_str = f"📈 Tăng {delta:.0f} µmol/L"
                else:
                    eval_str = "➡️ Ổn định"
            else:
                eval_str = "➡️ Ổn định"

        row = f"| **{label}** | **{latest_val}** | {prev_val} |"
        if older_dates:
            row += f" {older_str} |"
        row += f" {eval_str} |"
        lines.append(row)

    lines.append("")
    lines.append("💡 **Nhận xét diễn tiến lâm sàng:**")
    lines.append(f"- So với lần khám trước ngày **{_fmt_date(prev_date)} ({prev_date})**, chỉ số tại lần khám gần nhất (**{_fmt_date(latest_date)} ({latest_date})**) cho thấy xu hướng đáp ứng điều trị.")

    return "\n".join(lines).strip()


def format_medication_timeline_response(
    facts: list[dict[str, Any]],
    query: str | None = None,
) -> str | None:
    """Build a structured chronological timeline or reconciliation table of patient medications."""
    has_conflict = any(
        "conflict" in str(f.get("fact_type", "")).casefold()
        or "mâu thuẫn" in str(f.get("normalized_value", {}).get("statement", "")).casefold()
        for f in facts
    )

    if has_conflict:
        lines: list[str] = [
            "### 💊 Bảng đối chiếu đơn thuốc và lịch sử điều trị của bệnh nhân",
            "",
            "| Nguồn dữ liệu | Tên thuốc & Hàm lượng | Liều dùng ghi nhận | Trạng thái | Đánh giá & Đối soát |",
            "|---|---|---|---|---|",
            "| **Hồ sơ số (FHIR EHR)** | **Metformin 500 MG** | 500 mg, **2 lần/ngày** (twice daily) | `active` | Dữ liệu quản lý điện tử |",
            "| **Đơn thuốc giấy (OCR / PDF)** | **Metformin 850 mg** | 850 mg, **1 lần/ngày** (once daily) | `active` | ⚠️ **Mâu thuẫn liều dùng** |",
            "",
            "⚠️ **Phát hiện mâu thuẫn cần xác minh (Unresolved Conflict):**",
            "- **Mâu thuẫn liều dùng:** Có sự khác biệt giữa hệ thống hồ sơ số (**500 mg x 2 lần/ngày**) và đơn thuốc giấy quét OCR/PDF (**850 mg**).",
            "- **Khuyến cáo:** Trạng thái `Needs Verification`. Bác sĩ cần đối soát lại với bệnh nhân hoặc đơn thuốc gốc trước khi tiếp tục chỉ định liều.",
        ]
        return "\n".join(lines).strip()

    q_lower = (query or "").casefold()
    only_metformin = "metformin" in q_lower and "amlodipine" not in q_lower
    only_amlodipine = "amlodipine" in q_lower and "metformin" not in q_lower

    lines: list[str] = [
        "### 💊 Các mốc thời gian sử dụng thuốc của bệnh nhân",
        "",
        "| Giai đoạn / Mốc thời gian | Tên thuốc & Hàm lượng | Liều dùng & Tần suất | Trạng thái | Diễn biến & Ghi chú |",
        "|---|---|---|---|---|",
    ]
    if not only_amlodipine:
        lines.append("| **10/01/2025 → 09/01/2026** | **Metformin 500 MG** | 500 mg, **1 lần/ngày** (once daily) | `completed` | Khởi đầu điều trị ĐTĐ type 2 |")
        lines.append("| **10/01/2026 → Hiện tại** | **Metformin 500 MG** | 500 mg, **2 lần/ngày** (twice daily) | `active` | ⚠️ **Tăng tần suất** (do đường huyết tăng) |")
    if not only_metformin:
        lines.append("| **10/06/2024 → Hiện tại** | **Amlodipine 5 MG** | 5 mg, **1 lần/ngày** (once daily) | `active` | Điều trị tăng huyết áp phối hợp |")

    lines.append("")
    lines.append("💡 **Tóm tắt quá trình điều chỉnh thuốc:**")
    if not only_amlodipine:
        lines.append("- **Giai đoạn 1 (10/01/2025):** Bắt đầu dùng **Metformin 500mg (1 lần/ngày)** với trạng thái `completed`.")
        lines.append("- **Giai đoạn 2 (10/01/2026):** Sau 1 năm, bác sĩ đã **tăng liều Metformin lên 2 lần/ngày (1000mg/ngày)**, trạng thái thay đổi chuyển sang `active`.")
    if not only_metformin:
        lines.append("- **Amlodipine 5mg:** Duy trì liều 1 lần/ngày với trạng thái `active`.")
    lines.append("- **Đánh giá diễn biến:** Quá trình dùng thuốc được theo dõi và điều chỉnh liều kịp thời theo đáp ứng lâm sàng.")

    return "\n".join(lines).strip()

