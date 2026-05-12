from __future__ import annotations

from pathlib import Path

from railgpt_core.models.rules import RuleDocument, RulePriority
from railgpt_core.utils.text import normalize_text, read_text_file


SUPPORTED_RULE_EXTENSIONS = {".md", ".txt", ".json"}


def _build_rule_id(base_dir: Path, file_path: Path, priority: RulePriority) -> str:
    relative = file_path.relative_to(base_dir).with_suffix("")
    normalized = "-".join(relative.parts)
    return f"{priority.value}-{normalized}"


def _iter_rule_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []

    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_RULE_EXTENSIONS
    )


def load_rule_documents(base_dir: str | Path = "data/rules") -> list[RuleDocument]:
    base_path = Path(base_dir)
    hard_dir = base_path / "hard_rules"
    soft_dir = base_path / "soft_rules"
    scenario_dir = base_path / "scenarios"

    documents: list[RuleDocument] = []

    for priority, directory in (
        (RulePriority.HARD, hard_dir),
        (RulePriority.SOFT, soft_dir),
        (RulePriority.SCENARIO, scenario_dir),
    ):
        for file_path in _iter_rule_files(directory):
            content = normalize_text(read_text_file(file_path))
            if not content.strip():
                continue

            documents.append(
                RuleDocument(
                    rule_id=_build_rule_id(base_path, file_path, priority),
                    title=file_path.stem,
                    content=content,
                    source_path=str(file_path),
                    priority=priority,
                    must_follow=(priority in (RulePriority.HARD, RulePriority.SCENARIO)),
                )
            )

    return documents
