"""Availability metadata for allow-listed MIMIC-IV SQLite sources."""

from dataclasses import dataclass

HOSPITAL_TABLES = frozenset(
    {
        "patients",
        "admissions",
        "transfers",
        "services",
        "diagnoses_icd",
        "d_icd_diagnoses",
        "procedures_icd",
        "d_icd_procedures",
        "hcpcsevents",
        "d_hcpcs",
        "labevents",
        "d_labitems",
        "microbiologyevents",
    }
)
ICU_TABLES = frozenset(
    {
        "icustays",
        "chartevents",
        "datetimeevents",
        "inputevents",
        "outputevents",
        "procedureevents",
        "d_items",
    }
)
ALLOWED_SOURCE_TABLES = HOSPITAL_TABLES | ICU_TABLES


@dataclass(frozen=True)
class SourceAvailability:
    """The configured clinical tables and modules that are not loaded."""

    available_tables: set[str]
    unavailable_modules: list[str]


def source_availability(tables: set[str]) -> SourceAvailability:
    """Return availability constrained to the repository allow-list."""

    available_tables = tables & ALLOWED_SOURCE_TABLES
    unavailable_modules = [
        module
        for module, module_tables in (("hosp", HOSPITAL_TABLES), ("icu", ICU_TABLES))
        if not available_tables & module_tables
    ]
    return SourceAvailability(available_tables=available_tables, unavailable_modules=unavailable_modules)
