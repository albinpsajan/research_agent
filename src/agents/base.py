"""Shared agent infrastructure: evidence discipline, URL sanitising, logging."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from config.logging_config import get_logger
from config.settings import AgentSettings, get_settings
from src.database.repository import Repository
from src.llm.client import LLMClientProtocol
from src.research.registry import ResearchService, SearchBundle

logger = get_logger("agents")


class AgentError(RuntimeError):
    """An agent could not complete its assigned responsibility."""


def normalize_url(url: str) -> str:
    return (url or "").strip().rstrip("/").lower()


def allowed_urls(
    bundle: SearchBundle | None, extra: list[str] | None = None
) -> set[str]:
    """URLs the model is allowed to cite: retrieved evidence plus user input."""
    allowed = {normalize_url(url) for url in (extra or []) if url}
    if bundle:
        allowed.update(normalize_url(r.url) for r in bundle.results if r.url)
    return allowed


def is_valid_provenance(url: str, allowed: set[str]) -> bool:
    """Check if URL is in allowed set or is a verified uploaded document citation."""
    norm = normalize_url(url)
    if norm in allowed:
        return True
    if re.match(r"^\[uploaded document:\s*[^,]+,\s*page\s*\d+\]", norm, re.IGNORECASE):
        return True
    if norm.startswith("doc://"):
        return True
    return False


def sanitize_model_urls(model: BaseModel, allowed: set[str]) -> list[str]:
    """Remove hallucinated URLs from every URL-like field in *model*.

    Returns the removed values so callers can log them.  This is a hard
    evidence-integrity guard, not a prompt suggestion.
    """
    removed: list[str] = []

    def visit(value: Any) -> Any:
        if isinstance(value, BaseModel):
            for field_name in value.__class__.model_fields:
                current = getattr(value, field_name)
                if (
                    field_name in {"url", "source_url", "website", "link"}
                    and isinstance(current, str)
                    and current
                ):
                    if not is_valid_provenance(current, allowed):
                        removed.append(current)
                        setattr(value, field_name, None)
                elif field_name.endswith("_urls") and isinstance(current, list):
                    kept = []
                    for item in current:
                        if isinstance(item, str) and is_valid_provenance(item, allowed):
                            kept.append(item)
                        elif isinstance(item, str):
                            removed.append(item)
                    setattr(value, field_name, kept)
                else:
                    setattr(value, field_name, visit(current))
            return value
        if isinstance(value, list):
            return [visit(item) for item in value]
        if isinstance(value, dict):
            return {key: visit(item) for key, item in value.items()}
        return value

    visit(model)
    if removed:
        logger.warning("Removed %s unverifiable URL(s) from model output", len(removed))
    return removed


def evidence_lines(bundle: SearchBundle, max_items: int = 25) -> str:
    """Numbered evidence for prompts. IDs map back to bundle.results[i-1]."""
    if not bundle.results:
        return "(No external sources were retrieved. Do not invent facts or URLs.)"
    return "\n\n".join(
        result.as_context(index)
        for index, result in enumerate(bundle.results[:max_items], start=1)
    )


def evidence_from_indices(
    bundle: SearchBundle,
    indices: list[int],
    *,
    max_items: int = 5,
):
    """Convert model-cited 1-based evidence indices into validated evidence."""
    from src.models.domain import ProblemEvidence

    selected = []
    seen: set[int] = set()
    for index in indices:
        if not isinstance(index, int) or index < 1 or index > len(bundle.results):
            continue
        if index in seen:
            continue
        seen.add(index)
        result = bundle.results[index - 1]
        selected.append(
            ProblemEvidence(
                description=f"{result.title}: {result.snippet[:400]}",
                source_url=result.url,
                source_type=result.source_type,
                retrieved_at=result.published_at,
                credibility=result.reliability,
            )
        )
        if len(selected) >= max_items:
            break
    return selected


def word_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{4,}", (text or "").lower())}


def similarity(left: str, right: str) -> float:
    """Jaccard similarity with light prefix stemming for duplicate detection."""
    a = {token[:4] for token in word_tokens(left)}
    b = {token[:4] for token in word_tokens(right)}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class BaseAgent:
    """Base class with shared dependencies and bounded prompt helpers."""

    name = "base_agent"
    description = "Base agent"

    def __init__(
        self,
        llm: LLMClientProtocol,
        research: ResearchService,
        repository: Repository,
        settings: AgentSettings | None = None,
    ) -> None:
        self.llm = llm
        self.research = research
        self.repository = repository
        self.settings = settings or get_settings().agent

    def _save(self, session_id: str, result_type: str, payload: BaseModel) -> None:
        self.repository.save_agent_result(
            session_id, self.name, result_type, payload.model_dump(mode="json")
        )

    def _source_urls(self, session_id: str) -> list[str]:
        return [
            row["url"]
            for row in self.repository.get_research_sources(session_id)
            if row.get("url")
        ]
