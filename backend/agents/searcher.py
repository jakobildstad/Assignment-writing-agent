"""
Searcher agent — uses LangGraph ReAct pattern to find relevant sources
from pensum (via RAG) and the web (via Tavily).

Includes graceful degradation: if web search fails, continues with pensum only.
Token usage is extracted from the ReAct agent's accumulated messages.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Annotated

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from loguru import logger
from pydantic import BaseModel, Field

from config import AGENT_DEFAULTS
from llm import TokenUsage, _estimate_cost
from rag import retrieve

# ---------------------------------------------------------------------------
# Pydantic models for structured output
# ---------------------------------------------------------------------------


class PensumSource(BaseModel):
    content: str = Field(description="The relevant text passage from pensum")
    reference: str = Field(description="Source filename")
    page: int = Field(description="Page number in the source document")


class WebSource(BaseModel):
    content: str = Field(description="Summary or excerpt of the web source")
    url: str = Field(description="URL of the web source")
    title: str = Field(description="Title of the web page")


class SourceBundle(BaseModel):
    pensum_sources: list[PensumSource] = Field(
        default_factory=list,
        description="Relevant passages from uploaded pensum documents",
    )
    web_sources: list[WebSource] = Field(
        default_factory=list,
        description="Relevant sources found on the web",
    )
    summary: str = Field(
        description="Brief summary of what the sources collectively say about the topic",
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
def rag_search(
    query: Annotated[str, "Search query in Norwegian to find relevant pensum passages"],
    k: Annotated[int, "Number of results to return"] = 5,
) -> str:
    """Search through uploaded pensum documents using semantic similarity.

    Use this tool to find relevant passages from the student's course material.
    Formulate specific queries — use key concepts, philosopher names, and
    Norwegian terms for best results. Call this multiple times with different
    queries to get broad coverage.
    """
    try:
        docs = retrieve(query, k=k)
    except Exception as e:
        logger.warning("rag_search failed: {}", str(e)[:200])
        return f"RAG search error: {e}"

    if not docs:
        return "No relevant passages found in pensum."

    results = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        results.append(f"[{i}] (Source: {source}, p. {page})\n{doc.page_content.strip()}")
    return "\n\n---\n\n".join(results)


@tool
def web_search(
    query: Annotated[str, "Search query, preferably in English for broader coverage"],
    max_results: Annotated[int, "Number of results to return"] = 5,
) -> str:
    """Search the web for academic and philosophical sources.

    Use this to supplement pensum with additional context, definitions, or
    perspectives. Prefer English queries for broader coverage. Focus on
    academic sources like Stanford Encyclopedia of Philosophy.
    """
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        logger.warning("web_search: TAVILY_API_KEY not set, skipping web search")
        return (
            "[web_search unavailable — no TAVILY_API_KEY set]\n"
            "Continuing with pensum sources only."
        )

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=tavily_key)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_domains=[
                "plato.stanford.edu",
                "iep.utm.edu",
                "philpapers.org",
                "jstor.org",
                "cambridge.org",
                "oxfordhandbooks.com",
            ],
        )

        results = []
        for i, r in enumerate(response.get("results", []), 1):
            results.append(f"[{i}] {r['title']}\n    URL: {r['url']}\n    {r['content'][:500]}")
        return "\n\n".join(results) if results else "No web results found."

    except Exception as e:
        logger.warning("web_search failed (graceful degradation): {}", str(e)[:200])
        return f"[web_search error: {e}] Continuing with pensum sources only."


# ---------------------------------------------------------------------------
# System prompt loader
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def _load_system_prompt() -> str:
    prompt_file = _PROMPTS_DIR / "searcher.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return "You are a search agent. Find relevant academic sources."


# ---------------------------------------------------------------------------
# Token extraction from ReAct agent messages
# ---------------------------------------------------------------------------


def _extract_react_token_usage(messages: list, model: str) -> TokenUsage:
    """Extract accumulated token usage from a ReAct agent's message history.

    The ReAct agent makes multiple LLM calls (tool reasoning + final answer).
    We sum up usage_metadata from all AI messages.
    """
    total_input = 0
    total_output = 0

    for msg in messages:
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            total_input += usage.get("input_tokens", 0)
            total_output += usage.get("output_tokens", 0)

    cost = _estimate_cost(model, total_input, total_output)
    return TokenUsage(
        agent="searcher",
        model=model,
        input_tokens=total_input,
        output_tokens=total_output,
        cost_usd=cost,
    )


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

TOOLS = [rag_search, web_search]


def create_searcher_agent():
    """Create and return the searcher LangGraph agent."""
    cfg = AGENT_DEFAULTS["searcher"]
    llm = ChatAnthropic(
        model=cfg["model"],
        temperature=cfg["temperature"],
        max_tokens=cfg.get("max_tokens", 4096),
    )

    system_prompt = _load_system_prompt()

    agent = create_react_agent(
        model=llm,
        tools=TOOLS,
        prompt=system_prompt,
    )
    return agent


async def run_searcher(
    task: str,
    subtask: str | None = None,
) -> tuple[SourceBundle, TokenUsage]:
    """
    Run the searcher agent on a task and return a structured SourceBundle.

    Returns:
        (SourceBundle, TokenUsage)
    """
    cfg = AGENT_DEFAULTS["searcher"]
    agent = create_searcher_agent()

    user_msg = f"Oppgavetekst:\n{task}"
    if subtask:
        user_msg += f"\n\nDeloppgave:\n{subtask}"
    user_msg += (
        "\n\n---\n"
        "Søk i pensum (minst 2-3 forskjellige søk) og på nettet (2-3 søk). "
        "Når du er ferdig med å søke, oppsummer funnene.\n\n"
        "Svar med NØYAKTIG dette JSON-formatet og ingenting annet:\n"
        "{\n"
        '  "pensum_sources": [{"content": "...", "reference": "...", "page": N}],\n'
        '  "web_sources": [{"content": "...", "url": "...", "title": "..."}],\n'
        '  "summary": "..."\n'
        "}"
    )

    logger.info("Searcher: starting search for task='{}'", task[:80])

    t0 = time.monotonic()

    try:
        import asyncio

        result = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": [{"role": "user", "content": user_msg}]},
            ),
            timeout=180.0,
        )
    except asyncio.TimeoutError:
        logger.error("Searcher: timed out after 180s")
        empty_usage = TokenUsage(agent="searcher", model=cfg["model"])
        return SourceBundle(
            pensum_sources=[], web_sources=[],
            summary="Søke-agenten brukte for lang tid og ble avbrutt.",
        ), empty_usage
    except Exception as e:
        logger.error("Searcher: agent invocation failed: {}", str(e)[:200])
        empty_usage = TokenUsage(agent="searcher", model=cfg["model"])
        return SourceBundle(
            pensum_sources=[], web_sources=[],
            summary=f"Søke-agenten feilet: {str(e)[:200]}",
        ), empty_usage

    duration = time.monotonic() - t0

    # Extract token usage from all messages
    all_messages = result.get("messages", [])
    usage = _extract_react_token_usage(all_messages, cfg["model"])
    usage.duration_s = duration

    # Extract the final assistant message
    last_message = all_messages[-1] if all_messages else None
    content = last_message.content if last_message else ""

    logger.info(
        "Searcher done: duration={:.1f}s tokens={}/{}",
        duration, usage.input_tokens, usage.output_tokens,
    )

    # Parse the JSON from the response
    text = content
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    try:
        data = json.loads(text.strip())
        bundle = SourceBundle(**data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Searcher: failed to parse JSON response: {}", str(e)[:200])
        bundle = SourceBundle(
            pensum_sources=[],
            web_sources=[],
            summary=f"Agent returned unstructured response: {content[:500]}",
        )

    logger.info(
        "Searcher: pensum={} web={} summary_len={}",
        len(bundle.pensum_sources), len(bundle.web_sources), len(bundle.summary),
    )

    return bundle, usage
