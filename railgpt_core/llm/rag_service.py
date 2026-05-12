from __future__ import annotations

from railgpt_core.llm.client import OpenAICompatibleLLMClient
from railgpt_core.llm.prompts import build_dispatch_system_prompt, build_rag_user_prompt
from railgpt_core.models.llm import LLMGenerationResult
from railgpt_core.retrieval import RuleRetrievalService
from railgpt_core.utils.config import RailGPTSettings


class RAGDispatchService:
    def __init__(self, settings: RailGPTSettings | None = None) -> None:
        self.settings = settings or RailGPTSettings.from_env()
        self.retrieval_service = RuleRetrievalService(base_dir=self.settings.rules_base_dir)
        self.llm_client = OpenAICompatibleLLMClient(settings=self.settings)

    def load_knowledge(self) -> None:
        self.retrieval_service.load()

    def answer(self, query: str, top_k: int = 3, temperature: float = 0.2) -> LLMGenerationResult:
        retrieved_chunks = self.retrieval_service.search(query, top_k=top_k)
        system_prompt = build_dispatch_system_prompt()
        user_prompt = build_rag_user_prompt(query, retrieved_chunks)
        answer = self.llm_client.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=400,
        )

        return LLMGenerationResult(
            query=query,
            answer=answer,
            model_name=self.settings.llm_model,
            retrieved_chunks=retrieved_chunks,
        )
