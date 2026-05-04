from __future__ import annotations

import re

from railgpt_core.models.retrieval import RetrievedChunk


def _expand_cjk_token(token: str) -> list[str]:
    if len(token) <= 1:
        return [token]

    expanded = [token]
    expanded.extend(char for char in token if "\u4e00" <= char <= "\u9fff")

    if all("\u4e00" <= char <= "\u9fff" for char in token):
        expanded.extend(token[index:index + 2] for index in range(len(token) - 1))

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(expanded))


def tokenize(text: str) -> list[str]:
    raw_tokens = [token for token in re.split(r"[\s,，。；：:、()\[\]{}]+", text.lower()) if token]
    tokens: list[str] = []
    for token in raw_tokens:
        tokens.extend(_expand_cjk_token(token))
    return list(dict.fromkeys(tokens))


def keyword_score(query: str, chunk: RetrievedChunk) -> float:
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0

    content = chunk.content.lower()
    score = 0.0
    for token in query_tokens:
        if token in content:
            score += 1.0
    return score
