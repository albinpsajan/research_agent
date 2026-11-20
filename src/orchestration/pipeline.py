"""LangGraph orchestration for the complete HackathonIQ workflow."""

from __future__ import annotations

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
from src.intelligence.service import ContinuousIntelligenceService
from src.llm.client import LLMClientProtocol, OllamaClient
from src.models.candidate import FeasibilityReport
from src.models.evaluation import FinalEvaluationReport, WinnerSelection
from src.models.hackathon import HackathonInput
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
        return {}
