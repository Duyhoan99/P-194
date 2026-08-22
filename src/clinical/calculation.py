"""Calculation contract implementation strictly obeying ARCHITECTURE.md section 14.11.1."""

import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Literal


@dataclass
class CalculationProvenance:
    calculation_id: str
    calculation_version: str
    method: Literal["unit_conversion", "derived"]
    source: str
    input_evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calculation_id": self.calculation_id,
            "calculation_version": self.calculation_version,
            "method": self.method,
            "source": self.source,
            "input_evidence_ids": self.input_evidence_ids,
        }


def convert_unit(
    raw_value: float | Decimal,
    analyte_code: str,
    from_unit: str,
    to_unit: str,
    evidence_ids: list[str] | None = None,
) -> tuple[Decimal, int, str, CalculationProvenance | None]:
    """
    Convert lab raw value to canonical unit using Decimal precision according to ARCHITECTURE.md 14.11.1.
    Returns: (canonical_decimal_value, display_scale, canonical_unit, provenance)
    """
    val = Decimal(str(raw_value))
    evidence_ids = evidence_ids or []
    calc_id = f"calc_{uuid.uuid4().hex[:8]}"

    clean_from = from_unit.strip().lower()
    clean_to = to_unit.strip().lower()

    # Glucose conversion
    if analyte_code in ("2339-0", "GLUCOSE", "glucose"):
        if clean_from == "mg/dl" and clean_to in ("mmol/l", "mmol/L".lower()):
            canonical = val * Decimal("0.0555")
            prov = CalculationProvenance(
                calculation_id=calc_id,
                calculation_version="1.0.0",
                method="unit_conversion",
                source="NIDDK Diabetes in America - Conversions",
                input_evidence_ids=evidence_ids,
            )
            return canonical, 1, "mmol/L", prov
        elif clean_from in ("mmol/l", "mmol/L".lower()) and clean_to == "mg/dl":
            canonical = val / Decimal("0.0555")
            prov = CalculationProvenance(
                calculation_id=calc_id,
                calculation_version="1.0.0",
                method="unit_conversion",
                source="NIDDK Diabetes in America - Conversions",
                input_evidence_ids=evidence_ids,
            )
            return canonical, 0, "mg/dL", prov

    # Creatinine conversion
    if analyte_code in ("2160-0", "CREATININE", "creatinine"):
        if clean_from == "mg/dl" and clean_to in ("µmol/l", "umol/l", "µmol/L".lower()):
            canonical = val * Decimal("88.4")
            prov = CalculationProvenance(
                calculation_id=calc_id,
                calculation_version="1.0.0",
                method="unit_conversion",
                source="NIDDK 2021 CKD-EPI eGFR equation",
                input_evidence_ids=evidence_ids,
            )
            return canonical, 0, "µmol/L", prov
        elif clean_from in ("µmol/l", "umol/l") and clean_to == "mg/dl":
            canonical = val / Decimal("88.4")
            prov = CalculationProvenance(
                calculation_id=calc_id,
                calculation_version="1.0.0",
                method="unit_conversion",
                source="NIDDK 2021 CKD-EPI eGFR equation",
                input_evidence_ids=evidence_ids,
            )
            return canonical, 2, "mg/dL", prov

    # Same unit or no conversion rule
    return val, 2, to_unit, None


def format_display_value(val: Decimal, scale: int) -> float:
    """Format decimal value using ROUND_HALF_EVEN at display layer only."""
    quantizer = Decimal("1") if scale == 0 else Decimal("1." + "0" * scale)
    rounded = val.quantize(quantizer, rounding=ROUND_HALF_EVEN)
    return float(rounded)


def calculate_delta(
    new_val: float | Decimal,
    old_val: float | Decimal,
) -> tuple[Decimal, Decimal | None, float | None]:
    """
    Calculate absolute and relative delta.
    absolute_delta = new_value - old_value
    relative_delta = absolute_delta / abs(old_value), if old_value != 0
    If old_value == 0, relative_delta & relative_percent are None.
    """
    d_new = Decimal(str(new_val))
    d_old = Decimal(str(old_val))

    abs_delta = d_new - d_old

    if d_old == Decimal("0"):
        rel_delta = None
        rel_percent = None
    else:
        rel_delta = abs_delta / abs(d_old)
        rel_percent = float(rel_delta * Decimal("100"))

    return abs_delta, rel_delta, rel_percent


def calculate_trend(
    points: list[Decimal | float],
    tolerance: float | Decimal = 0.0,
    min_points: int = 3,
) -> Literal["increasing", "decreasing", "stable", "mixed", "insufficient_data"]:
    """
    Calculate sustained trend over a sequence of time-sorted points.
    Rules:
    - min_points = 3
    - increasing: all adjacent deltas > tolerance
    - decreasing: all adjacent deltas < -tolerance
    - stable: all abs(adjacent deltas) <= tolerance
    - else: mixed
    """
    if len(points) < min_points:
        return "insufficient_data"

    tol = Decimal(str(tolerance))
    dec_points = [Decimal(str(p)) for p in points]
    deltas = [dec_points[i] - dec_points[i - 1] for i in range(1, len(dec_points))]

    if all(d > tol for d in deltas):
        return "increasing"
    if all(d < -tol for d in deltas):
        return "decreasing"
    if all(abs(d) <= tol for d in deltas):
        return "stable"

    return "mixed"
