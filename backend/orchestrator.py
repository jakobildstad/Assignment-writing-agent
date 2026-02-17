"""
Orchestrator — LangGraph stateful graph that runs the full pipeline:

    START → searcher → writer → critic → evaluator ─┐
                ↑                                     │
                └── writer (revise) ← (if rejected) ──┘
                                       (if approved) → END

Supports stagnation detection: when the writer makes cosmetic-only
changes, the evaluator flags stagnation and the writer switches to
"restructure" mode for a fundamentally different approach.

Emits structured events via the progress callback:
    agent_start, agent_complete, draft_ready, critique_ready,
    revision_start, stagnation, tokens, complete, error
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine

from langgraph.graph import END, START, StateGraph
from loguru import logger
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from agents.critic import CritiqueResult, format_feedback_for_writer, run_critic
from agents.evaluator import EvalDecision, evaluate
from agents.searcher import SourceBundle, run_searcher
from agents.writer import EssayDraft, WriterConfig, run_writer
from config import EVALUATOR_DEFAULTS
from llm import TokenUsage
from rag import ingest, get_embeddings
import session as session_store

# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[dict], Coroutine[Any, Any, None]]


class PipelineState(TypedDict, total=False):
    # Inputs
    task: str
    session_id: str          # UUID for session persistence
    session_dir: str
    writer_config: dict
    evaluator_config: dict

    # Pipeline data
    sources: dict            # SourceBundle.model_dump()
    current_draft: dict      # EssayDraft.model_dump()
    critique: dict           # CritiqueResult.model_dump()
    eval_decision: dict      # EvalDecision.model_dump()
    feedback: str            # formatted feedback for writer

    # Version history (for diff-based evaluation)
    draft_history: list[dict]       # all EssayDraft versions
    critique_history: list[dict]    # all CritiqueResult versions

    # Stagnation tracking
    stagnation_count: int           # number of consecutive stagnations
    writer_mode: str                # "revise" or "restructure"
    unresolved_issues: list[str]    # from evaluator for restructure prompt

    # Bookkeeping
    iteration: int
    progress_log: list[str]
    status: str              # "running" | "completed" | "error"
    error: str

    # Token / cost tracking
    token_usage: list[dict]  # list of TokenUsage.to_dict()
    total_cost_usd: float


# ---------------------------------------------------------------------------
# Progress helper
# ---------------------------------------------------------------------------

# Module-level callback registry (set per-run)
_progress_callbacks: dict[str, ProgressCallback] = {}


async def _emit(state: PipelineState, event: dict) -> PipelineState:
    """Emit a structured event via the registered callback and persist to disk."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    event["timestamp"] = timestamp

    # Also keep a human-readable log entry
    log = list(state.get("progress_log", []))
    log.append(f"[{timestamp}] {event.get('message', event.get('event', ''))}")

    new_state = {**state, "progress_log": log}

    # Persist session to disk
    sid = state.get("session_id", "")
    if sid:
        session_store.save(sid, new_state)

    # Fire the callback if registered
    session_dir = state.get("session_dir", "")
    cb = _progress_callbacks.get(session_dir)
    if cb:
        try:
            await cb(event)
        except Exception:
            pass

    return new_state


def _accumulate_tokens(state: PipelineState, usage: TokenUsage) -> PipelineState:
    """Add a TokenUsage entry to the pipeline state and update total cost."""
    usage_list = list(state.get("token_usage", []))
    usage_list.append(usage.to_dict())
    total_cost = sum(u.get("cost_usd", 0) for u in usage_list)
    return {**state, "token_usage": usage_list, "total_cost_usd": total_cost}


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


async def search_node(state: PipelineState) -> PipelineState:
    """Run the searcher agent to gather sources from pensum and web."""
    state = await _emit(state, {
        "event": "agent_start",
        "agent": "searcher",
        "message": "Søker i pensum og på nettet...",
    })

    task = state["task"]
    session_dir = state.get("session_dir", "")

    # Ingest documents if session_dir is provided
    if session_dir and Path(session_dir).exists():
        try:
            emb = get_embeddings()
            ingest(session_dir, embeddings=emb)
            state = await _emit(state, {
                "event": "progress",
                "agent": "searcher",
                "message": f"Dokumenter indeksert fra {session_dir}",
            })
        except Exception as e:
            logger.warning("Failed to ingest documents: {}", str(e)[:200])
            state = await _emit(state, {
                "event": "progress",
                "agent": "searcher",
                "message": f"Kunne ikke indeksere dokumenter: {e}",
            })

    sources, usage = await run_searcher(task)
    state = _accumulate_tokens(state, usage)

    state = await _emit(state, {
        "event": "agent_complete",
        "agent": "searcher",
        "message": (
            f"Fant {len(sources.pensum_sources)} pensum-kilder "
            f"og {len(sources.web_sources)} nettkilder"
        ),
        "data": {
            "pensum_count": len(sources.pensum_sources),
            "web_count": len(sources.web_sources),
            "summary": sources.summary,
        },
    })

    # Emit token event
    state = await _emit(state, {
        "event": "tokens",
        "agent": "searcher",
        **usage.to_dict(),
        "total_cost_usd": state.get("total_cost_usd", 0),
        "message": f"Søker: {usage.input_tokens}+{usage.output_tokens} tokens (${usage.cost_usd:.4f})",
    })

    return {**state, "sources": sources.model_dump(), "status": "running"}


async def write_node(state: PipelineState) -> PipelineState:
    """Run the writer agent to produce or revise a draft."""
    iteration = state.get("iteration", 1)
    is_revision = iteration > 1
    writer_mode = state.get("writer_mode", "revise")

    if is_revision:
        if writer_mode == "restructure":
            state = await _emit(state, {
                "event": "stagnation",
                "agent": "writer",
                "iteration": iteration,
                "message": "Score-stagnasjon detektert — skriveren restrukturerer essayet...",
            })
        else:
            feedback_summary = state.get("feedback", "")[:200]
            state = await _emit(state, {
                "event": "revision_start",
                "agent": "writer",
                "iteration": iteration,
                "message": f"Reviderer utkast (iterasjon {iteration})...",
                "feedback_summary": feedback_summary,
            })
    else:
        state = await _emit(state, {
            "event": "agent_start",
            "agent": "writer",
            "message": "Skriver førsteutkast...",
        })

    sources = SourceBundle(**state["sources"])
    writer_config = WriterConfig(**state.get("writer_config", {}))

    # Build revision context
    feedback = state.get("feedback")
    previous_draft = None
    if is_revision and state.get("current_draft"):
        previous_draft = EssayDraft(**state["current_draft"])

    draft, usage = await run_writer(
        task=state["task"],
        sources=sources,
        feedback=feedback,
        previous_draft=previous_draft,
        writer_config=writer_config,
        mode=writer_mode,
        unresolved_issues=state.get("unresolved_issues"),
    )
    state = _accumulate_tokens(state, usage)

    # Warn frontend if output was truncated
    if usage.was_truncated:
        state = await _emit(state, {
            "event": "warning",
            "agent": "writer",
            "message": (
                f"Skriver-output ble trunkert ({usage.output_tokens} tokens). "
                f"Prøvde igjen med høyere grense. Resultatet kan være ufullstendig."
            ),
        })

    draft_data = draft.model_dump()

    # Append to draft history
    draft_history = list(state.get("draft_history", []))
    draft_history.append(draft_data)

    state = await _emit(state, {
        "event": "draft_ready",
        "agent": "writer",
        "iteration": iteration,
        "message": f"Utkast ferdig: «{draft.title}» ({draft.word_count} ord)",
        "draft": draft_data,
        "mode": writer_mode,
    })

    # Emit token event
    state = await _emit(state, {
        "event": "tokens",
        "agent": "writer",
        **usage.to_dict(),
        "total_cost_usd": state.get("total_cost_usd", 0),
        "message": f"Skriver: {usage.input_tokens}+{usage.output_tokens} tokens (${usage.cost_usd:.4f})",
    })

    return {
        **state,
        "current_draft": draft_data,
        "draft_history": draft_history,
        # Reset writer mode after use
        "writer_mode": "revise",
    }


async def critic_node(state: PipelineState) -> PipelineState:
    """Run the critic agent to evaluate the current draft (blind — no history)."""
    iteration = state.get("iteration", 1)

    state = await _emit(state, {
        "event": "agent_start",
        "agent": "critic",
        "message": "Evaluerer utkast...",
    })

    draft = EssayDraft(**state["current_draft"])
    sources = SourceBundle(**state["sources"])

    # Critic is BLIND — only gets task, draft, and sources.
    # No critique_history, no previous scores.
    critique, usage = await run_critic(state["task"], draft, sources)
    state = _accumulate_tokens(state, usage)

    # Warn frontend if output was truncated
    if usage.was_truncated:
        state = await _emit(state, {
            "event": "warning",
            "agent": "critic",
            "message": (
                f"Kritiker-output ble trunkert ({usage.output_tokens} tokens). "
                f"Prøvde igjen med høyere grense. Feedback kan være ufullstendig."
            ),
        })

    # Append to critique history
    critique_history = list(state.get("critique_history", []))
    critique_data = critique.model_dump()
    critique_history.append(critique_data)

    state = await _emit(state, {
        "event": "critique_ready",
        "agent": "critic",
        "iteration": iteration,
        "message": (
            f"Evaluering ferdig — score: {critique.score}/10 "
            f"({len(critique.strengths)} styrker, {len(critique.weaknesses)} svakheter)"
        ),
        "critique": critique_data,
    })

    # Emit token event
    state = await _emit(state, {
        "event": "tokens",
        "agent": "critic",
        **usage.to_dict(),
        "total_cost_usd": state.get("total_cost_usd", 0),
        "message": f"Kritiker: {usage.input_tokens}+{usage.output_tokens} tokens (${usage.cost_usd:.4f})",
    })

    return {
        **state,
        "critique": critique_data,
        "critique_history": critique_history,
    }


async def evaluator_node(state: PipelineState) -> PipelineState:
    """Decide whether the draft is approved or needs revision."""
    critique = CritiqueResult(**state["critique"])
    iteration = state.get("iteration", 1)
    eval_cfg = state.get("evaluator_config", {})

    # Get previous critique and draft for diff-based evaluation
    critique_history = state.get("critique_history", [])
    draft_history = state.get("draft_history", [])

    previous_critique = None
    previous_draft = None
    if len(critique_history) >= 2:
        previous_critique = CritiqueResult(**critique_history[-2])
    if len(draft_history) >= 2:
        previous_draft = EssayDraft(**draft_history[-2])

    current_draft = EssayDraft(**state["current_draft"]) if state.get("current_draft") else None

    decision = evaluate(
        critique,
        iteration=iteration,
        score_threshold=eval_cfg.get("score_threshold"),
        max_iterations=eval_cfg.get("max_iterations"),
        previous_critique=previous_critique,
        previous_draft=previous_draft,
        current_draft=current_draft,
    )

    stagnation_count = state.get("stagnation_count", 0)

    if decision.approved:
        # ── Approved ─────────────────────────────────────────────
        # If stagnation forced approval at max iterations, pick best draft
        final_draft = state.get("current_draft", {})
        if decision.stagnation_detected and len(critique_history) >= 2:
            # Find the draft with the best score
            best_idx = 0
            best_score = 0.0
            for i, ch in enumerate(critique_history):
                if ch.get("score", 0) > best_score:
                    best_score = ch["score"]
                    best_idx = i
            if best_idx < len(draft_history):
                final_draft = draft_history[best_idx]
                logger.info(
                    "Evaluator: stagnation at max — using best draft v{} (score {:.1f})",
                    best_idx + 1, best_score,
                )

        state = await _emit(state, {
            "event": "complete",
            "message": f"Godkjent! {decision.reason}",
            "final_draft": final_draft,
            "critique_history": critique_history,
            "iteration": iteration,
            "score": critique.score,
            "token_usage": state.get("token_usage", []),
            "total_cost_usd": state.get("total_cost_usd", 0),
            "improvements_found": decision.improvements_found,
            "unresolved_issues": decision.unresolved_issues,
        })
        return {
            **state,
            "eval_decision": decision.model_dump(),
            "status": "completed",
        }

    else:
        # ── Not approved — determine revision strategy ───────────
        feedback = format_feedback_for_writer(critique)
        writer_mode = "revise"
        unresolved = decision.unresolved_issues

        if decision.stagnation_detected:
            stagnation_count += 1

            if stagnation_count >= 2:
                # Stagnated twice — force approve with best version
                best_idx = 0
                best_score = 0.0
                for i, ch in enumerate(critique_history):
                    if ch.get("score", 0) > best_score:
                        best_score = ch["score"]
                        best_idx = i
                final_draft = draft_history[best_idx] if best_idx < len(draft_history) else state.get("current_draft", {})

                logger.warning(
                    "Evaluator: double stagnation — force-approving best v{} (score {:.1f})",
                    best_idx + 1, best_score,
                )

                state = await _emit(state, {
                    "event": "complete",
                    "message": (
                        f"Stagnasjon etter {iteration} forsøk — leverer beste versjon "
                        f"(v{best_idx + 1}, score {best_score}/10)."
                    ),
                    "final_draft": final_draft,
                    "critique_history": critique_history,
                    "iteration": iteration,
                    "score": best_score,
                    "token_usage": state.get("token_usage", []),
                    "total_cost_usd": state.get("total_cost_usd", 0),
                    "stagnation": True,
                })
                return {
                    **state,
                    "eval_decision": {**decision.model_dump(), "approved": True},
                    "status": "completed",
                }

            # First stagnation — switch to restructure mode
            writer_mode = "restructure"
            state = await _emit(state, {
                "event": "agent_complete",
                "agent": "evaluator",
                "message": (
                    f"Stagnasjon detektert (iterasjon {iteration}). "
                    f"Krever restrukturering — skriveren prøver ny tilnærming."
                ),
                "approved": False,
                "stagnation": True,
                "reason": decision.reason,
                "next_iteration": iteration + 1,
                "unresolved_issues": unresolved,
            })
        else:
            # Normal rejection
            stagnation_count = 0  # Reset on genuine progress
            state = await _emit(state, {
                "event": "agent_complete",
                "agent": "evaluator",
                "message": f"Trenger revisjon (iterasjon {iteration}). {decision.reason}",
                "approved": False,
                "reason": decision.reason,
                "next_iteration": iteration + 1,
                "improvements_found": decision.improvements_found,
            })

        return {
            **state,
            "eval_decision": decision.model_dump(),
            "feedback": feedback,
            "iteration": iteration + 1,
            "stagnation_count": stagnation_count,
            "writer_mode": writer_mode,
            "unresolved_issues": unresolved,
        }


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def should_revise(state: PipelineState) -> str:
    """Route after evaluator: go back to writer or finish."""
    decision = state.get("eval_decision", {})
    if decision.get("approved", False):
        return "end"
    return "revise"


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    """Construct and compile the orchestrator graph."""
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("searcher", search_node)
    graph.add_node("writer", write_node)
    graph.add_node("critic", critic_node)
    graph.add_node("evaluator", evaluator_node)

    # Edges: START → searcher → writer → critic → evaluator
    graph.add_edge(START, "searcher")
    graph.add_edge("searcher", "writer")
    graph.add_edge("writer", "critic")
    graph.add_edge("critic", "evaluator")

    # Conditional: evaluator → END or back to writer
    graph.add_conditional_edges(
        "evaluator",
        should_revise,
        {
            "end": END,
            "revise": "writer",
        },
    )

    return graph.compile()


# Pre-compiled graph instance
pipeline_graph = build_graph()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_pipeline(
    task: str,
    session_id: str = "",
    session_dir: str = "",
    writer_config: dict | None = None,
    evaluator_config: dict | None = None,
    on_progress: ProgressCallback | None = None,
) -> dict:
    """
    Run the full exphil agent pipeline.

    Args:
        task: The assignment/exam question text.
        session_id: UUID for session persistence.
        session_dir: Path to uploaded files for this session.
        writer_config: WriterConfig overrides (max_words, style, etc.).
        evaluator_config: Evaluator overrides (score_threshold, max_iterations).
        on_progress: Async callback for structured event dicts.

    Returns:
        The final PipelineState dict with draft, critique history, token usage, etc.
    """
    # Register progress callback
    if on_progress:
        _progress_callbacks[session_dir] = on_progress

    logger.info("Pipeline starting: task='{}' session_id='{}' session_dir='{}'", task[:80], session_id, session_dir)

    initial_state: PipelineState = {
        "task": task,
        "session_id": session_id,
        "session_dir": session_dir,
        "writer_config": writer_config or {},
        "evaluator_config": evaluator_config or EVALUATOR_DEFAULTS,
        "sources": {},
        "current_draft": {},
        "critique": {},
        "eval_decision": {},
        "feedback": "",
        "draft_history": [],
        "critique_history": [],
        "stagnation_count": 0,
        "writer_mode": "revise",
        "unresolved_issues": [],
        "iteration": 1,
        "progress_log": [],
        "status": "running",
        "error": "",
        "token_usage": [],
        "total_cost_usd": 0.0,
    }

    try:
        result = await pipeline_graph.ainvoke(initial_state)
        logger.info(
            "Pipeline completed: status={} iterations={} cost=${:.4f}",
            result.get("status"), result.get("iteration"),
            result.get("total_cost_usd", 0),
        )
        return result
    except Exception as e:
        error_msg = f"Pipeline error: {e}"
        logger.error("Pipeline failed: {}", str(e)[:500])
        if on_progress:
            await on_progress({
                "event": "error",
                "message": error_msg,
                "token_usage": initial_state.get("token_usage", []),
                "total_cost_usd": initial_state.get("total_cost_usd", 0),
            })
        return {**initial_state, "status": "error", "error": error_msg}
    finally:
        _progress_callbacks.pop(session_dir, None)
