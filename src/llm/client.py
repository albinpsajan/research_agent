"""Ollama integration with validated structured output.

All five agents share this single client and one local model.  Nothing in the
application requires a paid API key.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from config.logging_config import get_logger
from config.settings import OllamaSettings, get_settings

logger = get_logger("llm")

TModel = TypeVar("TModel", bound=BaseModel)


class LLMError(RuntimeError):
    """Base class for local-model failures."""


class LLMUnavailableError(LLMError):
    """Ollama is not running or no usable model is installed."""


class LLMOutputError(LLMError):
    """The model could not produce schema-valid output after retries."""


class LLMClientProtocol(Protocol):
    """Interface used by agents; tests substitute a deterministic fake."""

    def generate_json(
        self,
        prompt: str,
        schema: type[TModel],
        system: str | None = None,
        temperature: float | None = None,
    ) -> TModel: ...

    def generate_text(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
    ) -> str: ...

    def model_name(self) -> str: ...


@dataclass
class LLMStats:
    """Lightweight, reportable usage statistics."""

    calls: int = 0
    failures: int = 0
    prompt_chars: int = 0
    response_chars: int = 0
    total_seconds: float = 0.0
    by_agent: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "failures": self.failures,
            "prompt_chars": self.prompt_chars,
            "response_chars": self.response_chars,
            "total_seconds": round(self.total_seconds, 2),
            "by_agent": dict(self.by_agent),
        }


def extract_json(text: str, allow_salvage: bool = False) -> Any:
    """Extract the first balanced JSON object/array from model output.

    Small local models frequently wrap JSON in prose or code fences.  This
    parser is deliberately tolerant about wrapping but strict about syntax.
    If *allow_salvage* is True, safe completion of truncated brackets/strings
    is attempted when output terminates mid-stream.
    """
    if not text or not text.strip():
        raise LLMOutputError("Empty model response")
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Scan for a balanced top-level object or array, respecting strings/escapes.
    start = min(
        [i for i in (cleaned.find("{"), cleaned.find("[")) if i >= 0],
        default=-1,
    )
    if start < 0:
        raise LLMOutputError("No JSON object or array found in response")
    opener = cleaned[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escaped = False
    bracket_stack: list[str] = []
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in ("{", "["):
            depth += 1
            bracket_stack.append("}" if char == "{" else "]")
        elif char in ("}", "]"):
            depth -= 1
            if bracket_stack and bracket_stack[-1] == char:
                bracket_stack.pop()
            if depth == 0:
                candidate = cleaned[start : index + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # Attempt safe repair of trailing commas common in small LLM outputs
                    fixed = re.sub(r",\s*([\]}])", r"\1", candidate)
                    try:
                        return json.loads(fixed)
                    except json.JSONDecodeError as exc:
                        raise LLMOutputError(f"Malformed JSON: {exc}") from exc

    # Attempt safe salvage if response was truncated mid-stream by token limit
    if allow_salvage and depth > 0 and bracket_stack:
        salvage = cleaned[start:]
        if in_string:
            salvage += '"'
        salvage = re.sub(r",\s*$", "", salvage)
        salvage += "".join(reversed(bracket_stack))
        fixed = re.sub(r",\s*([\]}])", r"\1", salvage)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

    raise LLMOutputError("Unbalanced JSON in model response")


def truncate(text: str, limit: int = 4000) -> str:
    """Bound prompt context without silently losing the truncation marker."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


def compact_json(payload: Any, limit: int = 12000) -> str:
    """Serialize context compactly for a small-context local model."""
    return truncate(json.dumps(payload, ensure_ascii=False, default=str), limit)


class OllamaClient:
    """Synchronous Ollama chat client with schema validation and repair."""

    def __init__(self, settings: OllamaSettings | None = None) -> None:
        self.settings = settings or get_settings().ollama
        self.stats = LLMStats()
        self._resolved_model: str | None = None
        self._http = httpx.Client(
            base_url=self.settings.base_url,
            timeout=httpx.Timeout(self.settings.timeout, connect=10.0),
            headers={"User-Agent": "HackathonIQ/1.0"},
        )

    # ------------------------------------------------------------------
    # Availability / models
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Return Ollama health and installed models; never raises."""
        try:
            response = self._http.get("/api/tags", timeout=5.0)
            response.raise_for_status()
            models = response.json().get("models", [])
            names = [m.get("name", "") for m in models if m.get("name")]
            return {
                "available": True,
                "base_url": self.settings.base_url,
                "models": names,
                "model_present": any(
                    name == self.settings.model
                    or name.split(":")[0] == self.settings.model.split(":")[0]
                    for name in names
                ),
                "active_model": self._resolved_model or self.settings.model,
            }
        except Exception as exc:  # noqa: BLE001 - health must never crash UI
            return {
                "available": False,
                "base_url": self.settings.base_url,
                "models": [],
                "model_present": False,
                "active_model": self.settings.model,
                "error": str(exc),
            }

    def list_models(self) -> list[dict[str, Any]]:
        response = self._http.get("/api/tags")
        response.raise_for_status()
        return response.json().get("models", [])

    def pull_model(self, name: str) -> bool:
        """Pull a model, streaming progress to the log. Requires disk checks
        to have happened in the caller/UI before invocation."""
        logger.info("Pulling Ollama model %s", name)
        with self._http.stream(
            "POST",
            "/api/pull",
            json={"name": name, "stream": True},
            timeout=httpx.Timeout(3600.0, connect=10.0),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("status") == "success":
                    logger.info("Model %s pulled successfully", name)
                    return True
                if event.get("error"):
                    raise LLMError(str(event["error"]))
        return True

    def resolve_model(self) -> str:
        """Pick the configured model, falling back only if it is missing."""
        if self._resolved_model:
            return self._resolved_model
        health = self.health()
        if not health.get("available"):
            raise LLMUnavailableError(
                f"Ollama is not reachable at {self.settings.base_url}. "
                "Start the Ollama app or run `ollama serve`."
            )
        names = health.get("models", [])
        if not names:
            raise LLMUnavailableError(
                "Ollama is running but no models are installed. "
                f"Run `ollama pull {self.settings.model}`."
            )

        def matches(candidate: str) -> str | None:
            if candidate in names:
                return candidate
            base = candidate.split(":")[0]
            for installed in names:
                if installed.split(":")[0] == base:
                    return installed
            return None

        for candidate in (self.settings.model, self.settings.fallback_model):
            found = matches(candidate)
            if found:
                self._resolved_model = found
                logger.info("Using Ollama model %s", found)
                return found
        # Last resort: use the first installed model, but say so.
        self._resolved_model = names[0]
        logger.warning(
            "Configured models are missing; using installed model %s", names[0]
        )
        return names[0]

    def model_name(self) -> str:
        return self._resolved_model or self.settings.model

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _chat(
        self,
        prompt: str,
        system: str | None,
        response_format: dict[str, Any] | None,
        temperature: float | None,
        num_predict: int | None,
    ) -> str:
        model = self.resolve_model()
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": (
                    self.settings.temperature if temperature is None else temperature
                ),
                "num_ctx": self.settings.num_ctx,
                "num_predict": num_predict or self.settings.num_predict,
            },
        }
        if response_format:
            payload["format"] = response_format

        started = time.perf_counter()
        self.stats.calls += 1
        self.stats.prompt_chars += len(prompt) + (len(system) if system else 0)
        try:
            response = self._http.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            content = (data.get("message") or {}).get("content", "")
            if not content:
                raise LLMError("Ollama returned an empty message")
            self.stats.response_chars += len(content)
            return content
        except httpx.HTTPStatusError as exc:
            self.stats.failures += 1
            raise LLMError(
                f"Ollama HTTP {exc.response.status_code}: {exc.response.text[:300]}"
            ) from exc
        except httpx.HTTPError as exc:
            self.stats.failures += 1
            raise LLMUnavailableError(f"Ollama request failed: {exc}") from exc
        finally:
            self.stats.total_seconds += time.perf_counter() - started

    def generate_text(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
        num_predict: int | None = None,
    ) -> str:
        return self._chat(prompt, system, None, temperature, num_predict).strip()

    def generate_json(
        self,
        prompt: str,
        schema: type[TModel],
        system: str | None = None,
        temperature: float | None = None,
    ) -> TModel:
        """Generate JSON validated against *schema*, with bounded repair retries.

        The model is given the Pydantic JSON schema as Ollama's ``format`` and
        the response is re-validated in Python.  Invalid output is never
        accepted as a result.
        """
        json_schema = schema.model_json_schema()
        last_error: str | None = None
        raw = ""
        for attempt in range(self.settings.max_json_retries + 1):
            instruction = prompt
            if attempt:
                instruction = (
                    f"{prompt}\n\nYour previous response was rejected.\n"
                    f"Validation error: {last_error}\n"
                    "Return ONLY corrected JSON matching the schema. "
                    "Do not add commentary."
                )
            raw = self._chat(instruction, system, json_schema, temperature, None)
            try:
                try:
                    payload = extract_json(raw)
                except LLMOutputError:
                    payload = extract_json(raw, allow_salvage=True)
                return schema.model_validate(payload)
            except (LLMOutputError, ValidationError) as exc:
                last_error = str(exc)[:1500]
                logger.warning(
                    "Structured output attempt %s/%s failed for %s: %s",
                    attempt + 1,
                    self.settings.max_json_retries + 1,
                    schema.__name__,
                    last_error[:300],
                )
        raise LLMOutputError(
            f"Could not obtain valid {schema.__name__} JSON. "
            f"Last error: {last_error}. Raw response: {truncate(raw, 500)}"
        )

    def close(self) -> None:
        self._http.close()
