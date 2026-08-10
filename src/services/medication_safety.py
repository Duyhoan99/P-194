"""Medication safety service enforcing drug interaction rules strictly via configuration."""

import json
from pathlib import Path
import uuid
from typing import Any
from src.clinical.canonical import DrugInteractionFlag, Citation, DocumentCitation, FhirCitation, RecordCitation


def canonical_pair(ingredient_a: str, ingredient_b: str) -> tuple[str, str]:
    """Return a symmetric, lowercased pair key."""
    a, b = ingredient_a.strip().lower(), ingredient_b.strip().lower()
    return (a, b) if a <= b else (b, a)


class MedicationSafetyService:
    """Evaluates medication lists against deterministic interaction rules."""

    def __init__(self, config_path: str | Path | None = None):
        if config_path is None:
            config_path = Path(__file__).parents[2] / "configs" / "drug_interactions" / "drug_interactions.json"
        
        self.rules: list[dict[str, Any]] = []
        self.version = "1.0.0"
        self.load_rules(config_path)

    def load_rules(self, path: str | Path) -> None:
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.version = data.get("version", "1.0.0")
                self.rules = data.get("rules", [])

    def find_drug_interactions(
        self,
        medication_ingredients: list[tuple[str, Citation | None]],
    ) -> list[DrugInteractionFlag]:
        """
        Match current medication pairs against active rules.
        medication_ingredients: list of (ingredient_name, citation)
        """
        flags: list[DrugInteractionFlag] = []
        if len(medication_ingredients) < 2:
            return flags

        # Map normalized pairs to rules
        rule_map = {}
        for r in self.rules:
            pair = r.get("pair", [])
            if len(pair) == 2:
                key = canonical_pair(pair[0], pair[1])
                rule_map[key] = r

        # Check all unique pairs of current meds
        seen_flags = set()
        n = len(medication_ingredients)
        for i in range(n):
            for j in range(i + 1, n):
                ing_a, cit_a = medication_ingredients[i]
                ing_b, cit_b = medication_ingredients[j]
                pair_key = canonical_pair(ing_a, ing_b)

                if pair_key in rule_map and pair_key not in seen_flags:
                    seen_flags.add(pair_key)
                    r = rule_map[pair_key]
                    cits: list[Citation] = []
                    if cit_a:
                        cits.append(cit_a)
                    if cit_b:
                        cits.append(cit_b)

                    flags.append(
                        DrugInteractionFlag(
                            flag_id=f"dif_{uuid.uuid4().hex[:8]}",
                            ingredients=[pair_key[0], pair_key[1]],
                            severity=r.get("severity", "moderate"),
                            description=r.get("description", ""),
                            rule_source=r.get("rule_source", "Clinical Drug Interaction Database"),
                            rule_version=r.get("rule_version", self.version),
                            status="open",
                            citations=cits,
                        )
                    )

        return flags
