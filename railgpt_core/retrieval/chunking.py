from __future__ import annotations

from railgpt_core.models.retrieval import RetrievedChunk
from railgpt_core.models.rules import RuleDocument


def chunk_rule_document(document: RuleDocument) -> list[RetrievedChunk]:
    paragraphs = [part.strip() for part in document.content.split("\n\n") if part.strip()]
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
