"""Centralized, validated configuration for HackathonIQ.

Configuration precedence (lowest to highest):
1. Built-in defaults
2. ``data/user_settings.json`` (written by the Settings UI)
3. Environment variables / ``.env``

The application never silently allocates the storage budget; the budget is
only a guard-rail used before downloads.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

_BASE_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _BASE_DIR / "data"
_USER_SETTINGS_PATH = _DATA_DIR / "user_settings.json"


def _load_dotenv(path: Path = _BASE_DIR / ".env") -> None:
    """Minimal .env loader (no extra dependency, never overrides real env)."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_user_settings() -> dict[str, Any]:
    """Read UI-managed overrides. Corrupt files are ignored, not fatal."""
    if not _USER_SETTINGS_PATH.exists():
        return {}
    try:
        payload = json.loads(_USER_SETTINGS_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_user_settings(overrides: dict[str, Any]) -> Path:
    """Persist UI-managed overrides atomically and reset the cached settings."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = _load_user_settings()
    existing.update(overrides)
    tmp = _USER_SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    tmp.replace(_USER_SETTINGS_PATH)
    reset_settings()
    return _USER_SETTINGS_PATH


class OllamaSettings(BaseModel):
    """Ollama LLM connection settings (one shared local model)."""

    base_url: str = Field(default="http://localhost:11434")
    model: str = Field(default="qwen2.5:7b")
    fallback_model: str = Field(default="qwen2.5:3b")
    timeout: int = Field(default=300, ge=10)
    num_ctx: int = Field(default=8192, ge=1024)
    num_predict: int = Field(default=2048, ge=128)
    temperature: float = Field(default=0.35, ge=0.0, le=1.5)
    max_json_retries: int = Field(default=2, ge=0, le=5)

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


class StorageSettings(BaseModel):
    """Disk-budget and directory settings.

    ``budget_gb`` is a guard-rail, never an automatic allocation. 30 GB is
    the recommended starting budget.
    """

    budget_gb: float = Field(default=30.0, gt=0)
    warn_threshold: float = Field(default=0.85, gt=0, le=1.0)
    models_dir: Path = Field(default_factory=lambda: _DATA_DIR / "models")
    cache_dir: Path = Field(default_factory=lambda: _DATA_DIR / "cache")
    reports_dir: Path = Field(default_factory=lambda: _DATA_DIR / "reports")
    logs_dir: Path = Field(default_factory=lambda: _DATA_DIR / "logs")
    db_path: Path = Field(default_factory=lambda: _DATA_DIR / "hackathoniq.db")


class ResearchSettings(BaseModel):
    """Web-research and data-collection settings."""

    max_sources: int = Field(default=60, ge=5, le=500)
    timeout_seconds: int = Field(default=30, ge=5, le=120)
    github_token: str | None = Field(default=None)
    contact_email: str | None = Field(default=None)
    max_retries: int = Field(default=2, ge=0, le=5)
    rate_limit_delay: float = Field(default=1.0, ge=0.0, le=30.0)
    respect_robots_txt: bool = Field(default=True)
    user_agent: str = Field(
        default="HackathonIQ/1.0 (+local research assistant; respectful crawler)"
    )
    cache_ttl_hours: int = Field(default=24, ge=1)
    max_page_bytes: int = Field(default=2_000_000, ge=10_000)
    rss_feeds: list[str] = Field(
        default_factory=lambda: [
            "https://news.mit.edu/rss/topic/artificial-intelligence2",
            "https://www.sciencedaily.com/rss/top/science.xml",
            "https://hnrss.org/frontpage?points=100",
        ]
    )


class AgentSettings(BaseModel):
    """Multi-agent research and bounded-debate settings."""

    max_domains: int = Field(default=8, ge=3, le=20)
    problems_per_domain: int = Field(default=2, ge=1, le=5)
    max_total_problems: int = Field(default=20, ge=3, le=60)
    max_finalists: int = Field(default=5, ge=2, le=10)
    max_debate_rounds: int = Field(default=3, ge=1, le=5)
    min_confidence_threshold: float = Field(default=0.55, ge=0, le=1)
    research_results_per_query: int = Field(default=8, ge=3, le=20)
    default_hackathon_hours: float = Field(default=36.0, gt=0)


class EvaluationSettings(BaseModel):
    """Scoring-weight settings (must total 100)."""

    problem_significance: int = Field(default=15, ge=0)
    originality: int = Field(default=15, ge=0)
    technical_feasibility: int = Field(default=15, ge=0)
    theme_relevance: int = Field(default=15, ge=0)
    organizer_alignment: int = Field(default=10, ge=0)
    innovation: int = Field(default=10, ge=0)
    implementation_deadline: int = Field(default=10, ge=0)
    demonstration_appeal: int = Field(default=10, ge=0)

    @property
    def total_weight(self) -> int:
        return (
            self.problem_significance
            + self.originality
            + self.technical_feasibility
            + self.theme_relevance
            + self.organizer_alignment
            + self.innovation
            + self.implementation_deadline
            + self.demonstration_appeal
        )

    def as_weights(self) -> dict[str, int]:
        return {
            "Real-world problem significance": self.problem_significance,
            "Originality and differentiation": self.originality,
            "Technical feasibility": self.technical_feasibility,
            "Hackathon theme relevance": self.theme_relevance,
            "Organizer and sponsor alignment": self.organizer_alignment,
            "Innovation and future potential": self.innovation,
            "Implementation within deadline": self.implementation_deadline,
            "Demonstration and judging appeal": self.demonstration_appeal,
        }

    @model_validator(mode="after")
    def _weights_total_100(self) -> EvaluationSettings:
        if self.total_weight != 100:
            raise ValueError(
                f"Evaluation weights must total 100, got {self.total_weight}"
            )
        return self


class ContinuousIntelligenceSettings(BaseModel):
    """Background intelligence-refresh settings."""

    refresh_interval_hours: int = Field(default=24, ge=1, le=720)
    max_items_per_source: int = Field(default=50, ge=5, le=500)
    enabled: bool = Field(default=True)
    stale_after_days: int = Field(default=30, ge=1)
    scheduler_tick_seconds: int = Field(default=300, ge=30)


class LoggingSettings(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO")
    log_file: Path = Field(
        default_factory=lambda: _DATA_DIR / "logs" / "hackathoniq.log"
    )
    format: str = Field(default="%(asctime)s | %(name)s | %(levelname)s | %(message)s")


class Settings(BaseModel):
    """Root settings that aggregates every sub-section."""

    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    research: ResearchSettings = Field(default_factory=ResearchSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)
    continuous_intelligence: ContinuousIntelligenceSettings = Field(
        default_factory=ContinuousIntelligenceSettings
    )
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @property
    def db_path(self) -> Path:
        return Path(self.storage.db_path)

    @classmethod
    def load(cls) -> Settings:
        """Build settings from defaults, user overrides and environment."""
        _load_dotenv()
        user = _load_user_settings()
        user_ollama = (
            user.get("ollama", {}) if isinstance(user.get("ollama"), dict) else {}
        )
        user_storage = (
            user.get("storage", {}) if isinstance(user.get("storage"), dict) else {}
        )
        user_research = (
            user.get("research", {}) if isinstance(user.get("research"), dict) else {}
        )
        user_ci = (
            user.get("continuous_intelligence", {})
            if isinstance(user.get("continuous_intelligence"), dict)
            else {}
        )
        user_agent = (
            user.get("agent", {}) if isinstance(user.get("agent"), dict) else {}
        )

        ollama = OllamaSettings(
            base_url=os.getenv(
                "OLLAMA_BASE_URL",
                user_ollama.get("base_url", "http://localhost:11434"),
            ),
            model=os.getenv("OLLAMA_MODEL", user_ollama.get("model", "qwen2.5:7b")),
            fallback_model=os.getenv(
                "OLLAMA_FALLBACK_MODEL",
                user_ollama.get("fallback_model", "qwen2.5:3b"),
            ),
            num_ctx=int(
                os.getenv("OLLAMA_NUM_CTX", str(user_ollama.get("num_ctx", 8192)))
            ),
            num_predict=int(
                os.getenv(
                    "OLLAMA_NUM_PREDICT", str(user_ollama.get("num_predict", 2048))
                )
            ),
            timeout=int(
                os.getenv("OLLAMA_TIMEOUT", str(user_ollama.get("timeout", 300)))
            ),
            temperature=float(
                os.getenv(
                    "OLLAMA_TEMPERATURE",
                    str(user_ollama.get("temperature", 0.35)),
                )
            ),
        )
        storage = StorageSettings(
            budget_gb=float(
                os.getenv("STORAGE_BUDGET_GB", str(user_storage.get("budget_gb", 30)))
            ),
            warn_threshold=float(
                os.getenv(
                    "STORAGE_WARN_THRESHOLD",
                    str(user_storage.get("warn_threshold", 0.85)),
                )
            ),
        )
        research = ResearchSettings(
            max_sources=int(
                os.getenv(
                    "MAX_RESEARCH_SOURCES",
                    str(user_research.get("max_sources", 60)),
                )
            ),
            timeout_seconds=int(
                os.getenv(
                    "RESEARCH_TIMEOUT_SECONDS",
                    str(user_research.get("timeout_seconds", 30)),
                )
            ),
            github_token=os.getenv("GITHUB_TOKEN")
            or user_research.get("github_token")
            or None,
            contact_email=os.getenv("RESEARCH_CONTACT_EMAIL")
            or user_research.get("contact_email")
            or None,
            max_retries=int(
                os.getenv(
                    "RESEARCH_MAX_RETRIES",
                    str(user_research.get("max_retries", 2)),
                )
            ),
            rate_limit_delay=float(
                os.getenv(
                    "RESEARCH_RATE_LIMIT_DELAY",
                    str(user_research.get("rate_limit_delay", 1.0)),
                )
            ),
        )
        agent = AgentSettings(
            max_domains=int(
                os.getenv("MAX_DOMAINS", str(user_agent.get("max_domains", 8)))
            ),
            problems_per_domain=int(
                os.getenv(
                    "PROBLEMS_PER_DOMAIN",
                    str(user_agent.get("problems_per_domain", 2)),
                )
            ),
            max_finalists=int(
                os.getenv("MAX_FINALISTS", str(user_agent.get("max_finalists", 5)))
            ),
            max_debate_rounds=int(
                os.getenv(
                    "MAX_DEBATE_ROUNDS",
                    str(user_agent.get("max_debate_rounds", 3)),
                )
            ),
        )
        ci = ContinuousIntelligenceSettings(
            refresh_interval_hours=int(
                os.getenv(
                    "CI_REFRESH_INTERVAL_HOURS",
                    str(user_ci.get("refresh_interval_hours", 24)),
                )
            ),
            max_items_per_source=int(
                os.getenv(
                    "CI_MAX_ITEMS_PER_SOURCE",
                    str(user_ci.get("max_items_per_source", 50)),
                )
            ),
            enabled=os.getenv("CI_ENABLED", "true").lower() not in ("0", "false", "no"),
        )
        logging_cfg = LoggingSettings(
            level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=Path(
                os.getenv(
                    "LOG_FILE",
                    str(_DATA_DIR / "logs" / "hackathoniq.log"),
                )
            ),
        )
        return cls(
            ollama=ollama,
            storage=storage,
            research=research,
            agent=agent,
            continuous_intelligence=ci,
            logging=logging_cfg,
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a singleton Settings instance (lazy-loaded)."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def reset_settings() -> None:
    """Clear the cached settings so the next call reloads."""
    global _settings
    _settings = None


# Backwards-compatible explicit base path used by docs and scripts.
BASE_DIR = _BASE_DIR
DATA_DIR = _DATA_DIR
