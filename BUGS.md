# Bug Log

Tracks issues hit during implementation and their resolutions.

## Resolved

### 1. `uv pip install -r requirements.txt` — dependency conflict

**Error:**
```
× No solution found when resolving dependencies:
  ╰─▶ Because fastapi==0.115.0 depends on starlette>=0.37.2,<0.39.0 and mcp==1.1.0 depends on
      starlette>=0.39, we can conclude that fastapi==0.115.0 and mcp==1.1.0 are incompatible.
```

**Cause:** `fastapi==0.115.0` pinned `starlette<0.39`, but `mcp==1.1.0` requires `starlette>=0.39`.

**Fix:** Loosened pin to `fastapi>=0.115.6` in `requirements.txt`, allowing the resolver to pick a `fastapi` release compatible with the `starlette` version `mcp` needs.

### 2. `uvicorn main:app --reload` — could not import module "main"

**Error:**
```
ERROR:    Error loading ASGI app. Could not import module "main".
```

**Cause:** `main.py` was moved to `backend/main.py` (matching the repo structure in [.agents/01-overview-and-architecture.md](.agents/01-overview-and-architecture.md#4-repository-structure)), but uvicorn was still pointed at a root-level `main:app`. Additionally, `backend/main.py` uses relative imports (`from .observability.logfire_config import init_logfire`), which requires `backend` to be importable as a package.

**Fix:**
- Run `uvicorn backend.main:app --reload --port 8000` from the repo root instead.
- Added `__init__.py` to `backend/` and all subpackages (`db/`, `redaction/`, `ingestion/`, `valuation/`, `rag/`, `mcp/`, `observability/`) so relative imports resolve correctly.

### 3. `uvicorn backend.main:app` — `ModuleNotFoundError: No module named 'importlib_metadata'`

**Error:**
```
File ".../logfire/version.py", line 3, in <module>
    import importlib_metadata
ModuleNotFoundError: No module named 'importlib_metadata'
```

**Cause:** `logfire` imports `importlib_metadata` (the backport package) at startup on Python 3.10, but it wasn't present in the environment — likely skipped by the resolver or not installed after the `fastapi` pin change.

**Fix:** Added `importlib_metadata>=6.0` to `requirements.txt`. Re-run `uv pip install -r requirements.txt` to install it.

### 4. `uvicorn backend.main:app` — `KeyError: 'LOGFIRE_TOKEN'`

**Error:**
```
File ".../backend/observability/logfire_config.py", line 5, in init_logfire
    logfire.configure(token=os.environ["LOGFIRE_TOKEN"], service_name="property-intel")
KeyError: 'LOGFIRE_TOKEN'
```

**Cause:** `.env` is not automatically loaded into the process environment by plain `os.environ` — nothing was reading the `.env` file, so `LOGFIRE_TOKEN` (and the other keys) were never actually set when the app started.

**Fix:** Added `python-dotenv==1.0.1` to `requirements.txt` and called `load_dotenv()` at the top of `backend/main.py` before `init_logfire()`, so `.env` is loaded into `os.environ` at startup.

### 5. `uvicorn backend.main:app` — `ModuleNotFoundError: No module named 'opentelemetry.instrumentation.asgi'`

**Error:**
```
File ".../logfire/_internal/integrations/asgi.py", line 7, in <module>
    from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
ModuleNotFoundError: No module named 'opentelemetry.instrumentation.asgi'
```

**Cause:** `logfire.instrument_fastapi()` requires the ASGI OpenTelemetry instrumentation package, which is an optional extra (`logfire[fastapi]`) — not installed by the plain `logfire` package.

**Fix:** Changed `logfire==2.6.0` to `logfire[fastapi]==2.6.0` in `requirements.txt`.

### 6. `uvicorn backend.main:app` — `TypeError: MeterProvider.get_meter() got multiple values for argument 'version'`

**Error:**
```
File ".../logfire/_internal/metrics.py", line 56, in get_meter
    provider.get_meter(name, version=version, schema_url=schema_url, *args, **kwargs),
TypeError: MeterProvider.get_meter() got multiple values for argument 'version'
```

**Cause:** `logfire==2.6.0` was pinned exactly, but its `[fastapi]` extra pulled in newer, mutually-incompatible `opentelemetry-instrumentation-fastapi`/`asgi` packages (0.64b0) whose API had drifted from what logfire 2.6.0's internals expected — a version-skew bug from pinning one package tightly while its extras float.

**Fix:** Relaxed to `logfire[fastapi]>=4.37.0` and force-upgraded (`uv pip install --upgrade "logfire[fastapi]" opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-asgi`) so the whole OTel stack resolved together as a consistent set (logfire 4.37.0 + otel 1.42.1/0.63b1).

### 7. `uvicorn backend.main:app` — `ModuleNotFoundError: No module named 'openai.lib.streaming.responses'`

**Error:**
```
File ".../logfire/_internal/integrations/llm_providers/openai.py", line 9, in <module>
    from openai.lib.streaming.responses import ResponseStreamState
ModuleNotFoundError: No module named 'openai.lib.streaming.responses'
```

**Cause:** After upgrading `logfire` to 4.37.0, `logfire.instrument_openai()` requires OpenAI SDK APIs not present in the pinned `openai==1.54.0`.

**Fix:** Upgraded to `openai>=2.44.0` in `requirements.txt`. This also pulled in `pydantic` 2.13.4, so the exact `pydantic==2.9.0` pin was relaxed to `pydantic>=2.9.0` to avoid a resolver conflict.

**Verified:** `uvicorn backend.main:app --port 8000` boots cleanly and `GET /health` returns `{"status": "ok"}`.

### 8. `AnalyzerEngine()` — `ModuleNotFoundError: No module named 'pip'`

**Error:**
```
/Users/saharatif/transom/.venv/bin/python3: No module named pip
```

**Cause:** Presidio's `AnalyzerEngine()` loads a spaCy NLP model (`en_core_web_lg`) on init. It wasn't installed, and spaCy's fallback auto-download path shells out to `python -m pip install ...` — but this `uv`-managed venv has no `pip` module, so it failed with a misleading, stack-trace-free error instead of a clear "model not found" message.

**Fix:** Installed the model wheel directly via `uv pip install en_core_web_lg@https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.1/en_core_web_lg-3.7.1-py3-none-any.whl` (the equivalent of the `python -m spacy download en_core_web_lg` step in [Module 2 §5](.agents/02-data-layer-and-ingestion.md#install), which must be run separately in `uv` environments since spaCy's downloader depends on `pip` being present).

**Verified:** `redact_and_tokenize()` / `de_tokenize()` round-trip tested against a sample string (name, email, phone) — see `pii_text_output.txt`. All three PII types detected, tokenized, and correctly restored.

### 9. `uvicorn backend.main:app` — `openai.OpenAIError: Missing credentials` after wiring `/ingest/photo`

**Error:**
```
File "/Users/saharatif/transom/backend/ingestion/image_agent.py", line 7, in <module>
    client = OpenAI()
openai.OpenAIError: Missing credentials. Please pass an `api_key` ... or set the `OPENAI_API_KEY` ... environment variable.
```

**Cause:** In `backend/main.py`, `from .ingestion.image_agent import analyze_property_image` was placed *before* `load_dotenv()`. `image_agent.py` instantiates `OpenAI()` at module import time, so it ran before `.env` had been loaded into the process environment, even though `load_dotenv()` was present later in the same file.

**Fix:** Moved `load_dotenv()` to the very top of `backend/main.py`, before any local imports that trigger API-client construction at import time.

### 10. `blueprint_agent.py` — `AttributeError: 'Mistral' object has no attribute 'ocr'`

**Error:**
```
File "/Users/saharatif/transom/backend/ingestion/blueprint_agent.py", line 19, in process_blueprint
    ocr_resp = mistral.ocr.process(
AttributeError: 'Mistral' object has no attribute 'ocr'
```

**Cause:** `requirements.txt` pinned `mistralai==1.2.0`, which predates Mistral's OCR API — the client has no `.ocr` attribute at all in that version.

**Fix attempt 1 (bad):** `uv pip install --upgrade mistralai` jumped straight to `mistralai==2.5.1`, which has two problems:
- Its published wheel is missing a top-level `__init__.py` entirely (confirmed via the package's `RECORD` file) — `from mistralai import Mistral` fails with `ImportError`; only the internal path `from mistralai.client.sdk import Mistral` works. This looks like a broken/incomplete PyPI release, not something to build against.
- The upgrade pulled `opentelemetry-api` down to `1.39.1` and `opentelemetry-semantic-conventions` to `0.60b1`, breaking logfire's Pydantic plugin again (`ImportError: cannot import name '_ON_EMIT_RECURSION_COUNT_KEY' from 'opentelemetry.context'`) — the same category of version-skew bug as #6.

**Fix (final):** Pinned `mistralai==1.5.2` instead — has both a clean `from mistralai import Mistral` import and `.ocr.process()` support, without disturbing other dependencies. Then re-ran `uv pip install --upgrade "logfire[fastapi]" opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-asgi opentelemetry-api opentelemetry-sdk` to restore the known-good OTel set (`opentelemetry-api==1.42.1`, `opentelemetry-semantic-conventions==0.63b1`). Added explicit lower-bound pins for both in `requirements.txt` to stop a future package upgrade from silently downgrading them again.

**Lesson:** Blindly `--upgrade`-ing to "latest" in this dependency graph is risky — several packages here (`mistralai`, `logfire`, `openai`) have interlocking OTel/version requirements. Prefer targeted version pins over open-ended upgrades once a working set is found.

### 11. `blueprint_agent.py` — `pydantic_core.ValidationError` on `mistral.ocr.process()` call

**Error:**
```
pydantic_core._pydantic_core.ValidationError: 4 validation errors for Unmarshaller
body.ImageURLChunk.image_url
  Field required [type=missing, input_value={'type': 'document', 'doc...}, input_type=dict]
body.ImageURLChunk.type
  Input should be 'image_url' [type=literal_error, input_value='document', input_type=str]
body.DocumentURLChunk.document_url
  Field required [type=missing, ...]
body.DocumentURLChunk.type
  Input should be 'document_url' [type=literal_error, input_value='document', input_type=str]
```

**Cause:** The `document={"type": "document", "document": f.read()}` payload shape from [Module 2 §8.3](.agents/02-data-layer-and-ingestion.md#83-blueprint-agent) doesn't match this SDK version's actual schema. The real `mistralai` OCR API only accepts a `DocumentURLChunk` (`{"type": "document_url", "document_url": <url or base64 data URI>}`) or an `ImageURLChunk` — not raw file bytes under a `"document"` key.

**Fix:** Base64-encode the PDF and pass it as a data URI: `{"type": "document_url", "document_url": f"data:application/pdf;base64,{pdf_b64}"}`.

Also found: `ocr_resp.text` doesn't exist on `OCRResponse` — text comes back per-page as `ocr_resp.pages[i].markdown`. Fixed by joining all pages: `"\n\n".join(page.markdown for page in ocr_resp.pages)`.

**Verified:** `process_blueprint()` tested end-to-end against a real blueprint PDF (`docs/Blueprints/Blueprint_A101_Ground_Floor.pdf`) — see `tests/test_log.txt`.

### 12. `inspection_parser.py` — Mistral OCR text extraction loses checkbox state

**Symptom:** Parsing the filled inspection form via `mistral.ocr.process()` + GPT-4o text extraction (same pattern as `blueprint_agent.py`) returned almost all fields empty. Only `kitchen_condition` and `renovation_cost_estimate` populated.

**Cause:** Inspected the raw OCR markdown output directly — for checkbox sections, Mistral OCR renders every option as plain bullet text with no indication of which box was checked:
```
# 3.1 Paint Condition

Fresh / excellent
Fair-fading/patches
Water stains present
Cracks in walls
```
The checkbox glyph (☐/☑) and any checkmark are dropped in the markdown conversion — the checked/unchecked distinction is lost *before* GPT-4o ever sees the text, so no prompt change can recover it. (`kitchen_condition` only worked by accident — one checkmark happened to render as a LaTeX `\boxed{}` artifact.)

**Fix:** Rewrote `inspection_parser.py` to use GPT-4o **Vision** directly on rendered page images (via `pymupdf`/`fitz`, added to `requirements.txt`) instead of Mistral OCR text — same approach as `image_agent.py`. A vision model can actually see which checkbox is marked. Sends all pages in one Vision call so the model has full form context.

**Trade-off:** Since there's no OCR-text step to redact before this Vision call, the raw form (including inspector name/license number) reaches the external API unredacted, same as photos in `image_agent.py` — redaction only happens on the JSON *output*, not the input image. This matches the documented pattern in [Module 2 §7](.agents/02-data-layer-and-ingestion.md#7-pii-redaction-layer) ("Photos: GPT-4o Vision (unavoidable) → redact after").

**Verified:** Nearly all fields now extract correctly (floor type/condition, wood grade, paint, roof, HVAC age, kitchen, bathroom) against the real filled form — see `tests/test_log.txt`.

### 13. (Known limitation, not fixed) `renovation_cost_estimate` — cost ranges occasionally misredacted as PHONE_NUMBER

**Symptom:** In the Vision-extracted `renovation_cost_estimate` string, two entries were corrupted: `"Flooring refinish: [PHONE_NUMBER_XXXXXX] USD"` instead of `"4000-9000 USD"`. Presidio's phone-number recognizer pattern-matched the digit-hyphen-digit shape (`"4000-9000"`, `"3000-7000"`) as a phone number.

**Investigated fix:** Tried raising `analyzer.analyze()`'s `score_threshold` to filter low-confidence matches. Found both the false positive and a *real* phone number with no nearby context words (e.g. no "phone"/"call"/"tel" nearby) score identically at `0.4` — Presidio only boosts phone-number confidence when context clues are present. A threshold high enough to drop the false positive would also silently stop redacting real, contextless phone numbers elsewhere in the system — a worse failure mode (missed PII) than this one (corrupted cost data).

**Decision:** Left `pii.py` unchanged. `pii.py` is a shared module used by every ingestion pipeline; a narrow fix for this one call site isn't worth the risk of weakening PII detection everywhere else.

**Status:** Open / accepted trade-off. Revisit if this becomes a recurring problem — options discussed: per-call-site `context=[...]` hints to Presidio (boosts real phone matches without touching the shared default), or a stricter phone-format regex requiring realistic digit groupings.

### 14. `graph.py` — `ValueError: 'answer' is already being used as a state key`

**Error:**
```
File ".../langgraph/graph/state.py", line 318, in add_node
    raise ValueError(f"'{node}' is already being used as a state key")
ValueError: 'answer' is already being used as a state key
```

**Cause:** `build_rag_graph()` registered a node named `"answer"` (`g.add_node("answer", answer_node)`), which collides with the `answer` field already declared in `RAGState`. This version of `langgraph` (0.2.45, matching the pin exactly — not a version-drift issue) rejects a node name that shadows a state key.

**Fix:** Renamed the node to `"generate_answer"` in `add_node`, `add_conditional_edges`'s mapping, and `add_edge`, while keeping the `RAGState.answer` field and `return {**state, "answer": ...}` untouched — the node name and the state field it writes to are independent.

### 15. `rag_agent` — LLM cites the wrong section number / possible hallucination not grounded in retrieval

**Symptom:** Asked the agent `"Is a 1/8 inch crack in the master bath drywall covered under warranty?"` against the real ingested `Warranty_documents.pdf`. The answer was substantively correct (1/8" exceeds the real 1/32" threshold in § 7) but cited `"Section 2"` — the actual clause is under **§ 7. Performance Standards for Drywall**.

**Investigation:**
- Confirmed the real clause exists in the source PDF: `"(c) A drywall surface shall not crack such that any crack equals or exceeds 1/32 of an inch in width..."` under `§ 7. Performance Standards for Drywall`.
- Inspected the 3 chunks the reranked retriever actually returned for that question — **none of them contained the "1/32 of an inch" clause at all.** The model's answer was not grounded in what it retrieved, despite the system prompt saying "Answer using ONLY the sources" — it appears to have answered from outside knowledge of this standard TAB warranty document (or paraphrased/inferred from an adjacent but wrong clause), not from the provided context.
- Ran the raw MMR retriever (before reranking) with the same question directly: **the correct chunk was present at position 0 of 5 candidates.** The `CrossEncoderReranker` (top_n=3) demoted it out of the final top 3 — likely because a different, wrong chunk (a stucco crack-width clause, also mentioning "1/8 of an inch") scored higher by lexical/surface similarity to the query's "1/8 inch" phrase, despite being about the wrong material entirely.
- Separately found chunk metadata carried no section-number field at all — even a correctly retrieved chunk had no reliable way to be cited by section number; the LLM would have to infer it from surrounding prose (chunks near a section boundary don't always repeat the "§ N. ..." header).

**Fix:**
- `backend/rag/ingestion.py`: added `_section_map()` / `_section_for_chunk()` to tag every chunk with its real nearest-preceding section header (e.g. `"§ 7. Performance Standards for Drywall"`) as `metadata["section"]`, computed from character offsets in the source text at ingestion time.
- `backend/rag/retrieval.py`: widened `build_retriever()` from `k=5/top_n=3` to `k=6/top_n=4` (and `fetch_k` 20→24) — reduces the chance the reranker discards the one chunk that actually answers the question.
- `backend/rag/graph.py`: `answer_node` now prefixes each source chunk with its real `[§ N. ...]` section tag (from ingestion metadata) instead of a generic `[source chunk i]` label, and the prompt tells the model to cite that exact bracketed header. Citation regex updated to also catch `§ \d+` format.

**Verified:** Re-ingested the warranty PDF (`docs/pdfs/Warranty_documents.pdf`) with the fixed pipeline. Re-ran the same question — citation now correctly reads `§ 7`, and the correct "1/32 of an inch" chunk is present among the 4 retrieved documents (previously absent). See `tests/test_log.txt`.

**Residual risk:** This mitigates but doesn't eliminate the underlying risk — a cross-encoder reranker can still misrank on lexical false-matches for other queries not tested here. For a legal/warranty use case where wrong answers have real consequences, consider adding a post-answer verification step (e.g. checking the cited section number actually appears in the retrieved context) before shipping this to production use.

### 16. `mcp/server.py` — `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`

**Error:**
```
File "backend/mcp/server.py", line 1, in <module>
    from mcp.server.fastmcp import FastMCP
ModuleNotFoundError: No module named 'mcp.server.fastmcp'
```

**Cause:** `requirements.txt` pinned `mcp==1.1.0`, from before the `FastMCP` high-level API existed in the SDK at all — `mcp.server` in that version only has the low-level `Server`/`stdio_server` primitives.

**Fix:** `uv pip install --upgrade mcp` → `mcp==1.28.1`. This also pulled in several unrelated transitive upgrades (`uvicorn` 0.32.0→0.49.0, `python-dotenv` 1.0.1→1.2.2, `python-multipart` 0.0.12→0.0.32, `pydantic-settings` 2.6.0→2.14.2). Verified none of these broke anything: `FastMCP`, `logfire`, and `openai` all still import cleanly, and `uvicorn backend.main:app` still boots with `/health` returning `200 OK`. Updated `requirements.txt` pins to match (`>=` lower bounds, consistent with the rest of the file's approach after bug #10's lesson about avoiding blind exact-version staleness).

### 17. Ingest endpoints never persisted extracted data to SQLite

**Symptom:** `properties` and `maintenance_needs` tables were both empty despite having run `/ingest/photo`, `/ingest/blueprint`, and `/ingest/inspection` successfully multiple times in earlier milestones (Tests 5, 9, 10). MCP tools depending on these tables (`get_property_summary`, `get_maintenance`, `calculate_renovation_roi`) would silently return empty/`None` regardless of how much data had been "ingested."

**Cause:** The three `/ingest/*` endpoints in `backend/main.py` called their respective agent functions and returned the extracted JSON directly to the caller, but never wrote anything into SQLite. The original Milestone 3 plan explicitly included "Store results in SQLite" — it was missed because the `PROGRESS.md` checklist item for that milestone didn't have a separate line item for persistence, only for the agent functions and endpoints existing.

**Secondary issue found while fixing this:** `properties.id` is `INTEGER PRIMARY KEY` in the schema, but every test through Milestone 5 used string property IDs like `"test-prop-1"`. SQLite's dynamic typing wouldn't have errored on this, but it would silently break the `INTEGER PRIMARY KEY` rowid-alias behavior. Changed all three `/ingest/*` endpoint signatures from `property_id: str` to `property_id: int` to match the schema.

**Fix:** Added `ensure_property_exists()`, `save_photo_assessment()`, `save_blueprint_fields()`, and `save_inspection_form()` to `backend/db/queries.py`, wired into the three `/ingest/*` endpoints in `main.py` right after each agent call. `save_blueprint_fields()` uses `COALESCE` so ingesting the Upper Floor blueprint after the Ground Floor one doesn't null out fields the first blueprint already set (e.g. `sqft` from A101 is preserved when A102's `bedrooms`/`bathrooms` are merged in).

**Verified:** Reset the DB, re-ran all three endpoints for one property (`property_id=1`) via real HTTP requests, then queried SQLite directly — confirmed `properties` correctly shows `sqft: 2201` (from Ground Floor) + `bedrooms: 4, bathrooms: 3` (from Upper Floor) merged into one row, plus rows in `property_images`, `material_assessment` (2 rows, sourced `ai_photo` and `inspection`), and `inspection_forms`. See `tests/test_log.txt`.

### 18. Frontend — `/property/{id}` fetch fails with `net::ERR_CONNECTION_RESET` in the browser (worked fine via curl)

**Symptom:** `curl http://127.0.0.1:8000/property/1` succeeded every time, but the same request from the Vue app (browser `fetch`, and even a plain Node `fetch`) using `http://localhost:8000/...` failed with `ERR_CONNECTION_RESET` / `TypeError: Failed to fetch`. Backend access logs showed no corresponding request ever arrived — the failure happened before the request reached the server at all.

**Investigation:** `node -e "require('dns').lookup('localhost', {all:true}, ...)"` showed `localhost` resolves to **`::1` (IPv6) first**, then `127.0.0.1` (IPv4). `uvicorn` only binds `127.0.0.1` by default. Browsers and Node's `fetch` (via `undici`) try addresses in DNS-returned order, so the IPv6 attempt goes first, gets refused/reset (nothing listening on `::1:8000`), and — depending on the client — that shows up as a connection reset rather than falling back cleanly to the working IPv4 address. `curl` on this system apparently orders/handles this differently, which is why it never reproduced the bug.

**Fix:** Changed the frontend API client's base URL from `http://localhost:8000` to `http://127.0.0.1:8000` (`frontend/src/api/client.js`), bypassing DNS resolution order entirely.

**Verified:** Re-ran the Playwright screenshot check — zero console errors, `/property/1` data loads and renders correctly.

### 19. Frontend — `PropertyCard`/`RenovationTable` content invisible despite correct DOM

**Symptom:** Screenshot showed the property card's hero image and thumbnails, then jumped straight to the "Renovation Priorities" panel — no title, price, address, or bed/bath/sqft badges visible in between, even though `/property/1` was returning correct data.

**Investigation:** Queried the live DOM directly (`page.locator('.property-card').innerHTML()`) — the title/price/badges markup **was** present with correct values (`"Property #1"`, `"4 Bed"`, etc.). So this wasn't a data or template bug. Measured the element: `clientHeight: 186` vs `scrollHeight: 399` — the card was being rendered at less than half its content height, with the excess clipped by `overflow: hidden` (set intentionally for rounded corners).

**Cause:** `.property-card` and `.reno-table-panel` are children of `.column` (`display: flex; flex-direction: column`) in `App.vue`. Flex items default to `flex-shrink: 1` and `min-height: auto`, so when the column's available height was tight, the browser shrank these cards below their natural content height instead of letting the column scroll (`.column` already had `overflow-y: auto` for exactly this case, but shrinking happened first).

**Fix:** Added `flex-shrink: 0` to `.property-card` (`PropertyCard.vue`) and `.reno-table-panel` (`RenovationTable.vue`), so they keep their natural content height and the column scrolls instead of squeezing them.

**Verified:** Re-screenshotted — full card content (title, price, address, badges, builder/year, status pin) now renders correctly in both light and dark themes.

## Open

_13. `pii.py` phone-number recognizer can misflag numeric cost ranges (e.g. "4000-9000") as PHONE_NUMBER when no context words are present — accepted trade-off, not fixed (see #13 above)._

_15b. RAG answer grounding is improved but not guaranteed — no automated check yet confirms a generated citation's section number actually appears in the chunks that were retrieved for that answer (see #15 residual risk)._

_17b. `save_inspection_form()` doesn't extract `inspector_name_token`/`inspection_date`/`total_reno_cost` — the current inspection_parser.py prompt only pulls condition/checkbox fields, not the inspector-identity fields or a parsed cost total. `total_reno_cost` is left null; the full per-category cost breakdown is still available in `parsed_fields` JSON._

_20. `rag_agent`'s final yes/no conclusion is not stable across identical runs of the same question — re-asking "Is a 1/8 inch crack in the master bath drywall covered under warranty?" during frontend testing produced "No, not covered" versus the earlier Milestone 5 test's "would be covered," both citing the same correct § 7 clause. The retrieved source text and citation are grounded correctly; only the model's final interpretation of whether exceeding a performance standard implies warranty coverage varies. Not fixed — flagged as a real consistency limitation for a legal/warranty use case, on top of the grounding risk already noted in #15._
