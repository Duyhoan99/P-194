from unittest import mock

from src.agents.contracts import AgentRequest, EvidenceItem
from src.agents.evidence import ScopedEvidence, retrieve_evidence
from src.agents.policy import classify_request
from src.agents.retrieval.router import DomainNeed, RetrievalPlan


def _mock_req(q: str):
    return AgentRequest(
        tenant_id="t1", patient_id="p1", request_id="r1",
        task_type="ask_chart", question=q,
        user_id="u1", data_watermark="w1", profile_versions=[],
        approved_memory={}, structured_facts=[], note_evidence=[]
    )


def test_review_generation_is_always_a_grounded_summary():
    request = AgentRequest(
        tenant_id="t1", patient_id="p1", request_id="review-request",
        task_type="review_generation", question=None,
        user_id="u1", data_watermark="w1", profile_versions=[],
        approved_memory=None, structured_facts=[], note_evidence=[]
    )
    with mock.patch(
        "src.agents.policy.QueryPlanner.plan",
        side_effect=AssertionError("review generation must not use the chat planner"),
    ):
        plan = classify_request(request)

    assert plan["task_type"] == "summary"
    assert plan["retrieval_required"] is True
    assert plan["needs"] == [{
        "domain": "all",
        "entity": None,
        "temporal": {
            "intent": "none",
            "start_time": None,
            "end_time": None,
            "relative_months": None,
        },
    }]

def test_planner_conversational():
    req = _mock_req("Xin chào")
    plan = classify_request(req)
    assert isinstance(plan, dict)
    assert plan["task_type"] == "conversation"
    assert plan["retrieval_required"] is False

def test_planner_summary():
    req = _mock_req("Tóm tắt cho tôi")
    plan = classify_request(req)
    assert isinstance(plan, dict)
    assert plan["task_type"] == "summary"
    assert plan["retrieval_required"] is True

def test_planner_temporal_fast_path():
    req = _mock_req("HbA1c gần nhất?")
    plan = classify_request(req)
    assert plan["task_type"] == "clinical_question"
    assert any(n["temporal"]["intent"] == "latest" for n in plan["needs"])

@mock.patch("src.agents.retrieval.router.QueryPlanner._llm_plan")
def test_planner_ambiguous_llm(mock_llm):
    # Mock the LLM returning a diagnosis plan
    mock_llm.return_value = RetrievalPlan(
        task_type="clinical_question",
        needs=[DomainNeed(domain="diagnosis")],
        use_structured=True, use_semantic=True, use_lexical=True, retrieval_required=True
    )
    req = _mock_req("Bệnh nhân có đau ngực không?")
    plan = classify_request(req)
    assert plan["task_type"] == "clinical_question"
    assert plan["needs"][0]["domain"] == "diagnosis"
    mock_llm.assert_called_once()

def test_plan_validator_invalid_domain():
    # Bypass LLM and directly test validator
    from src.agents.retrieval.router import PlanValidator
    validator = PlanValidator()
    # Malicious plan with invalid domain
    bad_plan = RetrievalPlan(
        task_type="clinical_question",
        needs=[DomainNeed(domain="all")] # wait, we can't instantiate it with bad literal in Pydantic easily without validation error
    )
    # Actually Pydantic catches Literal errors, so LLM can't even return a bad domain without Pydantic failing.
    # But let's mock it
    bad_plan.needs[0].domain = "hacked_table"
    validated = validator.validate(bad_plan)
    assert validated.needs[0].domain == "all" # falls back

def test_safe_tools_filtering():
    e1 = EvidenceItem(
        evidence_id="e1", fact_type="diagnosis", normalized_value={"statement": "Diabetes"},
        source_value="", source_time=None, verification_status="verified", citations=[]
    )
    e2 = EvidenceItem(
        evidence_id="e2", fact_type="medication", normalized_value={"statement": "Metformin"},
        source_value="", source_time=None, verification_status="verified", citations=[]
    )

    s1 = ScopedEvidence(item=e1, origin="structured", patient_id="p1", tenant_id="t1")
    s2 = ScopedEvidence(item=e2, origin="structured", patient_id="p1", tenant_id="t1")
    packet = [s1, s2]

    plan = {
        "task_type": "clinical_question",
        "needs": [{"domain": "diagnosis"}],
        "retrieval_required": True,
        "use_semantic": False,
        "use_lexical": False
    }

    # Retrieval should only return diagnosis
    with mock.patch("src.agents.retrieval.fusion.BaselineWeightedReranker.rerank") as mock_rerank:
        # We mock reranker to just return candidates directly for testing filter
        mock_rerank.side_effect = lambda q, cands, k: cands
        res = retrieve_evidence(packet, route=plan, question="Mắc bệnh gì?")
        assert len(res) == 1
        assert res[0].item.evidence_id == "e1"

def test_lab_fact_mapping():
    from src.agents.evidence import SafeTool

    e1 = EvidenceItem(
        evidence_id="e1", fact_type="canonical_unit_backend_fact", normalized_value={"statement": "Lab"},
        source_value="", source_time=None, verification_status="verified", citations=[]
    )
    e2 = EvidenceItem(
        evidence_id="e2", fact_type="canonical_diagnosis_fact", normalized_value={"statement": "Diag"},
        source_value="", source_time=None, verification_status="verified", citations=[]
    )
    e3 = EvidenceItem(
        evidence_id="e3", fact_type="canonical_medication_fact", normalized_value={"statement": "Med"},
        source_value="", source_time=None, verification_status="verified", citations=[]
    )

    class MockRetrievalCandidate:
        def __init__(self, item):
            from src.agents.evidence import ScopedEvidence
            self.scoped = ScopedEvidence(item=item, origin="structured", patient_id="p1", tenant_id="t1")

        @property
        def fact_type(self):
            return self.scoped.item.fact_type

    cands = [MockRetrievalCandidate(e1), MockRetrievalCandidate(e2), MockRetrievalCandidate(e3)]
    safe_tool = SafeTool(tenant_id="t1", patient_id="p1", preloaded_packet=cands)

    results = safe_tool.execute("lab")
    assert len(results) == 1
    assert results[0].scoped.item.evidence_id == "e1"

def test_entity_specific_temporal_filtering():
    import datetime
    e_old_lab = EvidenceItem(
        evidence_id="e_old_lab", fact_type="lab", normalized_value={"statement": "HbA1c 7.5"},
        source_value="", source_time=datetime.datetime(2023, 1, 1).isoformat(), verification_status="verified", citations=[]
    )
    e_new_lab = EvidenceItem(
        evidence_id="e_new_lab", fact_type="lab", normalized_value={"statement": "HbA1c 6.5"},
        source_value="", source_time=datetime.datetime(2024, 1, 1).isoformat(), verification_status="verified", citations=[]
    )
    e_new_med = EvidenceItem(
        evidence_id="e_new_med", fact_type="medication", normalized_value={"statement": "Metformin"},
        source_value="", source_time=datetime.datetime(2025, 1, 1).isoformat(), verification_status="verified", citations=[]
    )

    packet = [
        ScopedEvidence(item=e_old_lab, origin="structured", patient_id="p1", tenant_id="t1"),
        ScopedEvidence(item=e_new_lab, origin="structured", patient_id="p1", tenant_id="t1"),
        ScopedEvidence(item=e_new_med, origin="structured", patient_id="p1", tenant_id="t1")
    ]

    plan = {
        "task_type": "clinical_question",
        "needs": [{"domain": "lab", "temporal": {"intent": "latest"}}],
        "retrieval_required": True,
        "use_semantic": False
    }

    with mock.patch("src.agents.retrieval.fusion.BaselineWeightedReranker.rerank") as mock_rerank:
        mock_rerank.side_effect = lambda q, cands, k: cands
        res = retrieve_evidence(packet, route=plan, question="HbA1c mới nhất", limit=1)

        # It should return ONLY e_new_lab, NOT e_new_med (even though med is newer overall)
        assert len(res) == 1
        assert res[0].item.evidence_id == "e_new_lab"

if __name__ == "__main__":
    test_planner_conversational()
    test_planner_summary()
    test_planner_temporal_fast_path()
    test_planner_ambiguous_llm()
    test_plan_validator_invalid_domain()
    test_safe_tools_filtering()
    test_entity_specific_temporal_filtering()
    print("Phase 3 tests passed!")
