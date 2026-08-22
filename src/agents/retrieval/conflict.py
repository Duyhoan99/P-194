"""Temporal and concept-aware deterministic conflict detection."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel


class ConflictResult(BaseModel):
    conflict_type: str
    description: str
    item_a: Any
    item_b: Any


def _field(item: Any, name: str, default: Any = None) -> Any:
    if hasattr(item, "item"):
        item = item.item
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def _concept(item: Any) -> str | None:
    fact_type = str(_field(item, "fact_type", "")).casefold()
    if "trend" in fact_type:
        return None  # a longitudinal aggregate is never a competing point observation
    value = _field(item, "normalized_value", {})
    source = _field(item, "source_value", {})
    if isinstance(value, dict):
        explicit = value.get("concept") or value.get("code") or value.get("medication")
        if explicit:
            return str(explicit).casefold().strip()
    if isinstance(source, dict):
        explicit_source = (
            source.get("code") or source.get("condition") or source.get("name")
            or source.get("medication")
        )
        if explicit_source:
            return str(explicit_source).casefold().strip()
    title = str(source.get("title", "")) if isinstance(source, dict) else ""
    if title:
        title = re.sub(r"^(xét nghiệm|lab|thuốc)\s*:\s*", "", title.casefold()).strip()
        if "medication" in fact_type:
            title = re.sub(r"\s+\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ml)\b.*$", "", title).strip()
        return title or None
    return fact_type or None


def _clinical_value(item: Any) -> str:
    source = _field(item, "source_value", {})
    if isinstance(source, dict):
        title = str(source.get("title", "")).strip()
        summary = str(source.get("summary", "")).strip()
        if title or summary:
            return f"{title} {summary}".casefold().strip()
    return str(_field(item, "normalized_value", "")).casefold().strip()


def detect_conflicts(evidence_items: list[Any]) -> list[ConflictResult]:
    """Flag only incompatible facts for the same concept and equivalent date."""
    conflicts: list[ConflictResult] = []
    for index, item_a in enumerate(evidence_items):
        concept_a = _concept(item_a)
        time_a = str(_field(item_a, "source_time", "") or "")
        if not concept_a or not time_a:
            continue
        for item_b in evidence_items[index + 1:]:
            concept_b = _concept(item_b)
            time_b = str(_field(item_b, "source_time", "") or "")
            if concept_a != concept_b or not time_b or time_a[:10] != time_b[:10]:
                continue
            value_a, value_b = _clinical_value(item_a), _clinical_value(item_b)
            if not value_a or not value_b or value_a == value_b:
                continue
            conflicts.append(ConflictResult(
                conflict_type="incompatible_values",
                description=f"Incompatible values for {concept_a} on {time_a[:10]}: {value_a} vs {value_b}",
                item_a=item_a,
                item_b=item_b,
            ))
    return conflicts
