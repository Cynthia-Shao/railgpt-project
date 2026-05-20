from __future__ import annotations

from railgpt_core.models.retrieval import RetrievedChunk
from railgpt_core.models.rules import RulePriority


def priority_bonus_norm(chunk: RetrievedChunk) -> float:
    """归一化优先级加权：强规则/场景 = 0.3，普通规则 = 0.1"""
    if chunk.priority in (RulePriority.HARD, RulePriority.SCENARIO):
        return 0.3
    return 0.1


def combined_score(
    keyword_norm: float,
    embedding_sim: float,
    chunk: RetrievedChunk,
) -> float:
    """关键词(0-1) + 语义相似度(0-1) + 优先级(0-1)"""
    return keyword_norm + embedding_sim + priority_bonus_norm(chunk)
