from __future__ import annotations

from railgpt_core.knowledge import RuleKnowledgeRegistry
from railgpt_core.models.retrieval import RetrievedChunk
from railgpt_core.retrieval.chunking import chunk_rule_document
from railgpt_core.retrieval.hybrid import hybrid_score
from railgpt_core.retrieval.keyword import keyword_score


class RuleRetrievalService:
    def __init__(self, base_dir: str = "data/rules") -> None:
        self.registry = RuleKnowledgeRegistry(base_dir=base_dir)
        self._chunks: list[RetrievedChunk] = []

    def load(self) -> None:
        self.registry.load()
        chunks: list[RetrievedChunk] = []
        for document in self.registry.documents:
            chunks.extend(chunk_rule_document(document))
        self._chunks = chunks

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        ranked: list[RetrievedChunk] = []
        for chunk in self._chunks:
            lexical_score = keyword_score(query, chunk)
            if lexical_score <= 0:
                continue

            score = hybrid_score(query, chunk)
            ranked.append(chunk.model_copy(update={"score": score}))

        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:top_k]
