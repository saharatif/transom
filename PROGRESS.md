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
- [x] Follow-up fix (post-Milestone 7): the agent's yes/no conclusion was found to flip-flop across identical runs even with correct grounding (BUGS.md #20). Added `backend/rag/measurement.py` to do inch-measurement comparisons deterministically in code, plus an explicit two-step reasoning rule in `answer_node` — verified 5/5 consistent runs, correct in both directions (see `tests/test_log.txt`, Test 21)

## Milestone 6 — MCP server ✅ CORE COMPLETE

- [x] MCP tools (`backend/mcp/server.py`) — all 6 tools verified end-to-end against real persisted data (see `tests/test_log.txt`, Test 18). Required upgrading `mcp==1.1.0`→`1.28.1` (no `FastMCP` API existed in the old pin, BUGS.md #16)
- [x] Along the way: fixed a real gap where `/ingest/*` endpoints never persisted to SQLite (BUGS.md #17) — added `save_photo_assessment`/`save_blueprint_fields`/`save_inspection_form` to `backend/db/queries.py`, changed `property_id` from `str` to `int` on all three endpoints to match schema, and extended `inspection_parser.py` to also capture the form's PROPERTY DETAILS header (builder, year_built) since `calculate_renovation_roi` needs `year_built`
- [ ] Connect to Claude Desktop — not done in this session (requires local Claude Desktop MCP config, a manual/interactive step outside automated testing)

## Milestone 7 — Frontend ✅ COMPLETE

- [x] Vue upload + property card + renovation table + chat — built to `design/DESIGN.md` spec (light/dark theme tokens, 3-column dashboard, sidebar nav, theme toggle). Components: `Sidebar`, `ThemeToggle`, `FileUpload`, `PropertyCard`, `RenovationTable`, `ChatPanel`
- [x] Wire to FastAPI — added `/property/{id}`, `/contractors`, `/chat` endpoints (not previously wired); visually verified end-to-end via headless Chromium screenshots in both themes, plus a real chat interaction through the live UI (see `tests/test_log.txt`, Tests 19–20)
- Fixed along the way: a `localhost` vs `127.0.0.1` IPv6/IPv4 resolution bug breaking all frontend→backend fetches (BUGS.md #18), and a flexbox `flex-shrink` bug that was silently clipping `PropertyCard`/`RenovationTable` content (BUGS.md #19)
- [x] Follow-up fixes (found via real interactive use of the live dashboard, not scripted tests): blueprint bedroom/bathroom count was flipping between runs on an ambiguous room-numbering label (BUGS.md #21), and the renovation cost table went blank when GPT-4o returned a third, different JSON shape for `renovation_cost_estimate` (BUGS.md #22). Both fixed by tightening extraction prompts to remove ambiguity/enforce a fixed schema, verified 3/3 consistent runs each, and confirmed live in the dashboard (see `tests/test_log.txt`, Test 22)
- [x] User-requested polish: real `design/` logo in the header (replacing plain text), a manual refresh button, multi-file upload for Property Photo/Blueprint (Inspection Form stays single-file), a new "That 1 Painter" contractor seeded in `renovation_companies` (and mapped to the "Paint (interior)" renovation category), and wired the existing valuation calculator into ingestion persistence so `estimated_value` actually gets computed instead of staying `NULL` forever (BUGS.md #23) — all verified live (see `tests/test_log.txt`, Test 23)
- [x] Recreated the `design/` logo as light/dark SVG variants (`design/transom-logo-{light,dark}.svg`), sized up in the header, and wired a theme-based swap. Found and fixed two real bugs along the way: an invalid `--` sequence inside the dark SVG's XML comment silently broke the whole image (BUGS.md #24), and the CSS `:global()` approach for the theme swap never actually compiled (BUGS.md #25) — replaced with a `MutationObserver`-driven `v-if`/`v-else` in `App.vue`. Verified both variants render correctly and swap live in the browser (see `tests/test_log.txt`, Test 24)
- [x] Finally fixed the long-open `pii.py` PHONE_NUMBER false-positive on currency ranges (BUGS.md #13/#26) — a context-adjacency check ("USD"/"$"/"dollars" immediately following a match) rather than a confidence threshold, per a user-proposed heuristic based on the actual observed data. While re-verifying, caught a fresh regression it would have been easy to miss: the blueprint extraction prompt started returning `0` instead of `null` for bedroom/bathroom counts on sheets with no room info, silently clobbering good data via `COALESCE` (BUGS.md #27) — fixed both the prompt and added a `NULLIF`-based persistence-layer safeguard given this field's repeat-incident history. Both verified live (see `tests/test_log.txt`, Test 26)
- [x] Dashboard UX/UI upgrade to a "premium SaaS dashboard" reference mockup — scoped to visual polish only (confirmed with user first; skipped nav items with no real backend behind them, like Portfolio/Clients/Reports/Organization Selector). Dark mode is now the default theme. Widened + labeled the sidebar, added a top bar with a functional "jump to property ID" search, upgraded FileUpload into a tabbed Active Queue / Upload History view with per-file progress indicators, added a Quick Actions row to PropertyCard (refresh / open photo / copy ID — all real, not decorative), made RenovationTable's columns sortable + filterable with a full contractor dropdown per row, and added suggested-question chips to ChatPanel using real, previously-verified warranty questions. All changes functionally smoke-tested (sort, filter, dropdown, chip→real chat round trip) and verified live in both themes (see `tests/test_log.txt`, Test 28)

## Robustness & UX hardening pass ✅ COMPLETE (2026-07-05)

Full-codebase review with four goals: better coding strategies, improved logic, a more professional UX/UI, and everything tested + documented.

**Backend correctness fixes (each has a full BUGS.md entry):**
- [x] PII tokenization collision — two people in one document collapsed into one token, corrupting de-tokenization (BUGS.md #28); replaced the anonymizer step with direct span splicing + overlap handling
- [x] `preprocess.py` path handling (`str.replace(".", ...)` broke on dotted filenames) and unreadable-image crashes now fail with clear errors (BUGS.md #29)
- [x] Upload handling: path-traversal-safe uuid temp files, per-doc-type extension allowlists (415s), post-processing cleanup, agent failures as 502-with-reason, `/property` 404s, blank-chat 422s, CORS narrowed to dev origins, and sync endpoints so OCR/Vision work doesn't block the event loop (BUGS.md #30)
- [x] Shared `parse_llm_json()` (`backend/ingestion/llm_json.py`) replaces fragile fence-stripping + bare `json.loads` in all three agents — finds the balanced JSON payload in any LLM reply and raises diagnosable errors; image agent also stops mislabeling PNGs as `image/jpeg`
- [x] `queries.py` connections through a commit/close context manager (no more leaked handles on exceptions); valuation calculator validates categories/costs/sqft with named-option error messages; MCP `calculate_renovation_roi` guards missing properties/fields
- [x] RAG graph logic overhaul (BUGS.md #33): per-excerpt relevance grading (the blob yes/no grader was deterministically rejecting good retrievals), rewrites now touch only a separate `retrieval_query` (the user's question is never mutated), and the measurement comparison narrows to subject-matching sentences so it fires on real mixed-threshold retrievals — verified 5/5 consistent correct answers in both directions
- [x] Photo persistence wiring regression introduced mid-refactor, caught live and pinned with tests (BUGS.md #32) — `property_images.image_path` now stores the kept `_safe` blurred copy

**Frontend UX/UI professionalization:**
- [x] Design-token layer in `theme.css`: rem type scale (`--text-xs`…`--text-xl`) replacing scattered pt sizes, semantic status colors (`--color-success/warning/danger`) replacing hardcoded hexes in five components, refined light mode (soft-gray page, white cards), radius tokens, shared skeleton shimmer
- [x] `AppIcon.vue` — one inline-SVG stroke icon set (20 icons) replacing every emoji in the UI, platform-consistent and theme-aware
- [x] Toast notifications (`useToasts` + `ToastHost`, aria-live) — upload success/failure and clipboard errors now surface in the UI instead of dying in the console; failure toasts carry the backend's actual error message
- [x] Sidebar navigation now actually navigates: Dashboard / focused Upload / focused Chat / Settings views (settings has theme control, backend connectivity status, active property). Upload history and the chat transcript moved to shared composables so the dashboard and focused views show one session state
- [x] PropertyCard skeleton loading state; "property not found" messaging distinct from "backend unreachable"; API client with timeouts (AbortController) that surfaces FastAPI `detail` messages
- [x] Fixed the contractor dropdown resetting on every sort (read/write key mismatch — BUGS.md #31); sortable-header `aria-sort`; chat renders multi-line answers (`pre-wrap`) with a Retry button on failures
- [x] Visually verified via headless Chromium in both themes across all four views; live E2E: real photo upload (success toast → history row → DB row) and real chat round trip with § 7 citation (see `tests/test_log.txt` Tests 29–31)

**Testing:**
- [x] New pytest suite `tests/unit/` — 66 tests, all passing: valuation formulas (PDF worked examples pinned), measurement extraction/comparison (incl. the real mixed-threshold scenario), `parse_llm_json`, PII round-trips (two-person regression for #28, currency filter), DB persistence safeguards (NULLIF zero-guard, estimated-value trigger, all three renovation JSON shapes), and FastAPI endpoint wiring with mocked agents (415/404/422/502 paths, safe-path persistence). Run: `uv run pytest tests/unit`

**Follow-up (user request):**
- [x] Reset-database button in Settings — `POST /reset` wipes all ingested data (properties + child tables + PII token map) while keeping the seeded contractor directory and the Pinecone warranty index; frontend gates it behind a two-step confirm, clears the session's upload history/chat transcript, and shows the fresh empty state. Unit-tested + verified live (see `tests/test_log.txt` Test 32)

## Milestone 8 — Polish + demo

- [ ] Demo video
- [ ] README, architecture diagram
- [ ] Logfire dashboard review
