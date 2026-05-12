from __future__ import annotations

import hashlib
import json
from pathlib import Path

import urllib.request as _request
import urllib.error as _error

from railgpt_core.models.retrieval import RetrievedChunk
from railgpt_core.utils.config import RailGPTSettings

CACHE_DIR = Path("data/cache")
HASHES_FILE = CACHE_DIR / "chunk_hashes.json"
EMBEDDINGS_FILE = CACHE_DIR / "chunk_embeddings.json"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class EmbeddingClient:
    def __init__(self, settings: RailGPTSettings | None = None) -> None:
        self.settings = settings or RailGPTSettings.from_env()

    def embed(self, texts: list[str]) -> list[list[float]]:
        url = f"{self.settings.llm_base_url.rstrip('/').replace('/v1', '')}/api/embed"
        payload = json.dumps({
            "model": self.settings.embedding_model,
            "input": texts,
        }).encode("utf-8")

        req = _request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with _request.urlopen(req, timeout=self.settings.llm_timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data.get("embeddings", [])
        except _error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Embedding failed HTTP {exc.code}: {detail}") from exc


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def compute_or_load_embeddings(
    chunks: list[RetrievedChunk],
    client: EmbeddingClient,
    batch_size: int = 32,
) -> dict[str, list[float]]:
    current_hashes: dict[str, str] = {}
    for c in chunks:
        current_hashes[c.chunk_id] = _content_hash(c.content)

    # 尝试从缓存加载
    cached_hashes = _load_json(HASHES_FILE)
    cached_embeddings = _load_json(EMBEDDINGS_FILE)
    if cached_hashes and cached_embeddings and cached_hashes == current_hashes:
        return {k: v for k, v in cached_embeddings.items() if isinstance(v, list)}

    # 缓存失效，重新计算
    print(f"Computing embeddings for {len(chunks)} chunks (this may take a few minutes)...")
    embeddings: dict[str, list[float]] = {}
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.content for c in batch]
        try:
            vecs = client.embed(texts)
        except Exception as exc:
            print(f"  Embedding batch {i // batch_size + 1} failed: {exc}")
            # 降级：该批次用零向量
            vecs = [[0.0] * 1024] * len(texts)

        for chunk, vec in zip(batch, vecs):
            embeddings[chunk.chunk_id] = vec

        pct = min(100, (i + len(batch)) * 100 // len(chunks))
        print(f"  {pct}% ({min(i + len(batch), len(chunks))}/{len(chunks)})")

    # 写缓存
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    HASHES_FILE.write_text(json.dumps(current_hashes, ensure_ascii=False), encoding="utf-8")
    EMBEDDINGS_FILE.write_text(json.dumps(embeddings, ensure_ascii=False), encoding="utf-8")
    print("Embeddings cached to disk.")

    return embeddings


def embedding_similarity(
    query_vec: list[float],
    chunk_vec: list[float],
) -> float:
    return _cosine_similarity(query_vec, chunk_vec)


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
