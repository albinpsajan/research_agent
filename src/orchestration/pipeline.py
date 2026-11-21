"""LangGraph orchestration for the complete HackathonIQ workflow."""

from __future__ import annotations

import gc
from collections.abc import Callable

from langgraph.graph import END, StateGraph

from config.logging_config import get_logger, setup_logging
from config.settings import get_settings
from src.agents.adversarial_critic import AdversarialCriticAgent
from src.agents.domain_discovery import DomainDiscoveryAgent
from src.agents.hackathon_intelligence import HackathonIntelligenceAgent
from src.agents.innovation_research import InnovationResearchAgent
from src.agents.solution_architect import SolutionArchitectAgent
from src.database.migrations import initialize_database
from src.database.repository import Repository
from src.evaluation.cross_track_comparison import CrossTrackComparisonEngine
from src.intelligence.service import ContinuousIntelligenceService
from src.llm.client import LLMClientProtocol, OllamaClient
from src.models.candidate import FeasibilityReport
from src.models.evaluation import FinalEvaluationReport, WinnerSelection
from src.models.hackathon import HackathonInput
from src.models.multitrack import (
    MultiTrackPipelineResult,
    TrackResult,
)
from src.models.pipeline import PipelineOptions, PipelineResult
from src.models.research import InnovationReport
from src.orchestration.state import PipelineState
from src.reports.generator import ReportGenerator
from src.research.registry import ResearchService
from src.storage.manager import StorageManager
from src.utils.hackathon_time import utc_now

logger = get_logger("orchestration")

ProgressCallback = Callable[[str, str, float], None]

STAGES = {
    "prepare": (0.02, "Preparing workspace and continuous intelligence"),
    "hackathon_intelligence": (0.10, "Agent 1 — Hackathon intelligence"),
    "domain_discovery": (0.30, "Agent 2 — Dynamic domain and problem discovery"),
    "innovation_research": (0.52, "Agent 3 — Existing solutions and innovation gaps"),
    "solution_architecture": (0.70, "Agent 4 — Solution architecture and feasibility"),
    "adversarial_evaluation": (
        0.86,
        "Agent 5 — Adversarial debate and final evaluation",
    ),
    "report": (0.96, "Generating the 24-section final report"),
    "finalize": (1.0, "Completed"),
}


class HackathonPipeline:
    """Runs the five specialist agents as a LangGraph state machine."""

    def __init__(
        self,
        *,
        llm: LLMClientProtocol | None = None,
        repository: Repository | None = None,
        research: ResearchService | None = None,
        intelligence: ContinuousIntelligenceService | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        setup_logging()
        self.settings = get_settings()
        self.repository = repository or Repository()
        self.llm = llm or OllamaClient()
        self.research = research or ResearchService(self.repository)
        self.intelligence = intelligence or ContinuousIntelligenceService(
            self.repository
        )
        self.progress = progress
        self.storage = StorageManager()
        self._snapshot: dict = {}
        self._current_stage = "prepare"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        hackathon: HackathonInput,
        options: PipelineOptions | None = None,
        *,
        session_id: str | None = None,
    ) -> PipelineResult:
        if hackathon.is_multi_track and hackathon.tracks:
            multi_result = self.run_multi_track(hackathon, options, session_id=session_id)
            comp = multi_result.comparison
            winning_tid = (
                comp.overall_winning_track.id
                if comp and comp.overall_winning_track
                else (hackathon.tracks[0].id if hackathon.tracks else None)
            )
            best_track_res = multi_result.track_results.get(winning_tid) if winning_tid else None
            return PipelineResult(
                session_id=multi_result.session_id,
                input=hackathon,
                intelligence=multi_result.shared_intelligence,
                domain_map=best_track_res.domain_map if best_track_res else None,
                innovation_report=best_track_res.innovation_report if best_track_res else None,
                feasibility=best_track_res.feasibility if best_track_res else None,
                debates=best_track_res.debates if best_track_res else [],
                winner=best_track_res.winner if best_track_res else None,
                report=multi_result.master_report,
                status=multi_result.status,
                started_at=multi_result.started_at,
                completed_at=multi_result.completed_at,
                duration_seconds=multi_result.duration_seconds,
            )

        options = options or PipelineOptions(
            max_domains=self.settings.agent.max_domains,
            problems_per_domain=self.settings.agent.problems_per_domain,
            max_finalists=self.settings.agent.max_finalists,
            max_debate_rounds=self.settings.agent.max_debate_rounds,
        )
        initialize_database(self.repository.db)
        self.storage.ensure_dirs()
        if not session_id:
            session_id = self.repository.create_session(
                theme=hackathon.theme,
                name=hackathon.name,
                website_url=hackathon.website_url,
                rules_url=hackathon.rules_url,
                deadline=hackathon.deadline.isoformat() if hackathon.deadline else None,
                constraints=hackathon.constraints,
                is_multi_track=False,
            )
        hackathon.session_id = session_id
        self.repository.update_session_status(session_id, "running")
        started = utc_now()
        initial: PipelineState = {
            "session_id": session_id,
            "hackathon": hackathon,
            "options": options,
            "started_at": started,
        }
        self._snapshot = dict(initial)
        try:
            graph = self._build_graph()
            final_state = graph.invoke(
                initial,
                config={"recursion_limit": 30},
            )
            self._snapshot.update(final_state)
            result = PipelineResult(
                session_id=session_id,
                input=hackathon,
                intelligence=final_state.get("intelligence"),
                domain_map=final_state.get("domain_map"),
                innovation_report=final_state.get("innovation_report"),
                feasibility=final_state.get("feasibility"),
                debates=(
                    final_state["final_evaluation"].debates
                    if final_state.get("final_evaluation")
                    else []
                ),
                winner=(
                    final_state["final_evaluation"].winner
                    if final_state.get("final_evaluation")
                    else None
                ),
                report=final_state.get("report"),
                status=(
                    "completed"
                    if final_state.get("final_evaluation")
                    and final_state["final_evaluation"].winner.has_winner
                    else "completed_no_winner"
                ),
                started_at=started,
            )
            result.finalize()
            self.repository.update_session_status(session_id, result.status)
            self.repository.save_agent_result(
                session_id,
                "orchestrator",
                "pipeline_summary",
                {
                    "status": result.status,
                    "duration_seconds": result.duration_seconds,
                    "has_winner": bool(result.winner and result.winner.has_winner),
                    "domains": (
                        result.domain_map.total_domains_explored
                        if result.domain_map
                        else 0
                    ),
                    "problems": (
                        result.domain_map.total_problems_found
                        if result.domain_map
                        else 0
                    ),
                },
            )
            self._emit("finalize", "Workflow completed", 1.0)
            return result
        except Exception as exc:
            logger.exception("Pipeline failed")
            self.repository.update_session_status(session_id, "failed")
            self.repository.save_agent_result(
                session_id,
                "orchestrator",
                "pipeline_error",
                {
                    "stage": self._current_stage,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            result = PipelineResult(
                session_id=session_id,
                input=hackathon,
                intelligence=self._snapshot.get("intelligence"),
                domain_map=self._snapshot.get("domain_map"),
                innovation_report=self._snapshot.get("innovation_report"),
                feasibility=self._snapshot.get("feasibility"),
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                started_at=started,
            )
            result.finalize()
            return result

    def run_multi_track(
        self,
        hackathon: HackathonInput,
        options: PipelineOptions | None = None,
        *,
        session_id: str | None = None,
    ) -> MultiTrackPipelineResult:
        """Execute complete multi-track research and cross-track evaluation."""
        options = options or PipelineOptions(
            max_domains=self.settings.agent.max_domains,
            problems_per_domain=self.settings.agent.problems_per_domain,
            max_finalists=self.settings.agent.max_finalists,
            max_debate_rounds=self.settings.agent.max_debate_rounds,
        )
        initialize_database(self.repository.db)
        self.storage.ensure_dirs()
        started = utc_now()

        if not session_id:
            session_id = self.repository.create_session(
                theme=hackathon.theme,
                name=hackathon.name,
                website_url=hackathon.website_url,
                rules_url=hackathon.rules_url,
                deadline=hackathon.deadline.isoformat() if hackathon.deadline else None,
                constraints=hackathon.constraints,
                is_multi_track=True,
                multi_track_mode=hackathon.multi_track_mode.value,
            )
        hackathon.session_id = session_id
        self.repository.save_tracks(session_id, hackathon.tracks)
        self.repository.update_session_status(session_id, "running")

        # 1. Shared Organizer Research (Agent 1 once)
        self._emit("shared_intelligence", "Agent 1 — Shared Hackathon Intelligence (once across all tracks)", 0.05)
        context = ""
        if options.include_continuous_intelligence:
            try:
                intel_ctx = self.intelligence.context_for_theme(hackathon.theme)
                context = self.intelligence.context_as_prompt(intel_ctx)
                self.repository.save_agent_result(
                    session_id,
                    "continuous_intelligence",
                    "reused_context",
                    intel_ctx.model_dump(mode="json"),
                )
            except Exception as exc:
                logger.warning(f"Continuous intelligence context failed: {exc}")

        shared_agent = HackathonIntelligenceAgent(
            self.llm, self.research, self.repository, self.settings.agent
        )
        shared_intelligence = shared_agent.run(
            session_id,
            hackathon,
            intelligence_context=context,
        )
        del shared_agent
        gc.collect()

        self.repository.save_agent_result(
            session_id,
            "shared_intelligence",
            "hackathon_intelligence",
            shared_intelligence.model_dump(mode="json"),
        )

        # 2. Sequential Track Research & Evaluation
        track_results: dict[str, TrackResult] = {}
        total_tracks = len(hackathon.tracks)
        report_generator = ReportGenerator(self.repository)

        for idx, track in enumerate(hackathon.tracks):
            track_start = utc_now()
            progress_frac = 0.10 + 0.75 * (idx / max(1, total_tracks))
            self._emit(
                f"track_{track.id}",
                f"Processing Track {idx + 1}/{total_tracks}: '{track.name}' (Sequential Resource-Safe Mode)",
                progress_frac,
            )

            # Build track-specific HackathonInput
            track_theme = f"{hackathon.theme} — Track: {track.name}"
            if track.description and track.description.strip():
                track_theme += f" ({track.description.strip()})"

            track_constraints = hackathon.constraints or ""
            if track.track_rules and track.track_rules.strip():
                track_constraints = f"{track_constraints}; Track Rules: {track.track_rules.strip()}".strip("; ")

            track_input = HackathonInput(
                theme=track_theme,
                name=hackathon.name,
                website_url=track.official_track_url or hackathon.website_url,
                rules_url=hackathon.rules_url,
                deadline=hackathon.deadline,
                constraints=track_constraints,
                session_id=session_id,
            )

            # Build track-specific HackathonIntelligence
            track_intel = shared_intelligence.model_copy(deep=True)
            track_intel.hackathon_input = track_input
            if track.track_rules and track.track_rules.strip():
                track_intel.technical_restrictions.append(f"Track constraint: {track.track_rules.strip()}")

            try:
                # Agent 2: Dynamic Domain Discovery tailored to this track
                d_agent = DomainDiscoveryAgent(
                    self.llm, self.research, self.repository, self.settings.agent
                )
                domain_map = d_agent.run(
                    session_id,
                    track_input.theme,
                    track_intel,
                    intelligence_context=context,
                    max_domains=options.max_domains,
                    domain_exploration_budget=options.domain_exploration_budget,
                    min_domain_relevance=options.min_domain_relevance,
                    problems_per_domain=options.problems_per_domain,
                )
                del d_agent
                gc.collect()

                # Agent 3: Global Innovation Research for this track
                problems = domain_map.problem_candidates if domain_map else []
                if problems:
                    i_agent = InnovationResearchAgent(
                        self.llm, self.research, self.repository, self.settings.agent
                    )
                    innovation = i_agent.run(
                        session_id,
                        problems,
                        theme=track_input.theme,
                        intelligence_context=context,
                    )
                    del i_agent
                    gc.collect()
                else:
                    innovation = InnovationReport()

                # Agent 4: Solution Architecture for this track
                if problems:
                    s_agent = SolutionArchitectAgent(
                        self.llm, self.research, self.repository, self.settings.agent
                    )
                    feasibility = s_agent.run(
                        session_id,
                        problems,
                        innovation.gaps if innovation else [],
                        track_input,
                        track_intel,
                        max_finalists=options.max_finalists,
                        intelligence_context=context,
                    )
                    del s_agent
                    gc.collect()
                else:
                    feasibility = FeasibilityReport()

                # Agent 5: Adversarial Debate & 10 Mandatory Quality Gates
                candidates = feasibility.candidates if feasibility else []
                if candidates:
                    c_agent = AdversarialCriticAgent(
                        self.llm,
                        self.research,
                        self.repository,
                        self.settings.agent,
                    )
                    final_eval = c_agent.run(
                        session_id,
                        candidates,
                        problems,
                        innovation.gaps if innovation else [],
                        track_input,
                        track_intel,
                        max_rounds=options.max_debate_rounds,
                    )
                    del c_agent
                    gc.collect()
                else:
                    final_eval = FinalEvaluationReport(
                        winner=WinnerSelection(
                            has_winner=False,
                            rejection_reason=f"No feasible candidate survived in track '{track.name}'.",
                            selection_methodology="No finalists generated for this track.",
                        ),
                        scoring_methodology="No finalists to score.",
                    )

                track_elapsed = (utc_now() - track_start).total_seconds()

                # Build Track PipelineResult to generate 24-section track report
                track_pipe_res = PipelineResult(
                    session_id=session_id,
                    input=track_input,
                    intelligence=track_intel,
                    domain_map=domain_map,
                    innovation_report=innovation,
                    feasibility=feasibility,
                    debates=final_eval.debates,
                    winner=final_eval.winner,
                    status="completed" if (final_eval.winner and final_eval.winner.has_winner) else "completed_no_winner",
                    started_at=track_start,
                )
                track_pipe_res.finalize()

                track_report = report_generator.generate(
                    track_pipe_res, final_eval, track_id=track.id
                )
                track_report_path = f"data/reports/{track_report.metadata.report_id}.md"

                track_res = TrackResult(
                    track=track,
                    input=track_input,
                    domain_map=domain_map,
                    innovation_report=innovation,
                    feasibility=feasibility,
                    debates=final_eval.debates,
                    winner=final_eval.winner,
                    report=track_report,
                    report_path=track_report_path,
                    status=track_pipe_res.status,
                    duration_seconds=track_elapsed,
                )
                track_results[track.id] = track_res

                # Persist intermediate track summary to repository
                self.repository.save_agent_result(
                    session_id,
                    f"track_{track.id}",
                    "track_summary",
                    {
                        "track_id": track.id,
                        "track_name": track.name,
                        "status": track_res.status,
                        "has_winner": bool(final_eval.winner and final_eval.winner.has_winner),
                        "duration_seconds": track_elapsed,
                    },
                )

            except Exception as exc:
                logger.exception(f"Track '{track.name}' ({track.id}) encountered an error")
                track_elapsed = (utc_now() - track_start).total_seconds()
                track_results[track.id] = TrackResult(
                    track=track,
                    input=track_input,
                    status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                    duration_seconds=track_elapsed,
                )
                self.repository.save_agent_result(
                    session_id,
                    f"track_{track.id}",
                    "track_error",
                    {"error": str(exc), "error_type": type(exc).__name__},
                )

            # Garbage collect between tracks to ensure memory remains stable
            gc.collect()

        # 3. Cross-Track Comparison Engine
        self._emit("cross_track_comparison", "Evaluating and ranking candidates across all tracks", 0.90)
        comparison_engine = CrossTrackComparisonEngine()
        comparison_result = comparison_engine.compare(
            track_results=track_results,
            mode=hackathon.multi_track_mode,
            shared_intelligence=shared_intelligence,
        )

        # Persist comparison to DB
        winning_tid = (
            comparison_result.overall_winning_track.id
            if comparison_result.overall_winning_track
            else None
        )
        winning_cid = (
            comparison_result.overall_winning_candidate.id
            if comparison_result.overall_winning_candidate
            else None
        )
        self.repository.save_multi_track_comparison(
            session_id=session_id,
            mode=hackathon.multi_track_mode.value,
            winning_track_id=winning_tid,
            winning_candidate_id=winning_cid,
            comparison_data=comparison_result.model_dump(mode="json"),
        )

        # 4. Master Multi-Track Report Generation
        self._emit("master_report", "Generating master cross-track comparison report", 0.95)
        has_any_winner = bool(
            comparison_result.overall_winning_candidate
            or any(w for w in comparison_result.per_track_winners.values())
        )
        overall_status = "completed" if has_any_winner else "completed_no_winner"

        multi_result = MultiTrackPipelineResult(
            session_id=session_id,
            input=hackathon,
            shared_intelligence=shared_intelligence,
            track_results=track_results,
            comparison=comparison_result,
            status=overall_status,
            started_at=started,
        )
        master_report = report_generator.generate_multi_track_report(multi_result)
        multi_result.master_report = master_report
        multi_result.master_report_path = f"data/reports/{master_report.metadata.report_id}.md"
        multi_result.finalize()

        self.repository.update_session_status(session_id, multi_result.status)
        self._emit("finalize", "Multi-track hackathon research completed", 1.0)
        return multi_result


    # ------------------------------------------------------------------
    # Graph
    # ------------------------------------------------------------------

    def _build_graph(self):
        graph = StateGraph(PipelineState)
        graph.add_node("prepare", self._prepare)
        graph.add_node("hackathon_intelligence", self._hackathon_intelligence)
        graph.add_node("domain_discovery", self._domain_discovery)
        graph.add_node("innovation_research", self._innovation_research)
        graph.add_node("solution_architecture", self._solution_architecture)
        graph.add_node("adversarial_evaluation", self._adversarial_evaluation)
        graph.add_node("report", self._report)
        graph.add_node("finalize", self._finalize)

        graph.set_entry_point("prepare")
        graph.add_edge("prepare", "hackathon_intelligence")
        graph.add_edge("hackathon_intelligence", "domain_discovery")
        graph.add_edge("domain_discovery", "innovation_research")
        graph.add_edge("innovation_research", "solution_architecture")
        graph.add_edge("solution_architecture", "adversarial_evaluation")
        graph.add_edge("adversarial_evaluation", "report")
        graph.add_edge("report", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _emit(self, stage: str, message: str, fraction: float | None = None) -> None:
        self._current_stage = stage
        if fraction is None:
            fraction = STAGES.get(stage, (0.0, ""))[0]
        logger.info("[%s] %s", stage, message)
        if self.progress:
            try:
                self.progress(stage, message, fraction)
            except Exception:
                logger.exception("Progress callback failed")

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def _prepare(self, state: PipelineState) -> dict:
        self._emit("prepare", STAGES["prepare"][1])
        context = ""
        note = "Continuous Intelligence disabled for this run."
        if state["options"].include_continuous_intelligence:
            try:
                intel_context = self.intelligence.context_for_theme(
                    state["hackathon"].theme
                )
                context = self.intelligence.context_as_prompt(intel_context)
                note = intel_context.note
                self.repository.save_agent_result(
                    state["session_id"],
                    "continuous_intelligence",
                    "reused_context",
                    intel_context.model_dump(mode="json"),
                )
            except Exception as exc:  # noqa: BLE001 - optional enrichment
                logger.warning("Continuous intelligence context failed: %s", exc)
                note = f"Continuous intelligence unavailable: {exc}"
        return {
            "intelligence_context": context,
            "continuous_intelligence_note": note,
        }

    def _hackathon_intelligence(self, state: PipelineState) -> dict:
        self._emit("hackathon_intelligence", STAGES["hackathon_intelligence"][1])
        agent = HackathonIntelligenceAgent(
            self.llm, self.research, self.repository, self.settings.agent
        )
        intelligence = agent.run(
            state["session_id"],
            state["hackathon"],
            intelligence_context=state.get("intelligence_context", ""),
        )
        del agent
        gc.collect()
        return {"intelligence": intelligence}

    def _domain_discovery(self, state: PipelineState) -> dict:
        self._emit("domain_discovery", STAGES["domain_discovery"][1])
        agent = DomainDiscoveryAgent(
            self.llm, self.research, self.repository, self.settings.agent
        )
        opts = state["options"]
        domain_map = agent.run(
            state["session_id"],
            state["hackathon"].theme,
            state["intelligence"],
            intelligence_context=state.get("intelligence_context", ""),
            max_domains=opts.max_domains,
            domain_exploration_budget=getattr(opts, "domain_exploration_budget", None),
            min_domain_relevance=getattr(opts, "min_domain_relevance", None),
            problems_per_domain=opts.problems_per_domain,
        )
        del agent
        gc.collect()
        return {"domain_map": domain_map}

    def _innovation_research(self, state: PipelineState) -> dict:
        self._emit("innovation_research", STAGES["innovation_research"][1])
        domain_map = state.get("domain_map")
        problems = domain_map.problem_candidates if domain_map else []
        if not problems:
            report = InnovationReport()
            self.repository.save_agent_result(
                state["session_id"],
                "innovation_research",
                "innovation_report",
                report.model_dump(mode="json"),
            )
            return {"innovation_report": report}
        agent = InnovationResearchAgent(
            self.llm, self.research, self.repository, self.settings.agent
        )
        report = agent.run(
            state["session_id"],
            problems,
            theme=state["hackathon"].theme,
            intelligence_context=state.get("intelligence_context", ""),
        )
        del agent
        gc.collect()
        return {"innovation_report": report}

    def _solution_architecture(self, state: PipelineState) -> dict:
        self._emit("solution_architecture", STAGES["solution_architecture"][1])
        domain_map = state.get("domain_map")
        innovation = state.get("innovation_report")
        problems = domain_map.problem_candidates if domain_map else []
        if not problems:
            report = FeasibilityReport()
            self.repository.save_agent_result(
                state["session_id"],
                "solution_architect",
                "feasibility_report",
                report.model_dump(mode="json"),
            )
            return {"feasibility": report}
        agent = SolutionArchitectAgent(
            self.llm, self.research, self.repository, self.settings.agent
        )
        feasibility = agent.run(
            state["session_id"],
            problems,
            innovation.gaps if innovation else [],
            state["hackathon"],
            state["intelligence"],
            max_finalists=state["options"].max_finalists,
            intelligence_context=state.get("intelligence_context", ""),
        )
        del agent
        gc.collect()
        return {"feasibility": feasibility}

    def _adversarial_evaluation(self, state: PipelineState) -> dict:
        self._emit("adversarial_evaluation", STAGES["adversarial_evaluation"][1])
        feasibility = state.get("feasibility")
        domain_map = state.get("domain_map")
        innovation = state.get("innovation_report")
        candidates = feasibility.candidates if feasibility else []
        if not candidates:
            final = FinalEvaluationReport(
                winner=WinnerSelection(
                    has_winner=False,
                    rejection_reason=(
                        "No feasible candidate survived solution architecture; "
                        "HackathonIQ will not invent one."
                    ),
                    selection_methodology="No finalists to evaluate.",
                ),
                scoring_methodology="No finalists to score.",
            )
            self.repository.save_agent_result(
                state["session_id"],
                "adversarial_critic",
                "final_evaluation",
                final.model_dump(mode="json"),
            )
            return {"final_evaluation": final}
        agent = AdversarialCriticAgent(
            self.llm, self.research, self.repository, self.settings.agent
        )
        final = agent.run(
            state["session_id"],
            candidates,
            domain_map.problem_candidates if domain_map else [],
            innovation.gaps if innovation else [],
            state["hackathon"],
            state["intelligence"],
            max_rounds=state["options"].max_debate_rounds,
        )
        del agent
        gc.collect()
        return {"final_evaluation": final}

    def _report(self, state: PipelineState) -> dict:
        self._emit("report", STAGES["report"][1])
        final = state["final_evaluation"]
        started = state.get("started_at") or utc_now()
        result = PipelineResult(
            session_id=state["session_id"],
            input=state["hackathon"],
            intelligence=state.get("intelligence"),
            domain_map=state.get("domain_map"),
            innovation_report=state.get("innovation_report"),
            feasibility=state.get("feasibility"),
            debates=final.debates,
            winner=final.winner,
            started_at=started,
        )
        # Report metadata uses the real elapsed duration from session start.
        result.completed_at = utc_now()
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()
        generator = ReportGenerator(self.repository)
        report = generator.generate(
            result,
            final,
            continuous_intelligence_note=state.get("continuous_intelligence_note", ""),
            model_name=getattr(self.llm, "model_name", lambda: "test-model")(),
            llm_stats=(self.llm.stats.as_dict() if hasattr(self.llm, "stats") else {}),
        )
        return {"report": report}

    def _finalize(self, state: PipelineState) -> dict:
        self._emit("finalize", STAGES["finalize"][1], 1.0)
        if hasattr(self.research, "close"):
            try:
                self.research.close()
            except Exception:
                pass
        if hasattr(self.llm, "close"):
            try:
                self.llm.close()
            except Exception:
                pass
        gc.collect()
        return {}
