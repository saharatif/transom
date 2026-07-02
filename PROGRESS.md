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

## Milestone 2 — Photo pipeline ✅ COMPLETE

- [x] OpenCV preprocessing (`backend/ingestion/preprocess.py`) — verified against real photos, face blur confirmed on 2 test images (see `tests/test_log.txt`, Tests 1–2)
- [x] Presidio redaction layer (`backend/redaction/pii.py`) — verified round-trip (redact → de-tokenize) on sample text with PERSON/EMAIL/PHONE (see `tests/test_log.txt`, Test 3)
- [x] Image agent → GPT-4o Vision → JSON (`backend/ingestion/image_agent.py`) — verified end-to-end against a real damaged-property photo (see `tests/test_log.txt`, Test 4)
- [x] `/ingest/photo` endpoint wired end-to-end (`backend/main.py`) — verified via real HTTP POST with file upload (see `tests/test_log.txt`, Test 5)
- [x] Verify traces in Logfire — confirmed full nested span chain: `POST /ingest/photo` → `analyze_property_image` → `Chat Completion [LLM]` → `redact_and_tokenize` → `pii_detected`

## Milestone 3 — Structured extraction ✅ COMPLETE

- [x] Blueprint agent (`backend/ingestion/blueprint_agent.py`) — verified end-to-end against real blueprint PDF (see `tests/test_log.txt`, Test 6)
- [x] Inspection form parser (`backend/ingestion/inspection_parser.py`) — rewritten to use GPT-4o Vision on page images instead of Mistral OCR text (checkbox state was lost in OCR markdown, see BUGS.md #12); verified against real filled form (see `tests/test_log.txt`, Tests 7–8). Known open limitation: occasional PHONE_NUMBER false-positive on numeric cost ranges (BUGS.md #13)
- [x] `/ingest/blueprint` and `/ingest/inspection` endpoints (`backend/main.py`) — both verified via real HTTP POST requests, Logfire traces confirmed (see `tests/test_log.txt`, Tests 9–10)

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
