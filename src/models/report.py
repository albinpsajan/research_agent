"""Pydantic models for final report generation."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from src.utils.hackathon_time import utc_now


class ReportSection(BaseModel):
    """A section of the final report."""
    number: int
    title: str
    content: str
    subsections: list[ReportSection] = Field(default_factory=list)
    evidence_links: list[str] = Field(default_factory=list)


class ReportMetadata(BaseModel):
    """Metadata for a generated report."""
    report_id: str
    session_id: str
    hackathon_theme: str
    hackathon_name: Optional[str] = None
    generated_at: datetime = Field(default_factory=utc_now)
    generation_time_seconds: float = 0
    total_domains_explored: int = 0
    total_problems_found: int = 0
    total_solutions_analyzed: int = 0
    total_candidates_evaluated: int = 0
    model_used: str = ""
    version: str = "1.0.0"


class FinalReport(BaseModel):
    """The complete HackathonIQ final report."""
    metadata: ReportMetadata
    sections: list[ReportSection] = Field(default_factory=list)
    evidence_links: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    data_freshness: dict[str, str] = Field(default_factory=dict)
    
    def to_markdown(self) -> str:
        """Convert report to markdown format."""
        lines = [f"# HackathonIQ Report: {self.metadata.hackathon_theme}", ""]
        lines.append(f"**Generated:** {self.metadata.generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append(f"**Model:** {self.metadata.model_used}")
        lines.append("")
        for section in self.sections:
            lines.append(f"## {section.number}. {section.title}")
            lines.append("")
            lines.append(section.content)
            lines.append("")
            for sub in section.subsections:
                lines.append(f"### {section.number}.{sub.number}. {sub.title}")
                lines.append("")
                lines.append(sub.content)
                lines.append("")
        if self.unresolved_questions:
            lines.append("## Unresolved Questions")
            for q in self.unresolved_questions:
                lines.append(f"- {q}")
            lines.append("")
        if self.limitations:
            lines.append("## Limitations")
            for l in self.limitations:
                lines.append(f"- {l}")
            lines.append("")
        if self.evidence_links:
            lines.append("## Evidence Links")
            for link in self.evidence_links:
                lines.append(f"- {link}")
        return "\n".join(lines)
