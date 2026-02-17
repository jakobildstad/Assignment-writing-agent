from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Default model / temperature settings per agent
# ---------------------------------------------------------------------------

AGENT_DEFAULTS: dict[str, dict] = {
    "reader": {
        "model": "claude-sonnet-4-5-20250929",
        "temperature": 0.0,
        "max_tokens": 4096,
        "description": "Reads and extracts content from uploaded documents",
    },
    "analyzer": {
        "model": "claude-sonnet-4-5-20250929",
        "temperature": 0.3,
        "max_tokens": 4096,
        "description": "Analyzes extracted content for key concepts",
    },
    "writer": {
        "model": "claude-sonnet-4-5-20250929",
        "temperature": 0.7,
        "max_tokens": 8192,
        "description": "Produces final written output",
    },
    "searcher": {
        "model": "claude-sonnet-4-5-20250929",
        "temperature": 0.0,
        "max_tokens": 4096,
        "description": "Searches pensum and web for relevant sources",
    },
    "critic": {
        "model": "claude-sonnet-4-5-20250929",
        "temperature": 0.2,
        "max_tokens": 4096,
        "description": "Evaluates essay drafts and provides structured feedback",
    },
}

# ---------------------------------------------------------------------------
# Pipeline / evaluator settings
# ---------------------------------------------------------------------------

EVALUATOR_DEFAULTS = {
    "score_threshold": 7.5,
    "max_iterations": 10,
}

UPLOAD_DIR = "/tmp/uploads"
VECTORSTORE_DIR = "/tmp/vectorstore"

# ---------------------------------------------------------------------------
# Embedding settings
# ---------------------------------------------------------------------------

EMBEDDING_DEFAULTS: dict[str, str | int] = {
    "provider": "openai",          # "openai" (needs OPENAI_API_KEY) or "fake" (random vectors, no key needed)
    "model": "text-embedding-3-small",
    "chunk_size": 1000,
    "chunk_overlap": 200,
}


class AgentConfig(BaseModel):
    model: str
    temperature: float
    max_tokens: int = 4096
    description: str


class AppConfig(BaseModel):
    agents: dict[str, AgentConfig]
