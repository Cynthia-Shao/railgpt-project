from railgpt_core.llm.prompts import build_dispatch_system_prompt, build_rag_user_prompt
from railgpt_core.models.retrieval import RetrievedChunk
from railgpt_core.models.rules import RulePriority


def test_system_prompt_mentions_hard_rules() -> None:
    prompt = build_dispatch_system_prompt()
    assert "强规则" in prompt
    assert "不能建议违反强规则" in prompt


def test_rag_user_prompt_includes_retrieved_chunks() -> None:
    chunk = RetrievedChunk(
        chunk_id="hard-1-chunk-0",
        rule_id="hard-1",
        title="强规则样例",
        content="列车调度必须满足安全间隔要求。",
        source_path="data/rules/hard_rules/sample.md",
        priority=RulePriority.HARD,
        must_follow=True,
        chunk_index=0,
    )
    prompt = build_rag_user_prompt("如何调整发车顺序？", [chunk])
    assert "如何调整发车顺序" in prompt
    assert "强规则样例" in prompt
    assert "安全间隔要求" in prompt
