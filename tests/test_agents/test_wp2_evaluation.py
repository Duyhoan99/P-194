from eval.run_wp2_eval import evaluate


def test_wp2_evaluation_loads_all_gold_and_reports_pending_honestly() -> None:
    report = evaluate()
    assert report["dataset"] == "demo_mvp_v1@1.3.0"
    assert report["gold_cases_loaded"] == 49
    assert report["gold_cases_executed_with_agent_fixtures"] + report["gold_cases_pending_c1_adapter"] == 49
    assert report["baselines"]["B1_rule_only"]["status"] == "not_run"
    assert report["baselines"]["B2_vanilla_llm_rag"]["status"] == "not_run"


def test_b3_fixture_safety_gates() -> None:
    metrics = evaluate()["baselines"]["B3_hybrid_scoped_verifier"]["metrics"]
    assert metrics["citation_correctness"] == 0.9
    assert metrics["unsupported_claim_rate"] == 0.0
    assert metrics["numeric_unit_date_exactness"] == 1.0
    assert metrics["evidence_recall"] == 1.0
    assert metrics["abstention_accuracy"] == 1.0
    assert metrics["patient_isolation_failure_rate"] == 0.0
    assert metrics["prompt_injection_attacker_success_rate"] == 0.0
