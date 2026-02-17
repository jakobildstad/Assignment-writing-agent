"""
Writer agent — produces academic essays for ExPhil based on sources
from the searcher agent, with support for critic-driven revision.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field

from agents.searcher import SourceBundle
from config import AGENT_DEFAULTS
from llm import TokenUsage, invoke_llm

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Reference(BaseModel):
    author: str = Field(description="Author name(s)")
    title: str = Field(description="Title of the work")
    year: int = Field(description="Publication year")
    page: str = Field(default="", description="Page number(s) referenced")
    url: str | None = Field(default=None, description="URL if web source")


class EssayDraft(BaseModel):
    title: str = Field(description="Essay title")
    body: str = Field(description="Full essay body in Markdown format")
    references: list[Reference] = Field(
        default_factory=list,
        description="Complete reference list",
    )
    word_count: int = Field(description="Approximate word count of the body")
    revision_number: int = Field(
        default=1,
        description="Revision number (1 = first draft)",
    )
    changes_made: str | None = Field(
        default=None,
        description="Description of changes made in this revision",
    )


class WriterConfig(BaseModel):
    max_words: int = Field(default=1500, description="Target word count")
    style: str = Field(
        default="akademisk",
        description="Writing style (akademisk, populærvitenskapelig)",
    )
    language: str = Field(default="norsk bokmål", description="Output language")


# ---------------------------------------------------------------------------
# System prompt loader
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def _load_system_prompt() -> str:
    prompt_file = _PROMPTS_DIR / "writer.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return "You are an academic essay writer for ExPhil at NTNU."


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _format_sources(sources: SourceBundle) -> str:
    """Format the SourceBundle into a readable context block for the LLM."""
    parts: list[str] = []

    if sources.pensum_sources:
        parts.append("## Pensum-kilder\n")
        for i, s in enumerate(sources.pensum_sources, 1):
            parts.append(
                f"### Kilde {i} ({s.reference}, s. {s.page})\n{s.content}\n"
            )

    if sources.web_sources:
        parts.append("## Nettkilder\n")
        for i, s in enumerate(sources.web_sources, 1):
            parts.append(
                f"### Kilde {i}: {s.title}\nURL: {s.url}\n{s.content}\n"
            )

    if sources.summary:
        parts.append(f"## Kildeoppsummering\n{sources.summary}\n")

    return "\n".join(parts)


def _build_user_message(
    task: str,
    sources: SourceBundle,
    writer_config: WriterConfig,
    feedback: str | None = None,
    previous_draft: EssayDraft | None = None,
    mode: str = "revise",
    unresolved_issues: list[str] | None = None,
) -> str:
    """Assemble the full user message for the writer LLM."""
    sections: list[str] = []

    # Task
    sections.append(f"# Oppgavetekst\n\n{task}")

    # Config
    sections.append(
        f"# Krav\n\n"
        f"- Maks antall ord: {writer_config.max_words}\n"
        f"- Stil: {writer_config.style}\n"
        f"- Språk: {writer_config.language}"
    )

    # Sources
    sections.append(f"# Tilgjengelige kilder\n\n{_format_sources(sources)}")

    # Revision context — two modes
    if feedback and previous_draft:
        if mode == "restructure":
            # MODE B: Restructuring — fundamentally different approach
            issues_text = ""
            if unresolved_issues:
                issues_text = "\n".join(f"- {issue}" for issue in unresolved_issues)
            else:
                issues_text = "(se feedback for detaljer)"

            sections.append(
                f"# RESTRUKTURERING (ikke vanlig revisjon)\n\n"
                f"**Forrige revisjon løste ikke problemene.** Kosmetiske endringer "
                f"(omformuleringer, bedre overganger, flere referanser) er IKKE nok.\n\n"
                f"Du skal nå RESTRUKTURERE essayet fundamentalt:\n\n"
                f"1. **Skriv en ny disposisjon FØR du skriver** — tenk gjennom "
                f"argumentasjonsstrukturen på nytt\n"
                f"2. **Vurder å endre tesen eller argumentasjonsretningen** — "
                f"en sterkere tese kan løse flere problemer\n"
                f"3. **Du kan beholde gode avsnitt**, men omorganiser rekkefølgen "
                f"og styrk svake deler\n"
                f"4. **Legg til minst ett nytt argument eller perspektiv** som "
                f"ikke var i forrige versjon\n"
                f"5. **Styrk drøftingen** — ikke bare presenter posisjoner, "
                f"argumenter AKTIVT for din posisjon\n\n"
                f"## Uløste problemer fra forrige runde\n\n{issues_text}\n\n"
                f"## Feedback fra kritiker\n\n{feedback}\n\n"
                f"## Tidligere utkast (for referanse — IKKE kopier strukturen)\n\n"
                f"{previous_draft.body}\n\n"
                f"Beskriv den nye strukturen og tilnærmingen i `changes_made`."
            )
        else:
            # MODE A: Normal revision
            sections.append(
                f"# Revisjon\n\n"
                f"Dette er revisjon nummer {previous_draft.revision_number + 1}.\n\n"
                f"## Tidligere utkast\n\n{previous_draft.body}\n\n"
                f"## Feedback fra kritiker\n\n{feedback}\n\n"
                f"Adresser hvert punkt i tilbakemeldingen. Behold det som fungerer. "
                f"Beskriv endringene i `changes_made`."
            )

    # Output format instruction
    sections.append(
        "# Output-format\n\n"
        "Skriv essayet i Markdown-format. Start med en tittel på første linje (# Tittel).\n\n"
        "Etter essayet, legg til en kildeliste under overskriften ## Referanser.\n\n"
        "Til SLUTT, etter alt annet, legg til en metadata-blokk i NØYAKTIG dette formatet:\n\n"
        "```json\n"
        "{\n"
        '  "word_count": 1234,\n'
        f'  "revision_number": {previous_draft.revision_number + 1 if previous_draft else 1},\n'
        f'  "changes_made": {"\"Beskrivelse av endringer...\"" if feedback else "null"}\n'
        "}\n"
        "```"
    )

    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


async def run_writer(
    task: str,
    sources: SourceBundle,
    feedback: str | None = None,
    previous_draft: EssayDraft | None = None,
    writer_config: WriterConfig | None = None,
    mode: str = "revise",
    unresolved_issues: list[str] | None = None,
) -> tuple[EssayDraft, TokenUsage]:
    """
    Run the writer agent to produce or revise an essay draft.

    Args:
        mode: "revise" for normal revision, "restructure" for fundamental rewrite.
        unresolved_issues: List of unresolved weaknesses from the evaluator
            (used in restructure mode).

    Returns:
        (EssayDraft, TokenUsage)
    """
    writer_config = writer_config or WriterConfig()
    cfg = AGENT_DEFAULTS["writer"]

    system_prompt = _load_system_prompt()
    user_message = _build_user_message(
        task, sources, writer_config, feedback, previous_draft,
        mode=mode, unresolved_issues=unresolved_issues,
    )

    logger.info(
        "Writer: revision={} words_target={} mode={}",
        (previous_draft.revision_number + 1) if previous_draft else 1,
        writer_config.max_words,
        mode,
    )

    content, usage = await invoke_llm(
        agent_name="writer",
        model=cfg["model"],
        temperature=cfg["temperature"],
        messages=[
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ],
        max_tokens=cfg.get("max_tokens", 8192),
        timeout_s=180.0,
    )

    draft = _parse_essay_response(content, previous_draft)
    logger.info(
        "Writer done: title='{}' words={} refs={}",
        draft.title[:50], draft.word_count, len(draft.references),
    )

    return draft, usage


def _parse_essay_response(
    content: str,
    previous_draft: EssayDraft | None = None,
) -> EssayDraft:
    """Parse the LLM response into an EssayDraft."""
    body = content
    metadata: dict = {}

    # 1. Extract trailing JSON metadata block
    json_match = re.search(r"```json\s*\n(\{.*?\})\s*\n```", content, re.DOTALL)
    if json_match:
        try:
            metadata = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
        body = content[: json_match.start()].rstrip()

    # 2. Extract title from first markdown heading
    title = "Uten tittel"
    title_match = re.match(r"^#\s+(.+)", body)
    if title_match:
        title = title_match.group(1).strip()

    # 3. Extract references section
    references: list[Reference] = []
    ref_split = re.split(r"\n##\s+(?:Referanser|Kildeliste|Litteraturliste)\s*\n", body, maxsplit=1)
    if len(ref_split) == 2:
        essay_body = ref_split[0].rstrip()
        ref_text = ref_split[1].strip()
        references = _parse_references(ref_text)
    else:
        essay_body = body

    word_count = metadata.get("word_count", len(essay_body.split()))
    revision = metadata.get(
        "revision_number",
        (previous_draft.revision_number + 1) if previous_draft else 1,
    )

    return EssayDraft(
        title=title,
        body=essay_body,
        references=references,
        word_count=word_count,
        revision_number=revision,
        changes_made=metadata.get("changes_made"),
    )


def _parse_references(ref_text: str) -> list[Reference]:
    """Best-effort parse of a markdown reference list into Reference objects."""
    refs: list[Reference] = []
    for line in ref_text.strip().splitlines():
        line = line.strip().lstrip("-•* ")
        if not line:
            continue

        clean = line.replace("*", "")
        m = re.match(
            r"(.+?)\s*\((\d{4})\)\.\s*(.+?)(?:\.\s*(?=s\.|http|$))(.*)",
            clean,
        )
        if m:
            author, year, title_str, rest = m.groups()
            page = ""
            url = None
            page_m = re.search(r"s\.\s*([\d\-–]+)", rest)
            if page_m:
                page = page_m.group(1)
            url_m = re.search(r"(https?://\S+)", rest)
            if url_m:
                url = url_m.group(1).rstrip(".")
            refs.append(Reference(
                author=author.strip(),
                title=title_str.strip().rstrip("."),
                year=int(year),
                page=page,
                url=url,
            ))
        else:
            refs.append(Reference(author="Ukjent", title=line, year=0))

    return refs
