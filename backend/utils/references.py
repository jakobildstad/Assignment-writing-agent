"""
Reference formatting and validation utilities.

Formats Reference objects into Harvard-style citation strings and validates
that references have complete, non-placeholder data.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.writer import EssayDraft, Reference


# ---------------------------------------------------------------------------
# Harvard-style formatting
# ---------------------------------------------------------------------------


def format_reference(ref: "Reference") -> str:
    """Format a single Reference into a Harvard-style citation string."""
    if ref.ref_type == "article":
        return _format_article(ref)
    elif ref.ref_type == "web":
        return _format_web(ref)
    elif ref.ref_type == "chapter":
        return _format_chapter(ref)
    else:
        return _format_book(ref)


def _format_book(ref: "Reference") -> str:
    """Bok: Forfatter (år) *Tittel*. Sted: Forlag."""
    parts = [f"{ref.author} ({ref.year}) *{ref.title}*."]
    if ref.publisher:
        parts.append(f"{ref.publisher}.")
    if ref.page:
        parts.append(f"s. {ref.page}.")
    return " ".join(parts)


def _format_article(ref: "Reference") -> str:
    """Artikkel: Forfatter (år) «Tittel», *Tidsskrift/avis*."""
    parts = [f"{ref.author} ({ref.year}) «{ref.title}»"]
    if ref.journal:
        parts.append(f", *{ref.journal}*.")
    else:
        parts.append(".")
    if ref.page:
        parts.append(f" s. {ref.page}.")
    if ref.url:
        parts.append(f" Tilgjengelig fra: {ref.url}")
    return "".join(parts)


def _format_web(ref: "Reference") -> str:
    """Nettside: Forfatter (år) *Tittel*. Tilgjengelig fra: URL."""
    parts = [f"{ref.author} ({ref.year}) *{ref.title}*."]
    if ref.url:
        parts.append(f"Tilgjengelig fra: {ref.url}")
    return " ".join(parts)


def _format_chapter(ref: "Reference") -> str:
    """Kapittel: Forfatter (år) «Kapittel», i *Bok*. Forlag."""
    parts = [f"{ref.author} ({ref.year}) «{ref.title}»"]
    if ref.publisher:
        parts.append(f". {ref.publisher}.")
    if ref.page:
        parts.append(f" s. {ref.page}.")
    return "".join(parts)


def format_reference_list(refs: list["Reference"]) -> str:
    """Format a complete reference list, sorted alphabetically by author."""
    if not refs:
        return ""
    sorted_refs = sorted(refs, key=lambda r: r.author.lower())
    lines = [format_reference(r) for r in sorted_refs]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_PLACEHOLDER_AUTHORS = {"ukjent", "unknown", "n/a", ""}
_PLACEHOLDER_TITLES = {"", "ukjent", "unknown", "n/a", "untitled"}


def validate_references(draft: "EssayDraft") -> list[str]:
    """
    Validate references in an EssayDraft. Returns a list of warning strings.

    Checks:
    1. References with placeholder/missing author or year
    2. Inline citations (Author, year) that don't match the reference list
    3. References in the list that are never cited inline
    """
    warnings: list[str] = []

    if not draft.references:
        warnings.append("Referanselisten er tom. Essayet mangler kildeliste.")
        return warnings

    # --- Check each reference for completeness ---
    for i, ref in enumerate(draft.references, 1):
        if ref.author.lower().strip() in _PLACEHOLDER_AUTHORS:
            warnings.append(
                f"Referanse {i}: Mangler forfatter (har '{ref.author}'). "
                f"Fiks eller fjern denne referansen."
            )
        if ref.year == 0 or ref.year < 1000:
            warnings.append(
                f"Referanse {i} ({ref.author}): Ugyldig årstall ({ref.year}). "
                f"Bruk faktisk utgivelsesår."
            )
        if ref.title.lower().strip() in _PLACEHOLDER_TITLES:
            warnings.append(
                f"Referanse {i} ({ref.author}): Mangler tittel."
            )
        if ref.ref_type == "web" and not ref.url:
            warnings.append(
                f"Referanse {i} ({ref.author}): Nettilde uten URL."
            )
        if ref.ref_type == "book" and not ref.publisher:
            warnings.append(
                f"Referanse {i} ({ref.author}, {ref.year}): Bok uten forlag."
            )

    # --- Check inline citations match reference list ---
    # Find all (Author, year) patterns in body
    inline_pattern = re.compile(r"\(([^()]+?),\s*(\d{4})")
    inline_citations: set[tuple[str, int]] = set()
    for match in inline_pattern.finditer(draft.body):
        author_part = match.group(1).strip()
        year_part = int(match.group(2))
        inline_citations.add((author_part, year_part))

    # Build lookup from reference list
    ref_authors_years: set[tuple[str, int]] = set()
    for ref in draft.references:
        # Extract last name(s) for matching
        last_name = ref.author.split(",")[0].strip()
        ref_authors_years.add((last_name, ref.year))
        # Also add full author for exact match
        ref_authors_years.add((ref.author, ref.year))

    # Check for inline citations without matching reference
    for author, year in inline_citations:
        found = False
        for ref_author, ref_year in ref_authors_years:
            if ref_year == year and (
                author.lower() in ref_author.lower()
                or ref_author.lower() in author.lower()
            ):
                found = True
                break
        if not found:
            warnings.append(
                f"Inline-referanse ({author}, {year}) har ingen match i referanselisten."
            )

    # Check for references never cited inline
    for ref in draft.references:
        last_name = ref.author.split(",")[0].strip()
        cited = False
        for author, year in inline_citations:
            if ref.year == year and (
                author.lower() in last_name.lower()
                or last_name.lower() in author.lower()
            ):
                cited = True
                break
        if not cited:
            warnings.append(
                f"Referanse '{ref.author} ({ref.year})' er i kildelisten "
                f"men aldri referert til i teksten."
            )

    return warnings
