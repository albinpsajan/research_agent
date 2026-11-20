"""JSON extraction and LLM output robustness tests."""

from __future__ import annotations

import pytest

from src.llm.client import LLMOutputError, extract_json, truncate


def test_extract_plain_object() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_from_code_fence() -> None:
    assert extract_json('Here you go:\n```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}


def test_extract_from_prose_with_nested_braces() -> None:
    text = 'Result: {"a": {"b": "}"}, "c": [1, 2]} done'
    assert extract_json(text) == {"a": {"b": "}"}, "c": [1, 2]}


def test_extract_array() -> None:
    assert extract_json('prefix [1, {"x": 2}] suffix') == [1, {"x": 2}]


def test_extract_rejects_empty_and_malformed() -> None:
    with pytest.raises(LLMOutputError):
        extract_json("")
    with pytest.raises(LLMOutputError):
        extract_json("no json here")
    with pytest.raises(LLMOutputError):
        extract_json('{"a": 1')


def test_truncate_marks_loss() -> None:
    output = truncate("abcdefghij", 5)
    assert output.startswith("abcde")
    assert "truncated" in output
