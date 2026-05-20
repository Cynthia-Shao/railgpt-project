from __future__ import annotations

import re

from railgpt_core.models.retrieval import RetrievedChunk


def _expand_cjk_token(token: str) -> list[str]:
    if len(token) <= 1:
        return [token]

    expanded = [token]
    # \u4e0d\u6dfb\u52a0\u5355\u4e2aCJK\u5b57\u7b26\u2014\u2014\u5355\u5b57\u5339\u914d\u8fc7\u4e8e\u5bbd\u6cdb\uff08\u5982"\u8f66"\u5339\u914d\u6240\u6709\u94c1\u8def\u6587\u6863\uff09

    if all("\u4e00" <= char <= "\u9fff" for char in token):
        expanded.extend(token[index:index + 2] for index in range(len(token) - 1))

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
