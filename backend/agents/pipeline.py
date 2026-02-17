"""
Placeholder agent functions.

Each function represents a stage in the agent pipeline.
Implement the actual logic later — for now they just emit progress messages.
"""

from __future__ import annotations

import asyncio
from typing import Callable

# Type alias for the progress callback
ProgressCallback = Callable[[str], asyncio.coroutines]


async def reader_agent(files: list[str], *, on_progress: ProgressCallback) -> dict:
    """Read and extract text from uploaded documents."""
    await on_progress(f"[reader] Starting — processing {len(files)} file(s)...")
    await asyncio.sleep(0.5)  # simulate work
    await on_progress("[reader] Done (placeholder).")
    return {"chunks": [], "metadata": {}}


async def analyzer_agent(reader_output: dict, *, on_progress: ProgressCallback) -> dict:
    """Analyze extracted content for key concepts."""
    await on_progress("[analyzer] Starting analysis...")
    await asyncio.sleep(0.5)
    await on_progress("[analyzer] Done (placeholder).")
    return {"concepts": [], "summary": ""}


async def writer_agent(analyzer_output: dict, *, on_progress: ProgressCallback) -> dict:
    """Produce final written output."""
    await on_progress("[writer] Starting writing...")
    await asyncio.sleep(0.5)
    await on_progress("[writer] Done (placeholder).")
    return {"output": "Placeholder output — agents not yet implemented."}


async def run_pipeline(files: list[str], *, on_progress: ProgressCallback) -> dict:
    """Run the full agent pipeline sequentially."""
    await on_progress("Pipeline started.")

    reader_out = await reader_agent(files, on_progress=on_progress)
    analyzer_out = await analyzer_agent(reader_out, on_progress=on_progress)
    writer_out = await writer_agent(analyzer_out, on_progress=on_progress)

    await on_progress("Pipeline complete.")
    return writer_out
