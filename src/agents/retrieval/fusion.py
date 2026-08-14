from typing import Protocol, Any
import re

def _get_terms(query: str) -> set[str]:
    stopwords = {"bệnh", "có", "cho", "của", "được", "kết", "quả", "không", "là", "như", "nào", "nhiêu", "thế", "the", "patient", "what", "bao"}
    return {
        token for token in re.findall(r"[\w]+", query.casefold(), flags=re.UNICODE)
        if len(token) > 2 and token not in stopwords
    }

class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[Any], k: int = 10) -> list[Any]:
        ...

class BaselineWeightedReranker:
    """
    Deterministic weighted score fusion baseline:
    - structured relevance
    - semantic similarity (simulated via vector score if present)
    - lexical score
    - temporal relevance (implied by pre-filtering)
    - source quality
    """
    def rerank(self, query: str, candidates: list[Any], k: int = 10) -> list[Any]:
        scored = []
        q_lower = query.lower()
        terms = _get_terms(query)
        for idx, cand in enumerate(candidates):
            score = 1.0 # default base score
            
            # 1. Source Quality
            status = getattr(cand, "verification_status", None) or (cand.get("verification_status") if isinstance(cand, dict) else None)
            source_quality_score = 1.0 if status == "verified" else 0.0
            
            # 2. Structured Exact Match
            fact_type = getattr(cand, "fact_type", None) or (cand.get("fact_type") if isinstance(cand, dict) else None)
            structured_match_score = 2.0 if fact_type and fact_type.lower() in q_lower else 0.0
            
            # 3. Lexical Score
            lexical_score = 0.0
            norm_val = getattr(cand, "normalized_value", None) or (cand.get("normalized_value") if isinstance(cand, dict) else None)
            if norm_val and isinstance(norm_val, str) and terms and any(term in norm_val.lower() for term in terms):
                lexical_score = 1.5
            elif isinstance(norm_val, dict):
                stmt = norm_val.get("statement", "")
                if stmt and terms and any(term in stmt.lower() for term in terms):
                    lexical_score = 1.5

            # 4. Semantic Score (Placeholder for Phase 2)
            semantic_score = getattr(cand, "semantic_score", 0.0)
            if isinstance(cand, dict) and not semantic_score:
                semantic_score = cand.get("semantic_score", 0.0)

            # 5. Temporal Score (Placeholder, currently temporal is pre-filtered)
            temporal_score = 0.0
            
            # Final continuous score
            total_score = score + source_quality_score + structured_match_score + lexical_score + semantic_score + temporal_score

            # Tie-breaker (preserve original order if scores match)
            scored.append((total_score, -idx, cand))
            
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [cand for _, _, cand in scored[:k]]

