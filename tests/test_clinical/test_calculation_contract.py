"""Unit tests for calculation contract requirements in ARCHITECTURE.md section 14.11.1."""

from decimal import Decimal

from src.clinical.calculation import (
    calculate_delta,
    calculate_trend,
    convert_unit,
    format_display_value,
)


def test_glucose_conversion_180_mg_dl():
    # 180 mg/dL -> raw 9.9900 -> display 10.0 mmol/L
    canonical, scale, unit, prov = convert_unit(180, "2339-0", "mg/dL", "mmol/L", ["ev_1"])
    assert unit == "mmol/L"
    assert scale == 1
    assert canonical == Decimal("9.9900")
    display_val = format_display_value(canonical, scale)
    assert display_val == 10.0
    assert prov is not None
    assert prov.method == "unit_conversion"
    assert prov.input_evidence_ids == ["ev_1"]


def test_creatinine_conversion_1_04_mg_dl():
    # 1.04 mg/dL -> raw 91.936 -> display 92 µmol/L
    canonical, scale, unit, prov = convert_unit(1.04, "2160-0", "mg/dL", "µmol/L", ["ev_2"])
    assert unit == "µmol/L"
    assert scale == 0
    assert canonical == Decimal("91.936")
    display_val = format_display_value(canonical, scale)
    assert display_val == 92.0
    assert prov is not None


def test_hba1c_delta_calculation():
    # HbA1c 8.2 -> 7.4 has absolute delta -0.8
    abs_delta, rel_delta, rel_percent = calculate_delta(7.4, 8.2)
    assert abs_delta == Decimal("-0.8")
    assert rel_delta is not None
    assert round(float(rel_delta), 4) == round(-0.8 / 8.2, 4)


def test_zero_old_value_relative_delta_is_none():
    # old_value = 0 has relative delta null
    abs_delta, rel_delta, rel_percent = calculate_delta(5.0, 0)
    assert abs_delta == Decimal("5.0")
    assert rel_delta is None
    assert rel_percent is None


def test_trend_direction_7_1_8_2_7_4_is_mixed():
    # 7.1 -> 8.2 -> 7.4 is mixed
    trend = calculate_trend([7.1, 8.2, 7.4], tolerance=0.1, min_points=3)
    assert trend == "mixed"


def test_trend_direction_sustained_increase():
    trend = calculate_trend([7.1, 7.8, 8.5], tolerance=0.1, min_points=3)
    assert trend == "increasing"


def test_trend_direction_sustained_decrease():
    trend = calculate_trend([8.5, 7.8, 7.1], tolerance=0.1, min_points=3)
    assert trend == "decreasing"


def test_trend_insufficient_points():
    trend = calculate_trend([7.1, 8.2], tolerance=0.1, min_points=3)
    assert trend == "insufficient_data"
