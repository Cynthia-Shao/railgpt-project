from __future__ import annotations

from pathlib import Path

from railgpt_core.knowledge.loader import load_rule_documents
from railgpt_core.models.rules import RuleDocument, RulePriority


class RuleKnowledgeRegistry:
    def __init__(self, base_dir: str | Path = "data/rules") -> None:
        self.base_dir = Path(base_dir)
        self._documents: list[RuleDocument] = []

    def load(self) -> None:
        self._documents = load_rule_documents(self.base_dir)

    @property
    def documents(self) -> list[RuleDocument]:
        return list(self._documents)

    @property
    def hard_rules(self) -> list[RuleDocument]:
        return [doc for doc in self._documents if doc.priority == RulePriority.HARD]

    @property
    def soft_rules(self) -> list[RuleDocument]:
        return [doc for doc in self._documents if doc.priority == RulePriority.SOFT]
