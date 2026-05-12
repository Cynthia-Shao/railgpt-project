from __future__ import annotations

from railgpt_core.models.retrieval import RetrievedChunk
from railgpt_core.models.rules import RuleDocument

MAX_CHUNK_CHARS = 1000


def chunk_rule_document(document: RuleDocument) -> list[RetrievedChunk]:
    if len(document.content) <= MAX_CHUNK_CHARS:
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

    paragraphs = [p.strip() for p in document.content.split("\n\n") if p.strip()]
    chunks: list[RetrievedChunk] = []
    for index, paragraph in enumerate(paragraphs):
        chunks.append(
            RetrievedChunk(
                chunk_id=f"{document.rule_id}-chunk-{index}",
                rule_id=document.rule_id,
                title=document.title,
                content=paragraph,
                source_path=document.source_path,
                priority=document.priority,
                must_follow=document.must_follow,
                chunk_index=index,
            )
        )
    return chunks
