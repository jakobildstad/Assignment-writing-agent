"""
Shared LLM utilities: retry with backoff, token tracking, timeouts, logging,
and truncation detection with automatic retry.

Every agent calls `invoke_llm()` instead of `llm.ainvoke()` directly.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage
from loguru import logger
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

T = TypeVar("T", bound=BaseModel)

# ---------------------------------------------------------------------------
# Token / cost tracking
# ---------------------------------------------------------------------------

# Approximate cost per 1M tokens (USD) — Anthropic pricing Feb 2025
_COST_TABLE: dict[str, tuple[float, float]] = {
    # (input_cost_per_1M, output_cost_per_1M)
    "claude-sonnet-4-5-20250929": (3.0, 15.0),
    "claude-opus-4-0-20250115": (15.0, 75.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-opus-4-6": (15.0, 75.0),
    # GPT fallbacks (for config options)
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
}

# Maximum ceiling for truncation retry doubling
MAX_TOKENS_CEILING = 16384


@dataclass
class TokenUsage:
    """Accumulated token usage for a single LLM call."""
    agent: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_s: float = 0.0
    was_truncated: bool = False

    def to_dict(self) -> dict:
        d = {
            "agent": self.agent,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "duration_s": round(self.duration_s, 2),
        }
        if self.was_truncated:
            d["was_truncated"] = True
        return d


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = _COST_TABLE.get(model, (3.0, 15.0))  # default to Sonnet rates
    return (input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000


def _extract_token_usage(response: Any) -> tuple[int, int]:
    """Extract input/output token counts from a LangChain AIMessage."""
    usage = getattr(response, "usage_metadata", None)
    if usage:
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)

    # Fallback: check response_metadata
    meta = getattr(response, "response_metadata", {})
    if "usage" in meta:
        u = meta["usage"]
        return u.get("input_tokens", 0), u.get("output_tokens", 0)

    return 0, 0


# ---------------------------------------------------------------------------
# Truncation detection
# ---------------------------------------------------------------------------


def _is_truncated(response: Any) -> bool:
    """
    Check if an LLM response was truncated due to max_tokens.

    Works for both Anthropic and OpenAI via LangChain's response_metadata:
      - Anthropic: stop_reason == "max_tokens"
      - OpenAI:    finish_reason == "length"
    """
    meta = getattr(response, "response_metadata", {})

    # Anthropic
    if meta.get("stop_reason") == "max_tokens":
        return True

    # OpenAI
    if meta.get("finish_reason") == "length":
        return True

    return False


# ---------------------------------------------------------------------------
# Retryable LLM invocation with truncation detection
# ---------------------------------------------------------------------------

# Retry on rate-limit and transient errors
_RETRYABLE_ERRORS = (
    Exception,  # Broad — tenacity will only retry up to max attempts
)


async def invoke_llm(
    *,
    agent_name: str,
    model: str,
    temperature: float,
    messages: list[BaseMessage],
    max_tokens: int = 4096,
    timeout_s: float = 120.0,
    max_retries: int = 3,
    truncation_retries: int = 2,
    max_tokens_ceiling: int = MAX_TOKENS_CEILING,
) -> tuple[str, TokenUsage]:
    """
    Invoke an LLM with retry, timeout, token tracking, and truncation detection.

    If the response is truncated (stop_reason == "max_tokens"), automatically
    retries with doubled max_tokens up to max_tokens_ceiling.

    Returns:
        (content_str, TokenUsage)

    Raises:
        asyncio.TimeoutError if the call exceeds timeout_s after all retries.
        Exception if all retries are exhausted.
    """
    total_inp = 0
    total_out = 0
    was_truncated = False
    current_max_tokens = max_tokens
    t0 = time.monotonic()

    for truncation_attempt in range(truncation_retries + 1):
        llm = ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=current_max_tokens,
        )

        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type(_RETRYABLE_ERRORS),
            reraise=True,
        )
        async def _call():
            return await asyncio.wait_for(
                llm.ainvoke(messages),
                timeout=timeout_s,
            )

        logger.info(
            "LLM call start | agent={} model={} max_tokens={} attempt={}",
            agent_name, model, current_max_tokens,
            truncation_attempt + 1 if truncation_attempt > 0 else 1,
        )

        try:
            response = await _call()
        except asyncio.TimeoutError:
            duration = time.monotonic() - t0
            logger.error(
                "LLM timeout | agent={} model={} duration={:.1f}s",
                agent_name, model, duration,
            )
            raise
        except Exception as e:
            duration = time.monotonic() - t0
            logger.error(
                "LLM error after retries | agent={} model={} error={} duration={:.1f}s",
                agent_name, model, str(e)[:200], duration,
            )
            raise

        # Accumulate token usage across truncation retries
        inp, out = _extract_token_usage(response)
        total_inp += inp
        total_out += out

        # Check for truncation
        if _is_truncated(response):
            was_truncated = True

            if truncation_attempt < truncation_retries:
                next_max = min(current_max_tokens * 2, max_tokens_ceiling)
                if next_max <= current_max_tokens:
                    # Already at ceiling, can't increase further
                    logger.warning(
                        "LLM truncated at ceiling | agent={} max_tokens={} output_tokens={}",
                        agent_name, current_max_tokens, out,
                    )
                    break

                logger.warning(
                    "LLM output truncated | agent={} output_tokens={} max_tokens={} → retrying with {}",
                    agent_name, out, current_max_tokens, next_max,
                )
                current_max_tokens = next_max
                continue
            else:
                logger.warning(
                    "LLM still truncated after {} retries | agent={} max_tokens={} output_tokens={}",
                    truncation_retries, agent_name, current_max_tokens, out,
                )
        break

    duration = time.monotonic() - t0
    content = response.content
    cost = _estimate_cost(model, total_inp, total_out)

    usage = TokenUsage(
        agent=agent_name,
        model=model,
        input_tokens=total_inp,
        output_tokens=total_out,
        cost_usd=cost,
        duration_s=duration,
        was_truncated=was_truncated,
    )

    log_fn = logger.warning if was_truncated else logger.info
    log_fn(
        "LLM call done | agent={} tokens={}/{} cost=${:.4f} duration={:.1f}s{}",
        agent_name, total_inp, total_out, cost, duration,
        " [TRUNCATED]" if was_truncated else "",
    )

    return content, usage


# ---------------------------------------------------------------------------
# Structured output (tool_use-backed) — guarantees valid schema
# ---------------------------------------------------------------------------


async def invoke_llm_structured(
    *,
    agent_name: str,
    model: str,
    temperature: float,
    messages: list[BaseMessage],
    response_schema: type[T],
    max_tokens: int = 4096,
    timeout_s: float = 120.0,
    max_retries: int = 3,
    truncation_retries: int = 2,
    max_tokens_ceiling: int = MAX_TOKENS_CEILING,
) -> tuple[T, TokenUsage]:
    """
    Invoke an LLM with structured output via tool_use, with truncation detection.

    The model is forced to return a JSON object matching `response_schema`
    (a Pydantic BaseModel). This uses Anthropic's tool_use under the hood,
    making the output ~99% reliable for schema compliance.

    If the response is truncated, automatically retries with doubled max_tokens.

    Returns:
        (parsed_model_instance, TokenUsage)
    """
    total_inp = 0
    total_out = 0
    was_truncated = False
    current_max_tokens = max_tokens
    t0 = time.monotonic()

    for truncation_attempt in range(truncation_retries + 1):
        llm = ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=current_max_tokens,
        )

        structured_llm = llm.with_structured_output(
            response_schema,
            method="tool_use",
            include_raw=True,
        )

        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type(_RETRYABLE_ERRORS),
            reraise=True,
        )
        async def _call():
            return await asyncio.wait_for(
                structured_llm.ainvoke(messages),
                timeout=timeout_s,
            )

        logger.info(
            "LLM structured call start | agent={} model={} schema={} max_tokens={}",
            agent_name, model, response_schema.__name__, current_max_tokens,
        )

        try:
            result = await _call()
        except asyncio.TimeoutError:
            duration = time.monotonic() - t0
            logger.error(
                "LLM structured timeout | agent={} model={} duration={:.1f}s",
                agent_name, model, duration,
            )
            raise
        except Exception as e:
            duration = time.monotonic() - t0
            logger.error(
                "LLM structured error | agent={} model={} error={} duration={:.1f}s",
                agent_name, model, str(e)[:200], duration,
            )
            raise

        # include_raw=True returns {"raw": AIMessage, "parsed": T, "parsing_error": ...}
        raw_msg = result.get("raw")
        parsed = result.get("parsed")
        parsing_error = result.get("parsing_error")

        inp, out = _extract_token_usage(raw_msg) if raw_msg else (0, 0)
        total_inp += inp
        total_out += out

        # Check for truncation on the raw message
        if raw_msg and _is_truncated(raw_msg):
            was_truncated = True

            if truncation_attempt < truncation_retries:
                next_max = min(current_max_tokens * 2, max_tokens_ceiling)
                if next_max <= current_max_tokens:
                    logger.warning(
                        "LLM structured truncated at ceiling | agent={} max_tokens={}",
                        agent_name, current_max_tokens,
                    )
                    break

                logger.warning(
                    "LLM structured output truncated | agent={} max_tokens={} → retrying with {}",
                    agent_name, current_max_tokens, next_max,
                )
                current_max_tokens = next_max
                continue
            else:
                logger.warning(
                    "LLM structured still truncated after {} retries | agent={}",
                    truncation_retries, agent_name,
                )
        break

    duration = time.monotonic() - t0
    cost = _estimate_cost(model, total_inp, total_out)

    usage = TokenUsage(
        agent=agent_name,
        model=model,
        input_tokens=total_inp,
        output_tokens=total_out,
        cost_usd=cost,
        duration_s=duration,
        was_truncated=was_truncated,
    )

    if parsing_error or parsed is None:
        logger.warning(
            "LLM structured output parsing failed | agent={} error={}",
            agent_name, str(parsing_error)[:200] if parsing_error else "parsed=None",
        )
        raise ValueError(
            f"Structured output parsing failed: {parsing_error}"
        )

    log_fn = logger.warning if was_truncated else logger.info
    log_fn(
        "LLM structured call done | agent={} tokens={}/{} cost=${:.4f} duration={:.1f}s{}",
        agent_name, total_inp, total_out, cost, duration,
        " [TRUNCATED]" if was_truncated else "",
    )

    return parsed, usage
