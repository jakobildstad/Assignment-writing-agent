# Exphil Agent
'''
note 
Other ideas worth trying: 
- Job application optimizer (CV-writer, Application writer, critic, ...)
- Study Companion Agents (searcher, tutor agent, quiz agent, evaluator agent, )
'''

Multi-agent system that writes academic ExPhil essays (NTNU). Uploads curriculum PDFs, searches sources via RAG and web, writes drafts, evaluates with a blind critic, and revises automatically until a quality threshold is met.

## Pipeline

```
START → searcher → writer → critic → evaluator ─┐
                     ↑                            │
                     └── writer (revise/restructure) ← (rejected) ──┘
                                                    (approved) → END
```

| Agent | Role | LLM strategy |
|---|---|---|
| Searcher | RAG search (FAISS) + web search (Tavily, academic domains only) | ReAct agent with tools |
| Writer | Produces/revises essay in Markdown with Harvard references | Single LLM call, text output |
| Critic | Blind evaluation returning structured JSON (score, feedback, independence) | Three-layer structured output |
| Evaluator | Threshold + stagnation + weighted scoring logic | Pure Python, no LLM |

## Architecture decisions

### Blind critic
The critic never sees previous drafts or scores. It evaluates each version on its own merits, preventing grade inflation where the model inflates scores to reward marginal improvements.

### Weighted scoring
The evaluator computes `final = essay_score * 0.7 + independence_score * 0.3`. An essay that scores 8.0 overall but only 4.0 on independent thinking gets a weighted 6.8, forcing revision. This combats the common failure mode where essays are well-structured summaries with no original analysis.

### Stagnation detection and restructuring
When consecutive revisions produce similar scores (delta <= 0.3) and similar weaknesses (fuzzy overlap >= 0.6) or near-identical body text (similarity > 0.92), the evaluator flags stagnation. The writer then switches from "revise" mode (address feedback points) to "restructure" mode (rewrite the argument structure from scratch). Second consecutive stagnation force-approves the best-scoring draft from history.

### Three-layer critic output
Structured JSON output fails occasionally, so the critic uses layered fallbacks:
1. Anthropic `tool_use` schema enforcement (most reliable)
2. Text output with multi-strategy JSON extraction (code fence stripping, brace-depth matching, regex, raw parse)
3. Repair prompt — sends broken output back asking for valid JSON
4. Degraded `CritiqueResult` with `score=0.0`

### Anti-AI writing style
Both the writer and critic prompts contain extensive rules to avoid detectable AI writing patterns: no m-dashes, no "rule of three", no mechanical transitions, blacklisted AI vocabulary (Norwegian and English), varied sentence rhythm, mandatory personal voice ("jeg mener"), no bold-keyword spam, prose over bullet lists.

### Prompts as external files
All agent prompts live in `prompts/*.md` and are loaded at runtime. This keeps them editable without touching Python code and separates prompt engineering from application logic.

### Session persistence at every event
`session_store.save()` is called after every pipeline state transition. The frontend can rehydrate a running or completed pipeline on page reload. Sessions survive server restarts. Stored as JSON at `/tmp/sessions/`.

### Truncation retry
The LLM layer detects when output was cut short (`stop_reason == "max_tokens"`) and automatically retries with doubled `max_tokens` up to 16,384 — up to 2 extra attempts before giving up.

## Project structure

```
exphil-agent/
├── backend/
│   ├── main.py                # FastAPI app — REST + WebSocket endpoints
│   ├── orchestrator.py        # LangGraph StateGraph pipeline
│   ├── config.py              # Agent defaults, evaluator config, embedding config
│   ├── llm.py                 # Shared LLM abstraction (retry, timeout, truncation, cost tracking)
│   ├── rag.py                 # PDF/TXT ingestion → FAISS vectorstore → similarity search
│   ├── session.py             # File-based session persistence (/tmp/sessions/)
│   ├── agents/
│   │   ├── searcher.py        # ReAct agent with rag_search + web_search tools
│   │   ├── writer.py          # Essay generation with revision/restructure modes
│   │   ├── critic.py          # Structured evaluation with independence scoring
│   │   └── evaluator.py       # Pure-Python threshold + stagnation + weighted scoring
│   ├── utils/
│   │   └── references.py      # Harvard-style formatting + inline citation validation
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Entire frontend (~2400 lines, monolithic)
│   │   ├── index.css          # Tailwind v4 + custom animations
│   │   └── components/
│   │       └── MermaidBlock.jsx  # Mermaid diagram renderer
│   ├── vite.config.js         # Dev proxy: /api → :8000, /ws → ws://:8000
│   └── package.json
├── prompts/
│   ├── searcher.md            # Search strategy, source prioritization, JSON output spec
│   ├── writer.md              # Academic writing, anti-AI style rules, Mermaid diagrams
│   └── critic.md              # Examiner rubric, scoring scale, AI-detection criteria
└── test/
    └── text_1.md              # Sample ExPhil essay for testing
```

## Data flow

### RAG pipeline
1. User uploads PDF/TXT files → saved to `/tmp/uploads/{session_id}/`
2. `rag.ingest()` loads files → chunks with `RecursiveCharacterTextSplitter` (1000 chars, 200 overlap) → embeds with OpenAI `text-embedding-3-small` → builds FAISS index at `/tmp/vectorstore`
3. Searcher agent calls `rag_search(query, k=5)` → cosine similarity search over the index
4. Searcher also calls `web_search()` via Tavily (restricted to `plato.stanford.edu`, `iep.utm.edu`, `philpapers.org`, `jstor.org`, `cambridge.org`, `oxfordhandbooks.com`)

### WebSocket events
The frontend connects to `/ws/{session_id}` and receives real-time progress events:

| Event | Data |
|---|---|
| `agent_start` | Which agent is running |
| `agent_complete` | Agent finished |
| `draft_ready` | Full `EssayDraft` object |
| `critique_ready` | Full `CritiqueResult` object |
| `revision_start` | New iteration number |
| `stagnation` | Warning message |
| `tokens` | Per-call token usage and cost |
| `complete` | Final draft + total cost |
| `error` | Error message |

### Reference handling
The writer outputs Harvard-style references. The pipeline validates them post-generation:
- Detects placeholder values ("Ukjent", year 0)
- Checks inline citations match the reference list
- Critic prompt independently validates reference formatting
- `_parse_references()` uses three regex patterns with graceful fallback (skip unparseable lines rather than create garbage entries)

## Critic evaluation criteria

Weighted by importance in the prompt:

| Criterion | Weight | What it measures |
|---|---|---|
| Task answering | 25% | Does the essay answer what was asked? All parts addressed? |
| Philosophical depth | 25% | Genuine understanding vs. superficial summary |
| Argumentation structure | 20% | Logical flow, explicit premises, proportional treatment |
| Independent thinking | 15% | Own examples, own judgments, not just paraphrase → feeds `independence_score` |
| Source usage | 10% | Harvard citations, no cherry-picking, balance quotes vs. paraphrase |
| Language and authenticity | 5% | Academic style, AI-detection red flags |

Score scale: 1-3 F, 4-5 E, 5-6 D, 6-7 C, 7-8 B, 8-9 A/B, 9-10 A.

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...        # optional, enables web search
OPENAI_API_KEY=sk-...          # optional, for embeddings (use "fake" provider in config.py for testing)
```

Start:
```bash
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/upload` | POST | Upload PDF/TXT files, returns `session_id` |
| `/api/start` | POST | Start pipeline with task text and config |
| `/api/config` | GET/POST | Read/update agent config at runtime |
| `/api/session/{id}` | GET | Load persisted session state |
| `/api/sessions` | GET | List recent sessions |
| `/api/export/docx/{id}` | GET | Download essay as .docx |
| `/api/export/pdf/{id}` | GET | Download essay as .pdf |
| `/api/critique` | POST | Standalone re-critique of edited text |
| `/ws/{session_id}` | WS | Real-time progress streaming |

### Start pipeline

```json
POST /api/start
{
    "session_id": "uuid-from-upload",
    "task": "Gjør rede for Kants kategoriske imperativ...",
    "writer_config": { "max_words": 2000 },
    "evaluator_config": { "score_threshold": 8.0, "max_iterations": 5 }
}
```

## Configuration

Defaults in `config.py`:

| Setting | Default | Notes |
|---|---|---|
| Model (all agents) | `claude-sonnet-4-5-20250929` | Changeable per agent via `/api/config` |
| Writer temperature | 0.7 | Higher = more creative |
| Critic temperature | 0.2 | Lower = more consistent scoring |
| Score threshold | 7.5 | Weighted score needed for approval |
| Max iterations | 10 | Hard cap on revision cycles |
| Embeddings | OpenAI `text-embedding-3-small` | Set provider to `"fake"` for offline testing |
| Chunk size | 1000 chars | For RAG text splitting |

## Key dependencies

**Backend**: FastAPI, LangGraph, LangChain (Anthropic/OpenAI), FAISS, Tavily, pypdf, python-docx, reportlab, loguru, tenacity

**Frontend**: React 19, Vite 7, Tailwind CSS 4, framer-motion, react-markdown, mermaid, lucide-react

## Known limitations

- FAISS vectorstore is stored globally at `/tmp/vectorstore` — concurrent sessions overwrite each other
- Frontend is a single monolithic `App.jsx` (~2400 lines) — works for prototyping, not ideal for maintenance
- No automated test suite
- Session data stored at `/tmp/` — lost on OS cleanup/reboot
