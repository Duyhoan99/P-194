from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from src.clinical.summary_schemas import ClinicalSummaryDraft
from src.config import get_settings


def get_llm() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        temperature=settings.llm_temperature,
    )


def get_structured_llm() -> Runnable:
    """Return the configured LLM constrained to the clinical draft schema."""
    return get_llm().with_structured_output(
        ClinicalSummaryDraft,
        method="json_schema",
        strict=True,
    )
