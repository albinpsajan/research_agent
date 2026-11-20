"""URL safety and evidence-integrity tests."""

from __future__ import annotations

import socket
import pytest

from src.agents.base import allowed_urls, sanitize_model_urls, similarity
from src.research.base import ResearchError, validate_public_url
from src.research.registry import SearchBundle
from src.research.base import SearchResult
from src.models.hackathon import OrganizerProfile


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/x",
        "http://127.0.0.1/x",
        "http://10.0.0.5/x",
        "http://192.168.1.2/x",
        "http://169.254.1.1/x",
        "file:///etc/passwd",
        "http://user:pass@example.com/x",
    ],
)
def test_private_or_unsafe_urls_rejected(url: str) -> None:
    with pytest.raises(ResearchError):
        validate_public_url(url)


def test_public_url_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    # Deterministic mock DNS for offline test execution
    def mock_getaddrinfo(host: str, port: object, *args: object, **kwargs: object) -> list:
        if host == "example.com":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        raise socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)
    assert validate_public_url("https://example.com/path") == "https://example.com/path"


def test_dns_rebinding_private_ip_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    # A public-looking hostname that resolves to an internal/private IP must be blocked
    def mock_rebinding(host: str, port: object, *args: object, **kwargs: object) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.100", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_rebinding)
    with pytest.raises(ResearchError, match="resolves to a private address"):
        validate_public_url("https://malicious-rebinding.com/steal")


def test_unresolvable_host_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_fail(host: str, port: object, *args: object, **kwargs: object) -> list:
        raise socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", mock_fail)
    with pytest.raises(ResearchError, match="Cannot resolve host"):
        validate_public_url("https://does-not-exist-anywhere.invalid/test")


def test_hallucinated_urls_are_removed() -> None:
    bundle = SearchBundle(
        query="q",
        results=[
            SearchResult(title="A", url="https://real.example/a", source_type="web")
        ],
    )
    model = OrganizerProfile(
        name="Org",
        website="https://invented.example/fake",
        source_urls=["https://real.example/a", "https://invented.example/x"],
    )
    removed = sanitize_model_urls(model, allowed_urls(bundle))
    assert model.website is None
    assert model.source_urls == ["https://real.example/a"]
    assert len(removed) == 2


def test_similarity_detects_duplicates() -> None:
    assert similarity("urban air quality routing", "urban air quality route planning") > 0.5
    assert similarity("quantum computing", "municipal waste recycling") < 0.2


def test_finalist_labels_are_parsed_from_prose() -> None:
    from src.agents.adversarial_critic import _label

    assert _label("Finalist A") == "A"
    assert _label("FINALIST J") == "J"
    assert _label("Option C") == "C"
    assert _label("B") == "B"
    assert _label("") == ""
