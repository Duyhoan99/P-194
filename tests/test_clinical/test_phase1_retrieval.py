from src.agents.retrieval.fusion import BaselineWeightedReranker


class MockEvidence:
    def __init__(self, fact_type, statement, verification_status="verified"):
        self.fact_type = fact_type
        self.normalized_value = {"statement": statement}
        self.verification_status = verification_status

def test_paraphrased_queries_do_not_drop_evidence():
    reranker = BaselineWeightedReranker()

    candidates = [
        MockEvidence("diagnosis", "Đái tháo đường típ 2"),
        MockEvidence("medication", "Metformin 1000mg"),
        MockEvidence("lab", "HbA1c 7.8%"),
        MockEvidence("note", "Hạ đường huyết nhẹ")
    ]

    # 1. "Bệnh nhân mắc bệnh gì?" (Paraphrase of "diagnosis" or "Đái tháo đường")
    # Expected: should not return empty. It might just rank everything by base score + quality,
    # but the key is that it doesn't DROP the evidence anymore.
    results1 = reranker.rerank("Bệnh nhân mắc bệnh gì?", candidates)
    assert len(results1) > 0, "Should not drop evidence for 'Bệnh nhân mắc bệnh gì?'"

    # 2. "Thuốc hiện tại là gì?" (Has "thuốc", matches "medication" if lexical matches, but even if no lexical match, shouldn't drop)
    results2 = reranker.rerank("Thuốc hiện tại là gì?", candidates)
    assert len(results2) > 0, "Should not drop evidence for 'Thuốc hiện tại là gì?'"

    # 3. "HbA1c gần nhất?"
    results3 = reranker.rerank("HbA1c gần nhất?", candidates)
    assert len(results3) > 0, "Should not drop evidence for 'HbA1c gần nhất?'"

    # 4. "Tình trạng hiện tại có gì đáng chú ý?" (Paraphrase for notes/conditions)
    results4 = reranker.rerank("Tình trạng hiện tại có gì đáng chú ý?", candidates)
    assert len(results4) > 0, "Should not drop evidence for 'Tình trạng hiện tại có gì đáng chú ý?'"

    print("All tests passed! Evidence is no longer dropped purely due to lexical mismatch.")
