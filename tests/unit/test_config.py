"""Configuration and rubric-weight tests."""

from __future__ import annotations

import pytest

from config.settings import EvaluationSettings


def test_default_weights_total_100() -> None:
    settings = EvaluationSettings()
    assert settings.total_weight == 100
    assert sum(settings.as_weights().values()) == 100
    assert len(settings.as_weights()) == 8


def test_weights_reject_invalid_total() -> None:
    with pytest.raises(ValueError):
        EvaluationSettings(problem_significance=20)
