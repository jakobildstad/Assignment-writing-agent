"""
Evaluator agent — decides whether an essay draft is good enough
or needs another revision cycle.

Performs three checks:
  1. Threshold check — is the score above the approval threshold?
  2. Stagnation detection — is the writer stuck making cosmetic changes?
  3. Improvement analysis — which specific weaknesses were addressed?
"""

from __future__ import annotations

from difflib import SequenceMatcher

from loguru import logger
from pydantic import BaseModel, Field

from agents.critic import CritiqueResult
from agents.writer import EssayDraft
from config import EVALUATOR_DEFAULTS

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

STAGNATION_SCORE_DELTA = 0.3  # scores within ±0.3 are considered "same"
STAGNATION_SIMILARITY_THRESHOLD = 0.6  # weakness overlap ratio to confirm stagnation


class EvalDecision(BaseModel):
    approved: bool = Field(description="Whether the essay is good enough")
    reason: str = Field(description="Explanation of the decision")
    iteration: int = Field(description="Current iteration number")
    stagnation_detected: bool = Field(
        default=False,
        description="Whether the writer is stuck making cosmetic changes",
    )
    improvements_found: list[str] = Field(
        default_factory=list,
        description="Which previous weaknesses were addressed in this revision",
    )
    unresolved_issues: list[str] = Field(
        default_factory=list,
        description="Which previous weaknesses remain unaddressed",
    )


# ---------------------------------------------------------------------------
# Stagnation detection helpers
# ---------------------------------------------------------------------------


def _weakness_overlap(prev_weaknesses: list[str], curr_weaknesses: list[str]) -> float:
    """
    Compute how much the weakness lists overlap using fuzzy string matching.
    Returns a ratio 0.0-1.0 where 1.0 means identical weaknesses.
    """
    if not prev_weaknesses or not curr_weaknesses:
        return 0.0

    matches = 0
    for pw in prev_weaknesses:
        for cw in curr_weaknesses:
            # Fuzzy match — two weaknesses describing the same problem
            # may be phrased slightly differently
            ratio = SequenceMatcher(None, pw.lower(), cw.lower()).ratio()
            if ratio > 0.5:
                matches += 1
                break

    return matches / len(prev_weaknesses) if prev_weaknesses else 0.0


def _find_improvements(
    prev_weaknesses: list[str],
    curr_weaknesses: list[str],
) -> tuple[list[str], list[str]]:
    """
    Compare previous and current weaknesses to find what was improved
    and what remains unresolved.

    Returns:
        (improvements_found, unresolved_issues)
    """
    improvements: list[str] = []
    unresolved: list[str] = []

    for pw in prev_weaknesses:
        still_present = False
        for cw in curr_weaknesses:
            ratio = SequenceMatcher(None, pw.lower(), cw.lower()).ratio()
            if ratio > 0.5:
                still_present = True
                break
        if still_present:
            unresolved.append(pw)
        else:
            improvements.append(pw)

    return improvements, unresolved


def _body_similarity(prev_draft: EssayDraft | None, curr_draft: EssayDraft | None) -> float:
    """
    Check how similar two draft bodies are. High similarity (>0.9) combined
    with same score strongly indicates cosmetic-only changes.
    """
    if not prev_draft or not curr_draft:
        return 0.0
    return SequenceMatcher(None, prev_draft.body, curr_draft.body).ratio()


# ---------------------------------------------------------------------------
# Evaluator logic
# ---------------------------------------------------------------------------


def evaluate(
    critique: CritiqueResult,
    iteration: int,
    score_threshold: float | None = None,
    max_iterations: int | None = None,
    previous_critique: CritiqueResult | None = None,
    previous_draft: EssayDraft | None = None,
    current_draft: EssayDraft | None = None,
) -> EvalDecision:
    """
    Decide whether the essay passes or needs revision.

    Performs three checks:
      1. Threshold — score meets the target
      2. Max iterations — forced approval with best version
      3. Stagnation — writer is stuck (same score + same weaknesses)

    Args:
        critique: The current CritiqueResult from the critic agent.
        iteration: Current iteration number (1-based).
        score_threshold: Minimum score for approval.
        max_iterations: Maximum revision cycles allowed.
        previous_critique: The CritiqueResult from the previous iteration (None for first).
        previous_draft: The EssayDraft from the previous iteration (None for first).
        current_draft: The current EssayDraft being evaluated.
    """
    score_threshold = score_threshold or EVALUATOR_DEFAULTS["score_threshold"]
    max_iterations = max_iterations or EVALUATOR_DEFAULTS["max_iterations"]

    # ── Diff analysis (iteration >= 2) ───────────────────────────
    improvements: list[str] = []
    unresolved: list[str] = []
    stagnation = False

    if iteration >= 2 and previous_critique:
        improvements, unresolved = _find_improvements(
            previous_critique.weaknesses,
            critique.weaknesses,
        )

        # Stagnation detection: score within ±delta AND high weakness overlap
        score_delta = abs(critique.score - previous_critique.score)
        weakness_overlap = _weakness_overlap(
            previous_critique.weaknesses,
            critique.weaknesses,
        )
        body_sim = _body_similarity(previous_draft, current_draft)

        logger.info(
            "Evaluator diff: score_delta={:.1f} weakness_overlap={:.2f} "
            "body_sim={:.2f} improvements={} unresolved={}",
            score_delta, weakness_overlap, body_sim,
            len(improvements), len(unresolved),
        )

        # Stagnation = similar score + same weaknesses OR nearly identical text
        if score_delta <= STAGNATION_SCORE_DELTA and (
            weakness_overlap >= STAGNATION_SIMILARITY_THRESHOLD
            or body_sim > 0.92
        ):
            stagnation = True
            logger.warning(
                "Evaluator: stagnation detected at iteration {} "
                "(delta={:.1f}, overlap={:.2f}, body_sim={:.2f})",
                iteration, score_delta, weakness_overlap, body_sim,
            )

    # ── Weighted score (independence matters) ────────────────────
    independence = getattr(critique, "independence_score", 5.0)
    weighted_score = round(critique.score * 0.7 + independence * 0.3, 1)

    logger.info(
        "Evaluator: score={} independence={} weighted={}",
        critique.score, independence, weighted_score,
    )

    # ── Max iterations — forced approval ─────────────────────────
    if iteration >= max_iterations:
        return EvalDecision(
            approved=True,
            reason=(
                f"Maks antall iterasjoner nådd ({max_iterations}). "
                f"Godkjent med vektet score {weighted_score}/10 "
                f"(essay: {critique.score}, selvstendighet: {independence}). "
                f"Gjenstående svakheter: {', '.join(critique.weaknesses[:3]) if critique.weaknesses else 'ingen'}."
            ),
            iteration=iteration,
            stagnation_detected=stagnation,
            improvements_found=improvements,
            unresolved_issues=unresolved,
        )

    # ── Weighted score meets threshold — approve ─────────────────
    if weighted_score >= score_threshold:
        return EvalDecision(
            approved=True,
            reason=(
                f"Vektet score {weighted_score}/10 møter terskel ({score_threshold}) "
                f"(essay: {critique.score}, selvstendighet: {independence}). "
                f"Styrker: {', '.join(critique.strengths[:3]) if critique.strengths else 'N/A'}."
            ),
            iteration=iteration,
            stagnation_detected=False,
            improvements_found=improvements,
            unresolved_issues=unresolved,
        )

    # ── Stagnation detected — flag for restructuring ─────────────
    if stagnation:
        return EvalDecision(
            approved=False,
            reason=(
                f"Vektet score {weighted_score}/10 "
                f"(essay: {critique.score}, selvstendighet: {independence}, "
                f"forrige: {previous_critique.score}). "
                f"Stagnasjon detektert — kosmetiske endringer løser ikke problemene. "
                f"Krever restrukturering."
            ),
            iteration=iteration,
            stagnation_detected=True,
            improvements_found=improvements,
            unresolved_issues=unresolved,
        )

    # ── Below threshold — normal revision ────────────────────────
    priorities = critique.revision_priority[:3] if critique.revision_priority else critique.weaknesses[:3]
    improvement_note = ""
    if improvements:
        improvement_note = f" Forbedret: {', '.join(improvements[:2])}."

    independence_note = ""
    if independence < 6.0:
        independence_note = f" Selvstendighet er lav ({independence}/10) — essayet trenger mer egen analyse."

    return EvalDecision(
        approved=False,
        reason=(
            f"Vektet score {weighted_score}/10 under terskel ({score_threshold}) "
            f"(essay: {critique.score}, selvstendighet: {independence}). "
            f"Topp prioriteringer: {', '.join(priorities) if priorities else 'se feedback'}."
            f"{improvement_note}{independence_note}"
        ),
        iteration=iteration,
        stagnation_detected=False,
        improvements_found=improvements,
        unresolved_issues=unresolved,
    )
