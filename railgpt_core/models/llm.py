from __future__ import annotations

from pydantic import BaseModel, Field

from railgpt_core.models.retrieval import RetrievedChunk


class LLMGenerationResult(BaseModel):
    query: str = Field(..., description="Original user query.")
    answer: str = Field(..., description="Generated model answer.")
    model_name: str = Field(..., description="Model used to generate the answer.")
    retrieved_chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Retrieved knowledge chunks used as context.",
    )
