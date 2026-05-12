from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class RailGPTSettings:
    llm_base_url: str
    llm_model: str
    llm_api_key: str
    llm_timeout_seconds: int
    rules_base_dir: str
    embedding_model: str

    @classmethod
    def from_env(cls) -> "RailGPTSettings":
        return cls(
            llm_base_url=os.getenv("RAILGPT_LLM_BASE_URL", "http://127.0.0.1:8000/v1"),
            llm_model=os.getenv("RAILGPT_LLM_MODEL", "qwen2.5:latest"),
            llm_api_key=os.getenv("RAILGPT_LLM_API_KEY", "ollama"),
            llm_timeout_seconds=int(os.getenv("RAILGPT_LLM_TIMEOUT_SECONDS", "300")),
            rules_base_dir=os.getenv("RAILGPT_RULES_BASE_DIR", "data/rules"),
            embedding_model=os.getenv("RAILGPT_EMBEDDING_MODEL", "nomic-embed-text:latest"),
        )
