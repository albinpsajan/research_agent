"""Execute autonomous research workflow for the extracted BeachHack Season 08 configuration."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.database.repository import Repository
from src.knowledge.document_intelligence.service import DocumentIntelligenceService
from src.llm.client import OllamaClient
from src.models.pipeline import PipelineOptions


def main() -> None:
    print("=" * 80)
    print("  HACKATHONIQ — AUTONOMOUS DOCUMENT-TO-RESEARCH EXECUTION")
    print("  Document: BeachHack Season 08 (6 Tracks)")
    print("=" * 80)

    repo = Repository()
    llm = OllamaClient()
    service = DocumentIntelligenceService(repository=repo, llm=llm)

    h_input = service.get_active_auto_configuration()
    if not h_input:
        print("ERROR: No active auto-configuration found from uploaded documents.")
        sys.exit(1)

    print(f"\n[1] Extracted Event Configuration:")
    print(f"  Event Name:       {h_input.name}")
    print(f"  Theme:            {h_input.theme}")
    print(f"  Deadline:         {h_input.deadline}")
    print(f"  Multi-Track Mode: {h_input.multi_track_mode.value}")
    print(f"  Total Tracks:     {len(h_input.tracks)}")
    for i, t in enumerate(h_input.tracks, start=1):
        print(f"    Track {i}: {t.name}")
        print(f"      Scope: {t.description}")
        if t.track_rules:
            print(f"      Rules: {t.track_rules[:80]}...")

    # Fast, bounded, resource-safe pipeline options across all 6 tracks
    options = PipelineOptions(
        max_domains=1,
        problems_per_domain=1,
        max_finalists=2,
        max_debate_rounds=1,
        include_continuous_intelligence=True,
    )

    t_start = time.perf_counter()

    def on_progress(stage: str, msg: str, frac: float) -> None:
        elapsed = time.perf_counter() - t_start
        print(f"  [{elapsed:6.1f}s | {int(frac * 100):3d}%] [{stage}] {msg}")

    print("\n[2] Initiating Autonomous 5-Agent Multi-Track Pipeline...")
    result = service.execute_automated_research(
        hackathon_input=h_input,
        options=options,
        progress_callback=on_progress,
    )

    elapsed_total = time.perf_counter() - t_start
    print("\n" + "=" * 80)
    print("  EXECUTION COMPLETE")
    print("=" * 80)
    print(f"Total Duration: {elapsed_total:.2f} seconds")
    print(f"Session ID:     {result.session_id}")
    print(f"Status:         {result.status}")

    # Check comparison result
    comp = getattr(result, "comparison", None)
    if comp:
        print("\n[3] Cross-Track Comparison Outcome:")
        if comp.overall_winning_track and comp.overall_winning_candidate:
            print(f"  🏆 Overall Winning Track:     {comp.overall_winning_track.name}")
            print(f"  🏆 Winning Candidate Title:   {comp.overall_winning_candidate.candidate_title}")
            print(f"  🏆 Score:                     {comp.overall_winning_candidate.total_score:.1f} / 100")
            print(f"  All 10 Gates Passed:          {comp.overall_winning_candidate.all_gates_passed}")
            print(f"  Justification:                {comp.overall_selection_justification[:160]}...")
        else:
            print("  No qualifying candidate passed all 10 mandatory evaluation gates.")

        print(f"\n  Evaluated Tracks ({len(result.track_results)}):")
        for tid, tres in result.track_results.items():
            t_win = tres.winner.winner if (tres.winner and tres.winner.has_winner) else None
            win_title = t_win.candidate_title if t_win else "None (honest rejection)"
            win_score = f"{t_win.total_score:.1f}/100" if t_win else "N/A"
            print(f"    - {tres.track.name:25s} | Winner: {win_title[:35]:35s} | Score: {win_score}")

    master_path = getattr(result, "master_report_path", None)
    if master_path:
        print(f"\n[4] Master Report Generated: {master_path}")


if __name__ == "__main__":
    main()
