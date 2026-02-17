"""
Critic agent — evaluates an EssayDraft against the original task and sources,
returning structured feedback for the writer to revise.

Uses a three-layer strategy for reliable structured output:
  1. Structured output via tool_use (API-level JSON schema enforcement)
  2. Robust text-based JSON extraction (multiple parsing strategies)
  3. Retry with repair prompt (send broken output back for correction)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from agents.searcher import SourceBundle
from agents.writer import EssayDraft
from config import AGENT_DEFAULTS
from llm import TokenUsage, invoke_llm, invoke_llm_structured

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SectionFeedback(BaseModel):
    section: str = Field(description="Which section or paragraph the feedback applies to")
    issue: str = Field(description="What the problem is")
    suggestion: str = Field(description="Concrete suggestion for improvement")


class CritiqueResult(BaseModel):
    overall_assessment: str = Field(
        description="High-level summary of the essay's quality",
    )
    score: float = Field(
        ge=0, le=10,
        description="Score from 0-10 (5 = pass, 8+ = excellent)",
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="What the essay does well",
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Main areas for improvement",
    )
    specific_feedback: list[SectionFeedback] = Field(
        default_factory=list,
        description="Section-by-section feedback with concrete suggestions",
    )
    factual_issues: list[str] = Field(
        default_factory=list,
        description="Factual errors or misrepresentations of philosophical positions",
    )
    missing_perspectives: list[str] = Field(
        default_factory=list,
        description="Important perspectives or arguments not addressed",
    )
    reference_issues: list[str] = Field(
        default_factory=list,
        description="Problems with citations or reference usage",
    )
    revision_priority: list[str] = Field(
        default_factory=list,
        description="Ordered list of what to fix first (most important → least)",
    )
    independence_score: float = Field(
        default=5.0,
        ge=0, le=10,
        description="How independently the essay thinks beyond summarizing sources (0-10)",
    )
    independence_notes: str = Field(
        default="",
        description="Specific observations about the essay's independent thinking",
    )


# ---------------------------------------------------------------------------
# System prompt loader
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def _load_system_prompt() -> str:
    prompt_file = _PROMPTS_DIR / "critic.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return "You are an academic essay evaluator for ExPhil at NTNU."


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _format_sources_summary(sources: SourceBundle) -> str:
    """Compact source summary for the critic to fact-check against."""
    parts: list[str] = []

    if sources.pensum_sources:
        parts.append("### Pensum-kilder brukt av søke-agenten:")
        for i, s in enumerate(sources.pensum_sources, 1):
            parts.append(f"{i}. ({s.reference}, s. {s.page}): {s.content[:200]}...")

    if sources.web_sources:
        parts.append("\n### Nettkilder:")
        for i, s in enumerate(sources.web_sources, 1):
            parts.append(f"{i}. [{s.title}]({s.url}): {s.content[:200]}...")

    return "\n".join(parts)


def _build_user_message(
    task: str,
    draft: EssayDraft,
    sources: SourceBundle,
) -> str:
    """Assemble the evaluation request."""
    references_text = ""
    if draft.references:
        refs = []
        for r in draft.references:
            ref = f"- {r.author} ({r.year}). *{r.title}*."
            if r.page:
                ref += f" s. {r.page}."
            if r.url:
                ref += f" {r.url}"
            refs.append(ref)
        references_text = "\n".join(refs)
    else:
        references_text = "(Ingen referanser oppgitt)"

    return f"""# Oppgavetekst

{task}

# Essay-utkast (revisjon {draft.revision_number})

## {draft.title}

{draft.body}

## Kildeliste

{references_text}

*Antall ord: {draft.word_count}*

# Tilgjengelige kilder (for faktasjekk)

{_format_sources_summary(sources)}

Evaluer essayet grundig mot alle kriteriene i din system-prompt."""


# ---------------------------------------------------------------------------
# Layer 2: Robust JSON extraction from unstructured text
# ---------------------------------------------------------------------------


def _extract_json_from_text(text: str) -> CritiqueResult | None:
    """
    Try multiple strategies to extract valid JSON from messy LLM output.
    Returns a CritiqueResult if successful, None otherwise.
    """
    candidates: list[str] = []

    # Strategy 1: strip markdown code fences
    if "```json" in text:
        for block in text.split("```json")[1:]:
            if "```" in block:
                candidates.append(block.split("```")[0])
    elif "```" in text:
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            candidates.append(parts[i])

    # Strategy 2: find the outermost { ... } with brace matching
    first_brace = text.find("{")
    if first_brace != -1:
        depth = 0
        for i, ch in enumerate(text[first_brace:], start=first_brace):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[first_brace : i + 1])
                    break

    # Strategy 3: regex for JSON-like block
    m = re.search(r"\{[\s\S]*\"overall_assessment\"[\s\S]*\"score\"[\s\S]*\}", text)
    if m:
        candidates.append(m.group(0))

    # Strategy 4: the raw text itself (maybe it's already clean JSON)
    candidates.append(text.strip())

    # Try each candidate
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            return CritiqueResult(**data)
        except (json.JSONDecodeError, ValidationError):
            continue

    return None


# ---------------------------------------------------------------------------
# Layer 3: Repair prompt — ask the LLM to fix its own broken output
# ---------------------------------------------------------------------------

_REPAIR_PROMPT = """Du prøvde å returnere en JSON-evaluering, men outputen var ikke gyldig JSON.
Her er det du svarte:

---
{broken_output}
---

Returner BARE et gyldig JSON-objekt med NØYAKTIG denne strukturen (ingen annen tekst):
{{
  "overall_assessment": "...",
  "score": 0.0,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "specific_feedback": [{{"section": "...", "issue": "...", "suggestion": "..."}}],
  "factual_issues": ["..."],
  "missing_perspectives": ["..."],
  "reference_issues": ["..."],
  "revision_priority": ["..."]
}}"""


# ---------------------------------------------------------------------------
# Agent runner — three-layer strategy
# ---------------------------------------------------------------------------


def _is_anthropic_model(model: str) -> bool:
    """Check if the model is an Anthropic Claude model."""
    return "claude" in model.lower()


async def run_critic(
    task: str,
    draft: EssayDraft,
    sources: SourceBundle,
) -> tuple[CritiqueResult, TokenUsage]:
    """
    Evaluate an essay draft and return structured critique.

    Three-layer strategy:
      1. Structured output via tool_use (Anthropic models only — ~99% reliable)
      2. Robust text-based JSON extraction (multiple parsing strategies)
      3. Retry with repair prompt (send broken output back for correction)

    Returns:
        (CritiqueResult, TokenUsage)
    """
    cfg = AGENT_DEFAULTS["critic"]
    model = cfg["model"]

    system_prompt = _load_system_prompt()
    user_message = _build_user_message(task, draft, sources)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    logger.info(
        "Critic: evaluating revision={} title='{}'",
        draft.revision_number, draft.title[:50],
    )

    # ── Layer 1: Structured output via tool_use ──────────────────
    if _is_anthropic_model(model):
        try:
            critique, usage = await invoke_llm_structured(
                agent_name="critic",
                model=model,
                temperature=cfg["temperature"],
                messages=messages,
                response_schema=CritiqueResult,
                max_tokens=cfg.get("max_tokens", 4096),
                timeout_s=120.0,
            )
            logger.info(
                "Critic done (structured) | score={} strengths={} weaknesses={}",
                critique.score, len(critique.strengths), len(critique.weaknesses),
            )
            return critique, usage

        except Exception as e:
            logger.warning(
                "Critic: structured output failed, falling back to text | error={}",
                str(e)[:200],
            )
            # Fall through to Layer 2

    # ── Layer 2: Text-based with robust JSON extraction ──────────
    content, usage = await invoke_llm(
        agent_name="critic",
        model=model,
        temperature=cfg["temperature"],
        messages=messages,
        max_tokens=cfg.get("max_tokens", 4096),
        timeout_s=120.0,
    )

    critique = _extract_json_from_text(content)
    if critique is not None:
        logger.info(
            "Critic done (text-parsed) | score={} strengths={} weaknesses={}",
            critique.score, len(critique.strengths), len(critique.weaknesses),
        )
        return critique, usage

    # ── Layer 3: Repair — send broken output back to the LLM ────
    logger.warning(
        "Critic: text parsing failed, attempting repair | raw_length={}",
        len(content),
    )

    repair_message = _REPAIR_PROMPT.format(broken_output=content[:3000])

    try:
        repair_content, repair_usage = await invoke_llm(
            agent_name="critic_repair",
            model=model,
            temperature=0.0,  # deterministic for repair
            messages=[
                SystemMessage(content="Du er en JSON-reparasjonsassistent. Returner KUN gyldig JSON."),
                HumanMessage(content=repair_message),
            ],
            max_tokens=4096,
            timeout_s=60.0,
            max_retries=2,
        )

        # Merge token usage from both calls
        usage = TokenUsage(
            agent="critic",
            model=model,
            input_tokens=usage.input_tokens + repair_usage.input_tokens,
            output_tokens=usage.output_tokens + repair_usage.output_tokens,
            cost_usd=usage.cost_usd + repair_usage.cost_usd,
            duration_s=usage.duration_s + repair_usage.duration_s,
        )

        critique = _extract_json_from_text(repair_content)
        if critique is not None:
            logger.info(
                "Critic done (repaired) | score={} strengths={} weaknesses={}",
                critique.score, len(critique.strengths), len(critique.weaknesses),
            )
            return critique, usage

    except Exception as e:
        logger.error("Critic: repair attempt also failed | error={}", str(e)[:200])

    # ── All layers failed — return degraded result ───────────────
    logger.error("Critic: all 3 layers failed, returning degraded critique")
    critique = CritiqueResult(
        overall_assessment=f"Kunne ikke parse strukturert feedback. Rå respons: {content[:500]}",
        score=0.0,
        strengths=[],
        weaknesses=["Kritiker-agenten returnerte ustrukturert respons etter 3 forsøk"],
        specific_feedback=[],
        factual_issues=[],
        missing_perspectives=[],
        reference_issues=[],
        revision_priority=["Kjør kritikeren på nytt med en annen modell"],
    )

    return critique, usage


def format_feedback_for_writer(critique: CritiqueResult) -> str:
    """
    Convert a CritiqueResult into a readable feedback string
    suitable for passing to the writer agent for revision.
    """
    lines: list[str] = []

    lines.append(f"## Helhetsvurdering (score: {critique.score}/10)\n")
    lines.append(critique.overall_assessment)

    if critique.strengths:
        lines.append("\n## Styrker (behold disse)")
        for s in critique.strengths:
            lines.append(f"- {s}")

    if critique.weaknesses:
        lines.append("\n## Svakheter (må forbedres)")
        for w in critique.weaknesses:
            lines.append(f"- {w}")

    if critique.specific_feedback:
        lines.append("\n## Spesifikk feedback per seksjon")
        for fb in critique.specific_feedback:
            lines.append(f"\n### {fb.section}")
            lines.append(f"**Problem:** {fb.issue}")
            lines.append(f"**Forslag:** {fb.suggestion}")

    if critique.factual_issues:
        lines.append("\n## Faktafeil (kritisk — må fikses)")
        for f in critique.factual_issues:
            lines.append(f"- {f}")

    if critique.missing_perspectives:
        lines.append("\n## Manglende perspektiver")
        for m in critique.missing_perspectives:
            lines.append(f"- {m}")

    if critique.reference_issues:
        lines.append("\n## Referanseproblemer")
        for r in critique.reference_issues:
            lines.append(f"- {r}")

    if critique.independence_notes:
        lines.append(f"\n## Selvstendighet (score: {critique.independence_score}/10)")
        lines.append(critique.independence_notes)
        if critique.independence_score < 6.0:
            lines.append(
                "\n**OBS:** Lav selvstendighets-score trekker ned totalvurderingen. "
                "Essayet trenger mer egen analyse, egne eksempler, og eksplisitte vurderinger "
                "— ikke bare gjengivelse av kildene."
            )

    if critique.revision_priority:
        lines.append("\n## Revisjonsprioritet (fiks i denne rekkefølgen)")
        for i, p in enumerate(critique.revision_priority, 1):
            lines.append(f"{i}. {p}")

    return "\n".join(lines)
