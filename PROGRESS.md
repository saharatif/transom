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

## Milestone 4 — Valuation module ✅ COMPLETE

- [x] `backend/valuation/calculator.py` — built directly from `docs/pdfs/texas_property_valuation_formulas.pdf` (not the inspector's per-property estimates in the filled inspection form), per user instruction
- [x] Unit tests against worked examples — base value ($288,000), renovation-adjusted value ($320,000, net equity $10,000), and all 6 ROI multipliers reproduced exactly from the source PDF; neighborhood ceiling cap verified separately (see `tests/test_log.txt`, Tests 11–12)

## Milestone 5 — RAG subsystem ✅ COMPLETE

- [x] LangChain ingestion (`backend/rag/ingestion.py`) — verified against real warranty PDF (229 chunks); added section-header metadata tagging after a grounding bug was found (see BUGS.md #15)
- [x] Pinecone index setup — created `property-intelligence` index (dimension 1536, cosine, serverless aws/us-east-1)
- [x] Retriever + reranker (`backend/rag/retrieval.py`) — widened k=5→6, top_n=3→4 after the reranker was found to discard the correct chunk on a real query (BUGS.md #15)
- [x] LangGraph agent (`backend/rag/graph.py`) — fixed a node/state-key name collision (BUGS.md #14); verified end-to-end against a real warranty clause with correct section citation (`§ 7`) after the grounding fix (see `tests/test_log.txt`, Tests 13–15)

## Milestone 6 — MCP server ✅ CORE COMPLETE

- [x] MCP tools (`backend/mcp/server.py`) — all 6 tools verified end-to-end against real persisted data (see `tests/test_log.txt`, Test 18). Required upgrading `mcp==1.1.0`→`1.28.1` (no `FastMCP` API existed in the old pin, BUGS.md #16)
- [x] Along the way: fixed a real gap where `/ingest/*` endpoints never persisted to SQLite (BUGS.md #17) — added `save_photo_assessment`/`save_blueprint_fields`/`save_inspection_form` to `backend/db/queries.py`, changed `property_id` from `str` to `int` on all three endpoints to match schema, and extended `inspection_parser.py` to also capture the form's PROPERTY DETAILS header (builder, year_built) since `calculate_renovation_roi` needs `year_built`
- [ ] Connect to Claude Desktop — not done in this session (requires local Claude Desktop MCP config, a manual/interactive step outside automated testing)

## Milestone 7 — Frontend ✅ COMPLETE

- [x] Vue upload + property card + renovation table + chat — built to `design/DESIGN.md` spec (light/dark theme tokens, 3-column dashboard, sidebar nav, theme toggle). Components: `Sidebar`, `ThemeToggle`, `FileUpload`, `PropertyCard`, `RenovationTable`, `ChatPanel`
- [x] Wire to FastAPI — added `/property/{id}`, `/contractors`, `/chat` endpoints (not previously wired); visually verified end-to-end via headless Chromium screenshots in both themes, plus a real chat interaction through the live UI (see `tests/test_log.txt`, Tests 19–20)
- Fixed along the way: a `localhost` vs `127.0.0.1` IPv6/IPv4 resolution bug breaking all frontend→backend fetches (BUGS.md #18), and a flexbox `flex-shrink` bug that was silently clipping `PropertyCard`/`RenovationTable` content (BUGS.md #19)

## Milestone 8 — Polish + demo

- [ ] Demo video
- [ ] README, architecture diagram
- [ ] Logfire dashboard review
