from railgpt_core.retrieval import RuleRetrievalService


def test_rule_retrieval_loads_chunks() -> None:
    service = RuleRetrievalService()
    service.load()
    assert service._chunks


def test_rule_retrieval_returns_results() -> None:
    service = RuleRetrievalService()
    service.load()
    results = service.search("调度计划 安全", top_k=3)
    assert len(results) <= 3


def test_hard_rules_are_present_in_ranked_results() -> None:
    service = RuleRetrievalService()
    service.load()
    results = service.search("调度", top_k=10)
    assert results
    assert any(item.must_follow for item in results)
