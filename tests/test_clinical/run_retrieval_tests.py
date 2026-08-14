from src.agents.retrieval.fusion import BaselineWeightedReranker

class MockEvidence:
    def __init__(self, fact_type, statement, verification_status="verified"):
        self.fact_type = fact_type
        self.normalized_value = {"statement": statement}
        self.verification_status = verification_status

def run_tests():
    reranker = BaselineWeightedReranker()
    
    candidates = [
        MockEvidence("diagnosis", "Đái tháo đường típ 2"),
        MockEvidence("medication", "Metformin 1000mg"),
        MockEvidence("lab", "HbA1c 7.8%"),
        MockEvidence("note", "Hạ đường huyết nhẹ")
    ]

    results1 = reranker.rerank("Bệnh nhân mắc bệnh gì?", candidates)
    assert len(results1) > 0, "Should not drop evidence for 'Bệnh nhân mắc bệnh gì?'"

    results2 = reranker.rerank("Thuốc hiện tại là gì?", candidates)
    assert len(results2) > 0, "Should not drop evidence for 'Thuốc hiện tại là gì?'"

    results3 = reranker.rerank("HbA1c gần nhất?", candidates)
    assert len(results3) > 0, "Should not drop evidence for 'HbA1c gần nhất?'"
    
    results4 = reranker.rerank("Tình trạng hiện tại có gì đáng chú ý?", candidates)
    assert len(results4) > 0, "Should not drop evidence for 'Tình trạng hiện tại có gì đáng chú ý?'"
    
    print("All tests passed! Evidence is no longer dropped purely due to lexical mismatch.")

if __name__ == "__main__":
    run_tests()
