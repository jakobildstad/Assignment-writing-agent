# Exphil Agent

Multi-agent system som skriver akademiske essay for ExPhil (NTNU). Laster opp pensum, søker i kilder, skriver utkast, evaluerer, og reviderer automatisk.

## Arkitektur

```
START → searcher → writer → critic → evaluator ─┐
           ↑                                      │
           └────── writer (revise) ←── (avvist) ──┘
                                       (godkjent) → END
```

| Agent | Rolle |
|---|---|
| **Searcher** | Søker i pensum (RAG/FAISS) og på nett (Tavily) |
| **Writer** | Skriver akademisk essay med kildehenvisninger |
| **Critic** | Evaluerer utkast og gir strukturert feedback |
| **Evaluator** | Avgjør om essayet er godt nok eller trenger revisjon |

## Prosjektstruktur

```
exphil-agent/
├── backend/
│   ├── main.py              # FastAPI app, CORS, WebSocket, REST-endepunkter
│   ├── orchestrator.py      # LangGraph pipeline (StateGraph)
│   ├── config.py            # Modell/temperatur/terskel-innstillinger
│   ├── rag.py               # PDF/TXT-inntak → FAISS vectorstore
│   ├── agents/
│   │   ├── searcher.py      # ReAct-agent med rag_search + web_search tools
│   │   ├── writer.py        # Essay-generering med revisjonsstøtte
│   │   ├── critic.py        # Strukturert evaluering (score, feedback)
│   │   └── evaluator.py     # Terskel-basert godkjenning/avvisning
│   ├── requirements.txt
│   └── .env                 # API-nøkler (ikke commit)
├── frontend/
│   ├── src/App.jsx          # React-app med upload, start, progress-log
│   └── vite.config.js       # Vite + Tailwind + proxy til backend
└── prompts/
    ├── searcher.md           # Søkestrategi og kildeprioritering
    ├── writer.md             # Akademisk skriving, ExPhil-konvensjoner
    └── critic.md             # Sensor-perspektiv, evalueringskriterier
```

## Oppsett

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Opprett `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...        # valgfritt, for nettsøk
OPENAI_API_KEY=sk-...          # valgfritt, for embeddings
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

Åpne http://localhost:5173

## API

| Endepunkt | Metode | Beskrivelse |
|---|---|---|
| `/api/upload` | POST | Last opp PDF/TXT-filer |
| `/api/start` | POST | Start pipeline med oppgavetekst |
| `/api/config` | GET/POST | Hent/oppdater agent-konfigurasjon |
| `/ws/{session_id}` | WS | Progress-streaming |

### Start pipeline

```json
POST /api/start
{
    "session_id": "uuid-fra-upload",
    "task": "Gjør rede for Kants kategoriske imperativ...",
    "writer_config": { "max_words": 2000 },
    "evaluator_config": { "score_threshold": 8.0, "max_iterations": 2 }
}
```

## Konfigurasjon

Defaults i `config.py`:

- **Modell**: `claude-sonnet-4-5-20250929` for alle agenter
- **Score-terskel**: 7.5/10 for godkjenning
- **Maks iterasjoner**: 3 (søk → skriv → evaluer-looper)
- **Embeddings**: OpenAI `text-embedding-3-small` (bruk `"fake"` for testing uten API-nøkkel)
