"""Provenance categories and constraint classification models."""

from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel


class ProvenanceCategory(StrEnum):
    """Explicit provenance categories for all requirements and claims."""

    USER_PROVIDED = "user_provided"  # A. User-provided constraints
    OFFICIAL_HACKATHON = "official_hackathon"  # B. Official hackathon rules/constraints
    EVIDENCE_SUPPORTED = "evidence_supported"  # C. Evidence-supported empirical findings
    AGENT_HYPOTHESIS = "agent_hypothesis"  # D. Agent-derived working hypotheses
    DESIGN_RECOMMENDATION = "design_recommendation"  # E. Optional design recommendations


class CategorizedConstraint(BaseModel):
    """A constraint or requirement with clear, verified provenance."""

    category: ProvenanceCategory
    description: str
    source: str = ""
    is_mandatory: bool = False
    notes: str = ""
