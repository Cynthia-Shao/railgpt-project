from __future__ import annotations

from railgpt_core.models.retrieval import RetrievedChunk
from railgpt_core.models.rules import RulePriority
from railgpt_core.retrieval.keyword import keyword_score


def priority_bonus(chunk: RetrievedChunk) -> float:
    if chunk.priority == RulePriority.HARD:
        return 2.0
    return 0.5


def hybrid_score(query: str, chunk: RetrievedChunk) -> float:
    return keyword_score(query, chunk) + priority_bonus(chunk)
