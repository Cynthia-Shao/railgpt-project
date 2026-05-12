from __future__ import annotations

from railgpt_core.models.retrieval import RetrievedChunk
from railgpt_core.models.rules import RuleDocument


def chunk_rule_document(document: RuleDocument) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id=f"{document.rule_id}-chunk-0",
            rule_id=document.rule_id,
            title=document.title,
            content=document.content,
            source_path=document.source_path,
            priority=document.priority,
            must_follow=document.must_follow,
            chunk_index=0,
        )
    ]
