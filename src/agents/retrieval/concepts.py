"""Central clinical concept normalization shared by planning and retrieval."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True)
class ClinicalConcept:
    canonical: str
    domain: str
    query_aliases: tuple[str, ...]
    evidence_aliases: tuple[str, ...]


def fold(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).casefold())
    folded = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(folded.translate(str.maketrans({"đ": "d"})).split())


CONCEPTS = (
    ClinicalConcept("HbA1c", "lab", ("hba1c", "hemoglobin a1c"), ("hba1c", "hemoglobin a1c")),
    ClinicalConcept("Glucose", "lab", ("glucose", "duong huyet", "duong mau"), ("glucose", "duong huyet", "duong mau")),
    ClinicalConcept("Creatinine", "lab", ("creatinine", "creatinin"), ("creatinine", "creatinin")),
    ClinicalConcept("eGFR", "lab", ("egfr", "do loc cau than"), ("egfr", "do loc cau than")),
    ClinicalConcept(
        "RenalFunction", "lab",
        ("chuc nang than", "renal function", "kidney function"),
        ("creatinine", "creatinin", "egfr", "do loc cau than"),
    ),
    ClinicalConcept("Metformin", "medication", ("metformin",), ("metformin",)),
    ClinicalConcept("Amlodipine", "medication", ("amlodipine",), ("amlodipine",)),
    ClinicalConcept(
        "Adherence", "medication",
        ("adherence", "tuan thu", "quen thuoc", "quen uong", "hay quen"),
        ("tuan thu", "quen", "uong thuoc", "adherence", "compliance"),
    ),
)


def resolve_concept(question: str) -> ClinicalConcept | None:
    normalized = fold(question)
    return next(
        (concept for concept in CONCEPTS if any(alias in normalized for alias in concept.query_aliases)),
        None,
    )


def get_concept(canonical: str) -> ClinicalConcept | None:
    normalized = fold(canonical)
    return next((concept for concept in CONCEPTS if fold(concept.canonical) == normalized), None)
