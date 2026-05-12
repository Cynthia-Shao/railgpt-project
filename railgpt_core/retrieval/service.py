from __future__ import annotations

from railgpt_core.knowledge import RuleKnowledgeRegistry
from railgpt_core.models.retrieval import RetrievedChunk
from railgpt_core.retrieval.chunking import chunk_rule_document
from railgpt_core.retrieval.embedding import (
    EmbeddingClient,
    compute_or_load_embeddings,
    embedding_similarity,
)
from railgpt_core.retrieval.hybrid import combined_score
from railgpt_core.retrieval.keyword import keyword_score


class RuleRetrievalService:
    def __init__(self, base_dir: str = "data/rules") -> None:
        self.registry = RuleKnowledgeRegistry(base_dir=base_dir)
        self._chunks: list[RetrievedChunk] = []
        self._embeddings: dict[str, list[float]] = {}
        self._embed_client: EmbeddingClient | None = None

    def load(self) -> None:
        self.registry.load()
        chunks: list[RetrievedChunk] = []
        for document in self.registry.documents:
            chunks.extend(chunk_rule_document(document))
        self._chunks = chunks

        self._embed_client = EmbeddingClient()
        self._embeddings = compute_or_load_embeddings(chunks, self._embed_client)

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        # 第一步：算所有 chunk 的关键词分，找最大值
        keyword_scores: dict[str, float] = {}
        max_kw = 0.0
        for chunk in self._chunks:
            kw = keyword_score(query, chunk)
            keyword_scores[chunk.chunk_id] = kw
            if kw > max_kw:
                max_kw = kw

        # 第二步：嵌入查询向量
        query_vec: list[float] = []
        if self._embed_client is not None:
            try:
                vecs = self._embed_client.embed([query])
                query_vec = vecs[0] if vecs else []
            except Exception:
                pass

        # 第三步：混合评分，过滤关键词分为零的结果
        ranked: list[RetrievedChunk] = []
        for chunk in self._chunks:
            kw = keyword_scores.get(chunk.chunk_id, 0.0)
            if kw <= 0:
                continue

            kw_norm = kw / max(1.0, max_kw)
            emb_sim = 0.0
            if query_vec and chunk.chunk_id in self._embeddings:
                emb_sim = embedding_similarity(query_vec, self._embeddings[chunk.chunk_id])

            score = combined_score(kw_norm, emb_sim, chunk)
            ranked.append(chunk.model_copy(update={"score": score}))

        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:top_k]
