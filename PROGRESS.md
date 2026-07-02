# Progress Log

Tracks build progress against the milestones in [.agents/04-frontend-and-delivery.md](.agents/04-frontend-and-delivery.md#16-build-order--milestones).

## Milestone 1 — Foundation ✅ COMPLETE

- [x] Repo scaffold (`backend/`, `frontend/`, `docs/` per [.agents/01-overview-and-architecture.md](.agents/01-overview-and-architecture.md#4-repository-structure))
- [x] `requirements.txt` populated
- [x] `.env` populated with API keys (gitignored)
- [x] SQLite schema (`backend/db/schema.sql`) — 8 tables + seeded contractors
- [x] `backend/db/setup_db.py` — DB initialization script
- [x] Logfire config (`backend/observability/logfire_config.py`)
- [x] Basic FastAPI app boots (`backend/main.py`, `/health` endpoint)
- [x] `__init__.py` added to `backend/` and all subpackages
- [x] Verified: `uvicorn backend.main:app --reload --port 8000` boots cleanly, `GET /health` returns `200 OK` (`curl -sv http://127.0.0.1:8000/health`), and a request trace confirmed live in the Logfire dashboard

## Milestone 2 — Photo pipeline

- [x] OpenCV preprocessing (`backend/ingestion/preprocess.py`) — verified against real photos, face blur confirmed on 2 test images (see `tests/test_log.txt`, Tests 1–2)
- [x] Presidio redaction layer (`backend/redaction/pii.py`) — verified round-trip (redact → de-tokenize) on sample text with PERSON/EMAIL/PHONE (see `tests/test_log.txt`, Test 3)
- [x] Image agent → GPT-4o Vision → JSON (`backend/ingestion/image_agent.py`) — verified end-to-end against a real damaged-property photo (see `tests/test_log.txt`, Test 4)
- [ ] `/ingest/photo` endpoint wired end-to-end
- [ ] Verify traces in Logfire (pending — endpoint not yet wired; ad-hoc test scripts didn't call `logfire.configure()`)

## Milestone 3 — Structured extraction

- [ ] Blueprint agent (`backend/ingestion/blueprint_agent.py`)
- [ ] Inspection form parser (`backend/ingestion/inspection_parser.py`)
- [ ] `/ingest/blueprint` and `/ingest/inspection` endpoints

## Milestone 4 — Valuation module

- [ ] `backend/valuation/calculator.py`
- [ ] Unit tests against worked examples

## Milestone 5 — RAG subsystem

- [ ] LangChain ingestion (`backend/rag/ingestion.py`)
- [ ] Pinecone index setup
- [ ] Retriever + reranker (`backend/rag/retrieval.py`)
- [ ] LangGraph agent (`backend/rag/graph.py`)

## Milestone 6 — MCP server

- [ ] MCP tools (`backend/mcp/server.py`)
- [ ] Connect to Claude Desktop

## Milestone 7 — Frontend

- [ ] Vue upload + property card + renovation table + chat
- [ ] Wire to FastAPI

## Milestone 8 — Polish + demo

- [ ] Demo video
- [ ] README, architecture diagram
- [ ] Logfire dashboard review
