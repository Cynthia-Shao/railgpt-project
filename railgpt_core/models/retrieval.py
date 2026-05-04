from __future__ import annotations

from pydantic import BaseModel, Field

from railgpt_core.models.rules import RulePriority


class RetrievedChunk(BaseModel):
    chunk_id: str = Field(..., description="Unique chunk identifier.")
    rule_id: str = Field(..., description="Source rule identifier.")
    title: str = Field(..., description="Source rule title.")
    content: str = Field(..., description="Chunk text content.")
    source_path: str = Field(..., description="Original file path.")
    priority: RulePriority = Field(..., description="Rule priority.")
    must_follow: bool = Field(..., description="Whether the source rule is mandatory.")
    chunk_index: int = Field(..., description="Chunk position in the source document.")
    score: float = Field(0.0, description="Retrieval score.")
