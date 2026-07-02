# transom

Every property, decoded. Photos in, valuations out, at the speed of AI.

A multimodal AI platform for automated property assessment, valuation, and renovation intelligence. Ingests property photos, blueprints, inspection forms, and legal/valuation PDFs; produces structured property intelligence queryable in natural language via an MCP server.

## Documentation

Implementation reference is split across four modules in [`.agents/`](.agents/):

1. [Overview & Architecture](.agents/01-overview-and-architecture.md) — system overview, tech stack, design principle, repo structure
2. [Data Layer & Ingestion](.agents/02-data-layer-and-ingestion.md) — env setup, SQLite schema, PII redaction, ingestion pipelines
3. [Intelligence & Serving Layer](.agents/03-intelligence-and-serving-layer.md) — valuation module, RAG subsystem, MCP server, observability, backend API
4. [Frontend & Delivery](.agents/04-frontend-and-delivery.md) — frontend, end-to-end flow, build milestones, demo script

Build progress is tracked in [PROGRESS.md](PROGRESS.md); issues hit during implementation (and their fixes) are logged in [BUGS.md](BUGS.md); manual test runs are logged in [tests/test_log.txt](tests/test_log.txt).

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (async) |
| Structured DB | SQLite |
| Vector DB | Pinecone |
| RAG | LangChain + LangGraph |
| Vision / LLM | GPT-4o |
| OCR | Mistral OCR |
| Image preprocessing | OpenCV |
| PII redaction | Microsoft Presidio |
| Observability | Pydantic Logfire |
| Agent interface | MCP (Model Context Protocol) |
| Frontend | Vue.js 3 |

See [Module 1 §2](.agents/01-overview-and-architecture.md#2-tech-stack) for the full breakdown.

## Setup

```bash
uv pip install -r requirements.txt
python -m spacy download en_core_web_lg   # or: uv pip install en_core_web_lg@<wheel-url>, see BUGS.md #8
```

Copy `.env.example`-style keys into a local `.env` (gitignored, never commit it):

```
OPENAI_API_KEY=sk-...
MISTRAL_API_KEY=...
PINECONE_API_KEY=...
PINECONE_INDEX=property-intelligence
LOGFIRE_TOKEN=...
DATABASE_PATH=./property_intel.db
```

Initialize the database:

```bash
python backend/db/setup_db.py
```

Run the API:

```bash
uvicorn backend.main:app --reload --port 8000
```

Check it's up:

```bash
curl http://127.0.0.1:8000/health
```

## Repository structure

```
backend/
├── main.py                    # FastAPI app entry
├── db/                        # SQLite schema + setup
├── redaction/pii.py           # Presidio redact + tokenize
├── ingestion/
│   ├── preprocess.py          # OpenCV face/plate blur
│   ├── image_agent.py         # Photo → GPT-4o Vision → JSON
│   ├── blueprint_agent.py     # Blueprint → Mistral OCR + GPT-4o → fields
│   └── inspection_parser.py   # Inspection form → GPT-4o Vision → fields
├── valuation/calculator.py    # Deterministic value formulas
├── rag/                       # LangChain/LangGraph ingestion + retrieval
├── mcp/server.py              # MCP tool definitions
└── observability/logfire_config.py

frontend/                      # Vue.js 3 app
docs/                          # Reference PDFs, blueprints, test photos
tests/test_log.txt             # Manual test run log
```

Full structure: [Module 1 §4](.agents/01-overview-and-architecture.md#4-repository-structure).

## Build status

Tracking against the 8-milestone build order in [Module 4](.agents/04-frontend-and-delivery.md#16-build-order--milestones):

- [x] **Milestone 1 — Foundation**
- [x] **Milestone 2 — Photo pipeline**
- [x] **Milestone 3 — Structured extraction**
- [ ] **Milestone 4 — Valuation module**
- [ ] **Milestone 5 — RAG subsystem**
- [ ] **Milestone 6 — MCP server**
- [ ] **Milestone 7 — Frontend**
- [ ] **Milestone 8 — Polish + demo**

Full checklist and verification notes: [PROGRESS.md](PROGRESS.md).

## Known limitations

See [BUGS.md](BUGS.md) for the full list. Notably still open:

- Presidio's phone-number recognizer can occasionally misflag numeric cost ranges (e.g. `"4000-9000"`) as `PHONE_NUMBER` when no context words are nearby (BUGS.md #13) — accepted trade-off, not fixed, since a stricter threshold would also suppress real contextless phone number redaction.
