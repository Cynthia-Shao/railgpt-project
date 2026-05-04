from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class RulePriority(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class RuleDocument(BaseModel):
    rule_id: str = Field(..., description="Unique rule document identifier.")
    title: str = Field(..., description="Human-readable rule title.")
    content: str = Field(..., description="Full text content of the rule document.")
    source_path: str = Field(..., description="Original file path.")
    priority: RulePriority = Field(..., description="Rule priority level.")
    must_follow: bool = Field(..., description="Whether the rule is mandatory.")
    tags: list[str] = Field(default_factory=list, description="Optional rule tags.")

    @property
    def source_name(self) -> str:
        return Path(self.source_path).name
