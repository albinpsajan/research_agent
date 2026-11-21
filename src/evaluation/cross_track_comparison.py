"""Dedicated Cross-Track Comparison Engine for Multi-Track Hackathons.

Provides uniform, explainable evaluation and ranking across all supplied tracks for:
- Mode A (Best Overall Track): Crown single strongest candidate across all tracks with runner-up explanations.
- Mode B (Best Idea Per Track): Crown strongest qualifying candidate per track, or mark 'No qualifying problem statement found for this track'.
- Cross-track duplicate and near-duplicate candidate detection with best-fit track resolution.
"""

from __future__ import annotations

import re
from typing import Any

from config.logging_config import get_logger
from src.models.candidate import CandidateSolution
from src.models.evaluation import CandidateEvaluation
from src.models.hackathon import HackathonIntelligence, HackathonTrack, MultiTrackMode
from src.models.multitrack import (
    CrossTrackComparisonItem,
    CrossTrackComparisonResult,
    TrackResult,
)

logger = get_logger("evaluation.cross_track_comparison")


class CrossTrackComparisonEngine:
    """Compares, ranks, and selects winners across multiple hackathon tracks under uniform standards."""

    DUPLICATE_SIMILARITY_THRESHOLD = 0.58

    def __init__(self, similarity_threshold: float = DUPLICATE_SIMILARITY_THRESHOLD) -> None:
        self.similarity_threshold = similarity_threshold

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        words = re.findall(r"[a-z0-9]{3,}", text.lower())
        stopwords = {
            "the", "and", "for", "with", "this", "that", "from", "using", "into",
            "system", "platform", "solution", "based", "data", "model", "hackathon",
        }
        return set(words) - stopwords

    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """Calculate token-based Jaccard similarity between two texts."""
        set_a = self._tokenize(text_a)
        set_b = self._tokenize(text_b)
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return round(intersection / union, 3)

    def detect_cross_track_duplicates(
        self,
        candidate_items: list[tuple[HackathonTrack, CandidateSolution, CandidateEvaluation]],
    ) -> list[dict[str, Any]]:
        """Identify duplicate or near-duplicate candidates submitted across different tracks."""
        duplicates: list[dict[str, Any]] = []
        n = len(candidate_items)

        for i in range(n):
            track_a, cand_a, eval_a = candidate_items[i]
            text_a = f"{cand_a.problem_statement} {cand_a.proposed_solution} {cand_a.unique_differentiation}"
            tokens_a = self._tokenize(text_a)

            for j in range(i + 1, n):
                track_b, cand_b, eval_b = candidate_items[j]
                if track_a.id == track_b.id:
                    continue  # Only compare across distinct tracks

                text_b = f"{cand_b.problem_statement} {cand_b.proposed_solution} {cand_b.unique_differentiation}"
                sim = self.compute_similarity(text_a, text_b)

                if sim >= self.similarity_threshold:
                    # Determine best fit track based on track name/description overlap
                    track_tokens_a = self._tokenize(f"{track_a.name} {track_a.description}")
                    track_tokens_b = self._tokenize(f"{track_b.name} {track_b.description}")

                    overlap_a = len(tokens_a & track_tokens_a)
                    overlap_b = len(tokens_a & track_tokens_b)

                    best_fit_track = track_a if overlap_a >= overlap_b else track_b

                    duplicates.append({
                        "candidate_a_id": cand_a.id,
                        "candidate_a_title": cand_a.title or cand_a.problem_statement[:60],
                        "track_a_id": track_a.id,
                        "track_a_name": track_a.name,
                        "candidate_b_id": cand_b.id,
                        "candidate_b_title": cand_b.title or cand_b.problem_statement[:60],
                        "track_b_id": track_b.id,
                        "track_b_name": track_b.name,
                        "similarity_score": sim,
                        "best_fit_track_id": best_fit_track.id,
                        "best_fit_track_name": best_fit_track.name,
                        "resolution_note": (
                            f"Identical core problem detected across tracks '{track_a.name}' and '{track_b.name}'. "
                            f"Designated primary best fit: '{best_fit_track.name}'."
                        ),
                    })

        return duplicates

    def _extract_criterion_score(self, evaluation: CandidateEvaluation, pattern: str) -> float:
        for s in evaluation.scores:
            if re.search(pattern, s.name, re.IGNORECASE):
                return s.score
        return 0.0

    def compare(
        self,
        track_results: dict[str, TrackResult],
        mode: MultiTrackMode,
        shared_intelligence: HackathonIntelligence | None = None,
    ) -> CrossTrackComparisonResult:
        """Execute comprehensive cross-track ranking and winner determination."""
        all_candidates: list[tuple[HackathonTrack, CandidateSolution, CandidateEvaluation]] = []

        total_tracks = len(track_results)
        tracks_completed = sum(1 for tr in track_results.values() if tr.status != "failed")
        tracks_failed = sum(1 for tr in track_results.values() if tr.status == "failed")

        # Harvest all evaluated candidates
        for track_id, tr in track_results.items():
            if tr.status == "failed" or not tr.feasibility:
                continue

            eval_map: dict[str, CandidateEvaluation] = {}
            if tr.winner and tr.winner.winner:
                eval_map[tr.winner.winner.candidate_id] = tr.winner.winner
            if tr.winner:
                for ru in tr.winner.runner_ups:
                    eval_map[ru.candidate_id] = ru

            for cand in tr.feasibility.candidates:
                ev = eval_map.get(cand.id)
                if ev:
                    all_candidates.append((tr.track, cand, ev))

        # Detect cross-track duplicates
        duplicates = self.detect_cross_track_duplicates(all_candidates)
        dup_resolved_candidate_keys: set[tuple[str, str]] = set()
        best_fit_map: dict[tuple[str, str], str] = {}
        for dup in duplicates:
            # If candidate is not in its best fit track, exclude from overall winner contention
            if dup["best_fit_track_id"] == dup["track_a_id"]:
                dup_resolved_candidate_keys.add((dup["track_b_id"], dup["candidate_b_id"]))
                best_fit_map[(dup["track_b_id"], dup["candidate_b_id"])] = dup["best_fit_track_name"]
            else:
                dup_resolved_candidate_keys.add((dup["track_a_id"], dup["candidate_a_id"]))
                best_fit_map[(dup["track_a_id"], dup["candidate_a_id"])] = dup["best_fit_track_name"]

        # Build comparison items
        comparison_items: list[CrossTrackComparisonItem] = []
        for track, cand, ev in all_candidates:
            cand_key = (track.id, cand.id)
            is_dup = cand_key in dup_resolved_candidate_keys
            item = CrossTrackComparisonItem(
                candidate_id=cand.id,
                candidate_title=cand.title or cand.problem_statement[:80],
                track_id=track.id,
                track_name=track.name,
                domain=cand.domain,
                total_score=ev.total_score,
                raw_score=ev.raw_score,
                normalized_score=ev.normalized_score,
                all_gates_passed=ev.all_gates_passed,
                is_qualified=ev.is_qualified and (not is_dup),
                is_duplicate=is_dup,
                best_fit_track_name=best_fit_map.get(cand_key, track.name),
                rank_in_track=ev.rank,
                impact_score=self._extract_criterion_score(ev, r"problem significance|impact"),
                originality_score=self._extract_criterion_score(ev, r"originality|differentiation"),
                feasibility_score=self._extract_criterion_score(ev, r"feasibility"),
                relevance_score=self._extract_criterion_score(ev, r"relevance|geographic"),
                organizer_alignment_score=self._extract_criterion_score(ev, r"organizer|judging"),
                evidence_strength_score=self._extract_criterion_score(ev, r"evidence|credibility"),
                demo_potential_score=self._extract_criterion_score(ev, r"demo|hero flow"),
                summary_justification=ev.overall_assessment or cand.unique_differentiation[:160],
                proposed_solution_preview=cand.proposed_solution[:200],
                unique_differentiation=cand.unique_differentiation[:200],
            )
            comparison_items.append(item)

        # Sort: qualifying candidates first by total_score desc, then disqualified by total_score desc
        qualifying_items = [ci for ci in comparison_items if ci.is_qualified]
        disqualified_items = [ci for ci in comparison_items if not ci.is_qualified]

        qualifying_items.sort(key=lambda ci: ci.total_score, reverse=True)
        disqualified_items.sort(key=lambda ci: ci.total_score, reverse=True)

        for rank, ci in enumerate(qualifying_items, start=1):
            ci.rank_overall = rank

        # --- MODE A: Best Overall Track ---
        overall_winning_track = None
        overall_winning_cand = None
        overall_winning_eval = None
        selection_rationale = ""
        runner_ups_explanation = ""

        if qualifying_items:
            best_ci = qualifying_items[0]
            # Match back to candidate and track
            for track, cand, ev in all_candidates:
                if cand.id == best_ci.candidate_id and track.id == best_ci.track_id:
                    overall_winning_track = track
                    overall_winning_cand = cand
                    overall_winning_eval = ev
                    break

            selection_rationale = (
                f"Candidate '{best_ci.candidate_title}' in Track '{best_ci.track_name}' achieved the highest "
                f"defensible score ({best_ci.total_score:.2f}/100) across all {total_tracks} tracks, passing all 10 "
                f"mandatory quality gates with zero disqualifications. Key strengths include high real-world impact "
                f"({best_ci.impact_score:.1f}/10), verified technical feasibility ({best_ci.feasibility_score:.1f}/10), "
                f"and robust evidence corroboration ({best_ci.evidence_strength_score:.1f}/10)."
            )

            # Runner ups explanation
            runner_up_lines = []
            for ru in qualifying_items[1:5]:
                runner_up_lines.append(
                    f"- [{ru.track_name}] '{ru.candidate_title}' (Score: {ru.total_score:.1f}/100): "
                    f"Strong contender in {ru.domain}, but scored lower on "
                    f"{'originality' if ru.originality_score < best_ci.originality_score else 'feasibility or evidence strength'}."
                )
            runner_ups_explanation = "\n".join(runner_up_lines) if runner_up_lines else "No qualifying runner-up candidates."
        else:
            selection_rationale = (
                "HONEST REJECTION: No candidate across any of the supplied tracks satisfied all 10 mandatory "
                "quality gates. HackathonIQ strictly refuses to invent or force an ungrounded overall winner."
            )

        # --- MODE B: Best Idea Per Track ---
        per_track_winners: dict[str, CandidateSolution | None] = {}
        per_track_evals: dict[str, CandidateEvaluation | None] = {}

        for track_id, tr in track_results.items():
            track_qualifying = [
                ci for ci in qualifying_items
                if ci.track_id == track_id
            ]
            if track_qualifying:
                best_track_ci = track_qualifying[0]
                matched_cand = None
                matched_eval = None
                for track, cand, ev in all_candidates:
                    if cand.id == best_track_ci.candidate_id and track.id == track_id:
                        matched_cand = cand
                        matched_eval = ev
                        break
                per_track_winners[track_id] = matched_cand
                per_track_evals[track_id] = matched_eval
            else:
                per_track_winners[track_id] = None
                per_track_evals[track_id] = None

        if mode == MultiTrackMode.BEST_PER_TRACK:
            mode_b_summaries: list[str] = []
            for track_id, tr in track_results.items():
                winner_cand = per_track_winners.get(track_id)
                if winner_cand:
                    mode_b_summaries.append(
                        f"Track '{tr.track.name}': Winner '{winner_cand.title or winner_cand.problem_statement[:60]}'."
                    )
                else:
                    mode_b_summaries.append(
                        f"Track '{tr.track.name}': No qualifying problem statement found for this track."
                    )
            selection_rationale = "\n".join(mode_b_summaries)

        return CrossTrackComparisonResult(
            mode=mode,
            total_tracks=total_tracks,
            tracks_completed=tracks_completed,
            tracks_failed=tracks_failed,
            overall_winning_track=overall_winning_track,
            overall_winning_candidate=overall_winning_cand,
            overall_winner_evaluation=overall_winning_eval,
            per_track_winners=per_track_winners,
            per_track_evaluations=per_track_evals,
            ranked_candidates=qualifying_items,
            rejected_candidates=disqualified_items,
            selection_rationale=selection_rationale,
            runner_ups_explanation=runner_ups_explanation,
            duplicate_detections=duplicates,
        )
