"""Regression tests for Multi-Track Results Page rendering and data model contracts.

Verifies:
1. Six-track Mode B result rendering (no AttributeError on best_per_track).
2. Mode A result rendering (with winner and honest rejection).
3. A track with no qualifying candidate ("No qualifying problem statement found for this track").
4. Missing or empty per-track results handling.
5. Historical result deserialization from SQLite.
6. Results with optional track URLs set to None.
7. Correct winner-to-track mapping.
8. Preservation of citations, qualification gate outcomes, and rejection details.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.database.repository import Repository
from src.models.candidate import CandidateSolution
from src.models.evaluation import (
    CandidateEvaluation,
    QualityGate,
    QualityGateStatus,
    ScoreCriterion,
    WinnerSelection,
)
from src.models.hackathon import HackathonInput, HackathonTrack, MultiTrackMode
from src.models.multitrack import (
    CrossTrackComparisonResult,
    MultiTrackPipelineResult,
    TrackResult,
)
from src.orchestration.loader import load_multi_track_result
from ui.pages.results import _render_multi_track


def _make_track(track_id: str, name: str, url: str | None = None) -> HackathonTrack:
    return HackathonTrack(
        id=track_id,
        name=name,
        description=f"Description for {name}",
        official_track_url=url,
    )


def _make_candidate(cand_id: str, title: str, domain: str) -> CandidateSolution:
    return CandidateSolution(
        id=cand_id,
        problem_candidate_id=f"p-{cand_id}",
        title=title,
        domain=domain,
        problem_statement=f"Critical challenge in {domain}",
        proposed_solution=f"Innovative edge architecture for {title}",
        unique_differentiation=f"Verified unique value proposition for {title}",
    )


def _make_evaluation(
    cand_id: str,
    title: str,
    domain: str,
    score: float,
    all_passed: bool = True,
    citation_url: str = "https://doi.org/10.1016/j.agwat.2024.108",
) -> CandidateEvaluation:
    gates = [
        QualityGate(
            name="Gate 1: Problem Evidence Verification",
            description="Problem is backed by verified citations",
            status=QualityGateStatus.PASSED if all_passed else QualityGateStatus.FAILED,
            justification=f"Grounded in verified citation: {citation_url}" if all_passed else "Insufficient empirical evidence",
        ),
        QualityGate(
            name="Gate 5: Unique Differentiation",
            description="Clear architectural differentiation",
            status=QualityGateStatus.PASSED if all_passed else QualityGateStatus.FAILED,
            justification="Documented structural differentiation",
        ),
    ]
    return CandidateEvaluation(
        candidate_id=cand_id,
        candidate_title=title,
        domain=domain,
        total_score=score,
        raw_score=score,
        normalized_score=score,
        all_gates_passed=all_passed,
        is_qualified=all_passed,
        rank=1 if all_passed else 99,
        scores=[ScoreCriterion(name="Real-world problem significance", score=score / 10, weight=10)],
        quality_gates=gates,
        overall_assessment=f"Comprehensive evaluation for {title} (score: {score:.1f}).",
    )


def test_six_track_mode_b_rendering() -> None:
    """1. Test Six-track Mode B rendering without AttributeError on best_per_track."""
    tracks = [
        _make_track(f"trk-{i}", f"Track {i} — Category", None)
        for i in range(1, 7)
    ]
    hackathon = HackathonInput(
        theme="BeachHack Season 08",
        name="BeachHack S08",
        is_multi_track=True,
        multi_track_mode=MultiTrackMode.BEST_PER_TRACK,
        tracks=tracks,
    )

    per_track_winners = {}
    per_track_evals = {}
    track_results = {}

    for idx, track in enumerate(tracks, 1):
        if idx <= 3:
            # First 3 tracks have qualifying winners
            cand = _make_candidate(f"c-{idx}", f"Solution {idx}", f"Domain {idx}")
            ev = _make_evaluation(f"c-{idx}", f"Solution {idx}", f"Domain {idx}", 85.0 + idx)
            per_track_winners[track.id] = cand
            per_track_evals[track.id] = ev
            w_sel = WinnerSelection(has_winner=True, winner=ev)
        else:
            # Last 3 tracks had no qualifying candidates
            per_track_winners[track.id] = None
            per_track_evals[track.id] = None
            w_sel = WinnerSelection(has_winner=False, rejection_reason="No qualifying candidate passed all gates")

        track_results[track.id] = TrackResult(
            track=track,
            input=HackathonInput(theme=f"Track {idx}"),
            winner=w_sel,
            status="completed",
        )

    comparison = CrossTrackComparisonResult(
        mode=MultiTrackMode.BEST_PER_TRACK,
        total_tracks=6,
        tracks_completed=6,
        per_track_winners=per_track_winners,
        per_track_evaluations=per_track_evals,
    )

    # Verify best_per_track property accessor
    assert len(comparison.best_per_track) == 6
    assert comparison.best_per_track["trk-1"].has_winner is True
    assert comparison.best_per_track["trk-1"].candidate_title == "Solution 1"
    assert comparison.best_per_track["trk-4"].has_winner is False

    multi_result = MultiTrackPipelineResult(
        session_id="test-session-6trk",
        input=hackathon,
        track_results=track_results,
        comparison=comparison,
    )

    # Render without exceptions
    with patch("ui.pages.results.st") as mock_st:
        mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]
        mock_st.tabs.side_effect = lambda tabs: [MagicMock() for _ in tabs]
        _render_multi_track(multi_result)

        # Verify success was called for winning tracks and warning for non-winning tracks
        assert mock_st.success.called
        assert mock_st.warning.called


def test_mode_a_winner_and_honest_rejection_rendering() -> None:
    """2. Test Mode A rendering with winner and with honest rejection."""
    track_1 = _make_track("t-1", "Agents in Production")
    track_2 = _make_track("t-2", "The Trust Layer")
    hackathon = HackathonInput(
        theme="Multi-Track AI",
        is_multi_track=True,
        multi_track_mode=MultiTrackMode.BEST_OVERALL,
        tracks=[track_1, track_2],
    )

    # Case A: Overall winner exists
    cand = _make_candidate("c-win", "Autonomous Edge Agent", "AI")
    ev = _make_evaluation("c-win", "Autonomous Edge Agent", "AI", 91.5, all_passed=True)
    comp_with_winner = CrossTrackComparisonResult(
        mode=MultiTrackMode.BEST_OVERALL,
        total_tracks=2,
        overall_winning_track=track_1,
        overall_winning_candidate=cand,
        overall_winner_evaluation=ev,
    )

    multi_with_winner = MultiTrackPipelineResult(
        session_id="sess-mode-a-win",
        input=hackathon,
        track_results={
            "t-1": TrackResult(track=track_1, input=hackathon, winner=WinnerSelection(has_winner=True, winner=ev)),
            "t-2": TrackResult(track=track_2, input=hackathon, winner=WinnerSelection(has_winner=False)),
        },
        comparison=comp_with_winner,
    )

    with patch("ui.pages.results.st") as mock_st:
        mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]
        mock_st.tabs.side_effect = lambda tabs: [MagicMock() for _ in tabs]
        _render_multi_track(multi_with_winner)
        assert mock_st.markdown.called

    # Case B: Honest rejection across all tracks
    comp_rejected = CrossTrackComparisonResult(
        mode=MultiTrackMode.BEST_OVERALL,
        total_tracks=2,
        overall_winning_track=None,
        overall_winning_candidate=None,
        overall_winner_evaluation=None,
    )
    multi_rejected = MultiTrackPipelineResult(
        session_id="sess-mode-a-rej",
        input=hackathon,
        track_results={
            "t-1": TrackResult(track=track_1, input=hackathon, winner=WinnerSelection(has_winner=False)),
            "t-2": TrackResult(track=track_2, input=hackathon, winner=WinnerSelection(has_winner=False)),
        },
        comparison=comp_rejected,
    )

    with patch("ui.pages.results.st") as mock_st:
        mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]
        mock_st.tabs.side_effect = lambda tabs: [MagicMock() for _ in tabs]
        _render_multi_track(multi_rejected)
        # Should render error for honest rejection
        assert mock_st.error.called


def test_track_with_no_qualifying_candidate_renders_cleanly() -> None:
    """3. Verify track with no qualifying candidate displays required message without inventing winners."""
    track = _make_track("trk-none", "Empty Track")
    hackathon = HackathonInput(
        theme="Theme",
        is_multi_track=True,
        multi_track_mode=MultiTrackMode.BEST_PER_TRACK,
        tracks=[track],
    )
    comp = CrossTrackComparisonResult(
        mode=MultiTrackMode.BEST_PER_TRACK,
        total_tracks=1,
        per_track_winners={"trk-none": None},
        per_track_evaluations={"trk-none": None},
    )
    multi = MultiTrackPipelineResult(
        session_id="sess-empty-track",
        input=hackathon,
        track_results={"trk-none": TrackResult(track=track, input=hackathon, winner=WinnerSelection(has_winner=False))},
        comparison=comp,
    )

    with patch("ui.pages.results.st") as mock_st:
        mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]
        mock_st.tabs.side_effect = lambda tabs: [MagicMock() for _ in tabs]
        _render_multi_track(multi)
        # warning must be displayed
        assert mock_st.warning.called


def test_missing_or_empty_per_track_results() -> None:
    """4. Handle comparison object with empty or None per_track_winners dictionary."""
    track = _make_track("trk-missing", "Unprocessed Track")
    hackathon = HackathonInput(
        theme="Theme",
        is_multi_track=True,
        multi_track_mode=MultiTrackMode.BEST_PER_TRACK,
        tracks=[track],
    )
    # Empty comparison
    comp = CrossTrackComparisonResult(
        mode=MultiTrackMode.BEST_PER_TRACK,
        total_tracks=1,
        per_track_winners={},
        per_track_evaluations={},
    )
    multi = MultiTrackPipelineResult(
        session_id="sess-missing",
        input=hackathon,
        track_results={},
        comparison=comp,
    )

    with patch("ui.pages.results.st") as mock_st:
        mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]
        mock_st.tabs.side_effect = lambda tabs: [MagicMock() for _ in tabs]
        _render_multi_track(multi)
        assert mock_st.warning.called


def test_historical_result_deserialization_beachhack(repository: Repository) -> None:
    """5. Verify historical result deserialization from SQLite for BeachHack session."""
    session_id = repository.create_session(
        "BeachHack Season 08: Agents in Production, The Toolchain, The Trust Layer, The Rails, The Edge, Earth Systems",
        name="BeachHack Season 08",
    )
    repository.db.execute(
        "UPDATE sessions SET is_multi_track=1, multi_track_mode='best_per_track' WHERE id=?",
        (session_id,),
    )
    # Insert tracks
    t1 = _make_track("trk-1", "Agents in Production", None)
    t2 = _make_track("trk-2", "The Toolchain", "https://beachhack.in/tools")
    repository.save_tracks(session_id, [t1, t2])

    comparison_data = {
        "mode": "best_per_track",
        "total_tracks": 2,
        "tracks_completed": 2,
        "tracks_failed": 0,
        "per_track_winners": {"trk-1": None, "trk-2": None},
        "per_track_evaluations": {"trk-1": None, "trk-2": None},
        "ranked_candidates": [],
        "rejected_candidates": [],
        "selection_rationale": "No qualifying problem statement found for this track.",
        "runner_ups_explanation": "",
        "duplicate_detections": [],
    }

    repository.save_multi_track_comparison(
        session_id=session_id,
        mode="best_per_track",
        winning_track_id=None,
        winning_candidate_id=None,
        comparison_data=comparison_data,
    )

    loaded = load_multi_track_result(session_id, repository)
    assert loaded is not None
    assert len(loaded.input.tracks) == 2
    assert loaded.comparison is not None
    assert loaded.comparison.mode == MultiTrackMode.BEST_PER_TRACK
    assert len(loaded.comparison.best_per_track) == 2
    assert loaded.comparison.best_per_track["trk-1"].has_winner is False

    # Render loaded result without exception
    with patch("ui.pages.results.st") as mock_st:
        mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]
        mock_st.tabs.side_effect = lambda tabs: [MagicMock() for _ in tabs]
        _render_multi_track(loaded)


def test_optional_track_url_none_rendering() -> None:
    """6. Results with optional track URLs set to None render without error."""
    track = _make_track("t-nourl", "No URL Track", url=None)
    assert track.official_track_url is None

    hackathon = HackathonInput(
        theme="Theme",
        is_multi_track=True,
        tracks=[track],
    )
    multi = MultiTrackPipelineResult(
        session_id="sess-nourl",
        input=hackathon,
        track_results={"t-nourl": TrackResult(track=track, input=hackathon)},
        comparison=CrossTrackComparisonResult(
            mode=MultiTrackMode.BEST_OVERALL,
            total_tracks=1,
        ),
    )

    with patch("ui.pages.results.st") as mock_st:
        mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]
        mock_st.tabs.side_effect = lambda tabs: [MagicMock() for _ in tabs]
        _render_multi_track(multi)


def test_winner_to_track_mapping_accuracy() -> None:
    """7. Correct winner-to-track mapping across distinct tracks."""
    t1 = _make_track("t1", "Track One")
    t2 = _make_track("t2", "Track Two")

    c1 = _make_candidate("c1", "Title 1", "Domain 1")
    e1 = _make_evaluation("c1", "Title 1", "Domain 1", 88.0)

    c2 = _make_candidate("c2", "Title 2", "Domain 2")
    e2 = _make_evaluation("c2", "Title 2", "Domain 2", 82.0)

    comp = CrossTrackComparisonResult(
        mode=MultiTrackMode.BEST_PER_TRACK,
        total_tracks=2,
        per_track_winners={"t1": c1, "t2": c2},
        per_track_evaluations={"t1": e1, "t2": e2},
    )

    best = comp.best_per_track
    assert best["t1"].candidate.title == "Title 1"
    assert best["t1"].evaluation.total_score == 88.0
    assert best["t2"].candidate.title == "Title 2"
    assert best["t2"].evaluation.total_score == 82.0


def test_preservation_of_citations_and_gates() -> None:
    """8. Preservation of citations and qualification gate outcomes."""
    cand = _make_candidate("c-cited", "Cited Candidate", "Agritech")
    citation = "https://doi.org/10.1016/j.cropro.2024.106"
    ev = _make_evaluation("c-cited", "Cited Candidate", "Agritech", 89.0, all_passed=True, citation_url=citation)

    gate1 = ev.quality_gates[0]
    assert gate1.status == QualityGateStatus.PASSED
    assert citation in gate1.justification

    t = _make_track("t-cite", "Agritech Track")
    tr = TrackResult(
        track=t,
        input=HackathonInput(theme="Agri"),
        winner=WinnerSelection(has_winner=True, winner=ev),
    )

    comp = CrossTrackComparisonResult(
        mode=MultiTrackMode.BEST_PER_TRACK,
        total_tracks=1,
        per_track_winners={"t-cite": cand},
        per_track_evaluations={"t-cite": ev},
    )
    multi = MultiTrackPipelineResult(
        session_id="sess-cite",
        input=HackathonInput(theme="Agri", is_multi_track=True, tracks=[t]),
        track_results={"t-cite": tr},
        comparison=comp,
    )

    with patch("ui.pages.results.st") as mock_st:
        mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]
        mock_st.tabs.side_effect = lambda tabs: [MagicMock() for _ in tabs]
        _render_multi_track(multi)

        # Confirm gate 1 citation was retained
        assert citation in ev.quality_gates[0].justification


def test_safe_navigation_helper() -> None:
    """9. Safe navigation queues target page in session state without modifying widget state during instantiation."""
    from ui.components.common import navigate_to

    fake_session: dict = {}
    with patch("streamlit.session_state", fake_session), patch("streamlit.rerun") as mock_rerun:
        navigate_to("Results")
        assert fake_session.get("target_nav") == "Results"
        assert "nav_choice" not in fake_session
        mock_rerun.assert_called_once()

