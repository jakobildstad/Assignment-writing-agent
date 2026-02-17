"""
File-based session store for persisting pipeline state across page reloads.

Each session is stored as a JSON file at /tmp/sessions/{session_id}.json.
The orchestrator calls `save()` at every state transition, so the file
always reflects the latest pipeline state.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

SESSIONS_DIR = Path("/tmp/sessions")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def save(session_id: str, state: dict) -> None:
    """Persist the current pipeline state to disk."""
    # Build the session document from PipelineState
    now = datetime.now().isoformat()

    # Determine current_phase from the state
    status = state.get("status", "running")
    if status == "completed":
        current_phase = "done"
    elif status == "error":
        current_phase = "failed"
    elif state.get("eval_decision") and not state["eval_decision"].get("approved", False):
        current_phase = "evaluating"
    elif state.get("critique"):
        current_phase = "critiquing"
    elif state.get("current_draft"):
        current_phase = "writing"
    elif state.get("sources"):
        current_phase = "searching"
    else:
        current_phase = "searching"

    # Collect all drafts (current_draft at each iteration)
    # We store the current_draft and can reconstruct from critique_history
    drafts = []
    if state.get("current_draft"):
        drafts.append(state["current_draft"])

    doc = {
        "session_id": session_id,
        "created_at": _read_created_at(session_id) or now,
        "updated_at": now,
        "status": status,
        "task_text": state.get("task", ""),
        "config": {
            "writer_config": state.get("writer_config", {}),
            "evaluator_config": state.get("evaluator_config", {}),
        },
        "current_phase": current_phase,
        "iteration": state.get("iteration", 1),
        "drafts": drafts,
        "critiques": state.get("critique_history", []),
        "sources": state.get("sources") or None,
        "final_draft": state.get("current_draft") if status == "completed" else None,
        "progress_log": [
            {"timestamp": "", "event": "log", "message": entry}
            for entry in state.get("progress_log", [])
        ],
        "token_usage": state.get("token_usage", []),
        "total_cost_usd": state.get("total_cost_usd", 0),
        "error": state.get("error", ""),
    }

    try:
        path = _session_path(session_id)
        path.write_text(json.dumps(doc, ensure_ascii=False, default=str), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to save session {}: {}", session_id, str(e)[:200])


def load(session_id: str) -> dict | None:
    """Load a session from disk. Returns None if not found."""
    path = _session_path(session_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to load session {}: {}", session_id, str(e)[:200])
        return None


def list_sessions(limit: int = 20) -> list[dict]:
    """List recent sessions, sorted newest first.

    Returns lightweight summaries (no full drafts/critiques).
    """
    sessions = []
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sessions.append({
                "session_id": data.get("session_id", path.stem),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "status": data.get("status", "unknown"),
                "task_text": (data.get("task_text", "") or "")[:100],
                "current_phase": data.get("current_phase", ""),
                "iteration": data.get("iteration", 1),
                "total_cost_usd": data.get("total_cost_usd", 0),
                "score": _extract_latest_score(data),
            })
        except Exception:
            continue

    # Sort by updated_at descending
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions[:limit]


def _read_created_at(session_id: str) -> str | None:
    """Read just the created_at from an existing session file."""
    path = _session_path(session_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("created_at")
    except Exception:
        return None


def _extract_latest_score(data: dict) -> float | None:
    """Extract the latest critique score from session data."""
    critiques = data.get("critiques", [])
    if critiques:
        return critiques[-1].get("score")
    return None
