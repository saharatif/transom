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

### 13. (Originally: known limitation, not fixed — now fixed, see #26) `renovation_cost_estimate` — cost ranges occasionally misredacted as PHONE_NUMBER

**Symptom:** In the Vision-extracted `renovation_cost_estimate` string, two entries were corrupted: `"Flooring refinish: [PHONE_NUMBER_XXXXXX] USD"` instead of `"4000-9000 USD"`. Presidio's phone-number recognizer pattern-matched the digit-hyphen-digit shape (`"4000-9000"`, `"3000-7000"`) as a phone number.

**Investigated fix (rejected at the time):** Tried raising `analyzer.analyze()`'s `score_threshold` to filter low-confidence matches. Found both the false positive and a *real* phone number with no nearby context words (e.g. no "phone"/"call"/"tel" nearby) score identically at `0.4` — Presidio only boosts phone-number confidence when context clues are present. A threshold high enough to drop the false positive would also silently stop redacting real, contextless phone numbers elsewhere in the system — a worse failure mode (missed PII) than this one (corrupted cost data). Left `pii.py` unchanged at the time.

**Status: fixed.** See #26 — a currency-context filter (checking for "USD"/"$"/"dollars" immediately after a PHONE_NUMBER match) turned out to be a much better signal than confidence score, and doesn't carry the same risk of suppressing real phone number detection.

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

### 20. `rag_agent`'s final yes/no conclusion was not stable across identical runs of the same question

**Symptom:** Re-asking "Is a 1/8 inch crack in the master bath drywall covered under warranty?" during frontend testing (Test 20) produced "No, not covered," while an earlier Milestone 5 test of the identical question concluded "would be covered" — both runs cited the same correct `§ 7` clause and retrieved the same correct source text. Only the model's final interpretation of whether exceeding a performance-standard threshold implies warranty coverage varied.

**Cause:** `answer_node` asked the LLM to do two things in one uninstructed step: (1) the numeric comparison ("does 1/8 inch exceed 1/32 inch?") and (2) the coverage judgment ("does exceeding it mean it's covered?"). Even at `temperature=0`, GPT-4o isn't perfectly deterministic (a known characteristic of the API — floating-point non-associativity in batched inference), and with no explicit rule connecting "exceeds threshold" to "is covered," the model's interpretation of that connection varied run to run.

**Fix — two parts:**
1. **`backend/rag/measurement.py`** (new file): `extract_inch_measurements()` parses fraction-of-an-inch and decimal-inch measurements (e.g. "1/8 inch" → `0.125`) via regex — the Texas warranty doc's performance standards are almost entirely fraction-of-inch tolerances (drywall cracks, stucco cracks, crowning, bows/depressions, etc.), so this narrow pattern covers what actually matters for this document. `compare_measurement_to_sources()` extracts exactly one measurement from the question and a single, unambiguous threshold from the retrieved source text, and does the `>` comparison **in Python**, deterministically. Returns `None` (falls back to the model's own judgment, unchanged from before) if the question has no single clear measurement, the sources have no threshold, or multiple sources state conflicting thresholds — this only activates for the narrow, well-defined case, not general questions.
2. **`backend/rag/graph.py`**'s `answer_node`: when a comparison is available, injects it as a `COMPUTED FACT (pre-calculated ... treat as ground truth)` line into the prompt, plus an explicit two-step reasoning rule: (1) state the computed comparison result without recomputing it, (2) apply a fixed coverage rule — exceeding a stated threshold is a covered defect per the warranty's general repair obligation, unless the sources state an explicit exclusion or the warranty period has lapsed. This removes the ambiguous, freely-interpreted connection between "exceeds threshold" and "is covered" that was previously left entirely to the model.

**Verified:**
- Same question run 5 times: all 5 runs that successfully retrieved the threshold clause concluded "covered/defect" consistently (previously flip-flopped) — see `tests/test_log.txt` Test 21.
- Negative case tested (`1/64 inch`, which is *below* the `1/32 inch` threshold): correctly concluded "not covered" — confirms the fix isn't just biased toward always saying "covered," it's actually applying the comparison correctly in both directions.
- One of the 5 runs still returned "not covered" with zero citations on a *different* attempt (not part of the 5-run consistency batch) — traced to a **retrieval** miss (the threshold chunk wasn't retrieved at all that run), not a reasoning failure. This is the pre-existing, separate, still-open risk noted in #15 (reranker can miss the right chunk); the fix in this entry only addresses the *reasoning* step, given the correct source was actually retrieved.

### 21. `blueprint_agent.py` — bedroom/bathroom count flipped between identical uploads (4 bed/3 bath → 2 bed/1 bath)

**Symptom:** Uploading `Blueprint_A102_Upper_Floor.png` through the live frontend changed `properties.bedrooms`/`bathrooms` from the previously-correct `4`/`3` down to `2`/`1`, visibly breaking the PropertyCard's badges.

**Investigation — first theory (wrong):** `blueprint_agent.py`'s Mistral OCR call hardcoded `document_url: "data:application/pdf;base64,..."` regardless of the actual uploaded file type, so a `.png` upload was mislabeled as a PDF. This looked like the obvious cause and is a real bug on its own (fixed regardless — see below), but reproducing the OCR call with the corrected `image/png` mime type still returned `bedrooms: 2, bathrooms: 1`. Diffing the raw OCR markdown output between the `.pdf` and `.png` versions of the same sheet showed **identical text** in both cases: `"BEDROOMS 3 & 4 + BATH 3"`. So mislabeling the mime type was not actually the cause of this particular discrepancy (it's still a real, separate correctness issue and was fixed).

**Actual cause:** `"BEDROOMS 3 & 4 + BATH 3"` is a genuinely ambiguous label — it can be read as "this sheet shows bedroom #3 and #4 (of a larger numbered sequence, implying ≥4 total) plus bathroom #3" or as "there are 2 bedrooms and 1 bathroom shown here." GPT-4o's extraction step interpreted this differently across separate runs on the exact same input text — same class of run-to-run interpretation instability as #20, but for room-numbering instead of measurement thresholds.

**Fix — two parts:**
1. `blueprint_agent.py`: use `mimetypes.guess_type()` to set the correct mime type in the OCR `document_url` data URI instead of always assuming `application/pdf`. Real, independent bug fix — doesn't explain this specific discrepancy, but was wrong regardless and worth fixing.
2. `blueprint_agent.py`'s extraction prompt: added explicit instruction that ordinal-numbered room labels (e.g. "BEDROOMS 3 & 4") indicate room numbers in the whole property's numbering sequence, not a literal count of items on that one sheet — extract the *highest* room number mentioned as the total count in that case, falling back to literal counting only when no such numbering convention is present.

**Verified:** Re-ran `process_blueprint()` against the same PNG 3 times after the prompt fix — all 3 runs consistently returned `bedrooms: 4, bathrooms: 3`. Re-ingested through the live API and confirmed the frontend PropertyCard shows the correct badges again. See `tests/test_log.txt` Test 22.

### 22. `inspection_parser.py` — `renovation_cost_estimate` returned a third, different JSON shape, breaking the RenovationTable

**Symptom:** Re-uploading the same filled inspection form through the live frontend produced a RenovationTable with 7 rows but every cell blank (`Category` empty, `Priority` defaulting to "Low", `Est. Cost`/`ROI`/`Contractor` all "—"), even though `/property/1` had previously rendered this table correctly.

**Cause:** The extraction prompt left `renovation_cost_estimate`'s JSON shape completely open-ended. Across different runs it had already been observed in two different shapes (a list of `{item, priority, est_cost, roi}` objects — Test 10; and a dict keyed by category name with `{Priority, "Est. cost ($)", "ROI (%)"}` sub-objects — Test 17). This run produced a **third** shape: a list of single-key dicts, `[{"Roof replacement": "8000-10000 USD"}, ...]`, with no priority or ROI captured at all. `get_renovation_breakdown()`'s normalizer only handled the first two shapes, so every field lookup on the third shape returned `None`.

**Fix:**
1. `inspection_parser.py`: rewrote the `renovation_cost_estimate` prompt instructions to specify **one exact, fixed JSON schema** — a list of `{category, priority, cost, roi}` objects, with an explicit example and per-field description — rather than leaving the structure to the model's discretion.
2. `backend/db/queries.py`'s `get_renovation_breakdown()`: added a third fallback branch for the single-key-dict shape, so already-ingested rows from before this fix still render instead of going blank, while the primary path now expects the new fixed schema directly.

**Verified:** Re-ran `parse_inspection_form()` 3 times after the prompt fix — all 3 runs returned the exact same fixed shape (`category`/`priority`/`cost`/`roi` keys) consistently. Re-ingested through the live API and confirmed the frontend RenovationTable renders all 7 (well, 8 — a null "Other" row is now included since the form has that row too) categories with priority chips, costs, ROI, and looked-up contractors again. See `tests/test_log.txt` Test 22.

### 23. PropertyCard always showed "Value pending" — `properties.estimated_value` was never computed by anything

**Symptom:** User asked why the dashboard always showed "Value pending" instead of a real price, even for a property with `sqft`, `year_built`, `bedrooms`, and `bathrooms` all populated.

**Cause:** The valuation module (`backend/valuation/calculator.py`, built and unit-tested in Milestone 4) was only ever wired into the MCP tools (`estimate_property_value`, `calculate_renovation_roi`) — nothing in the ingestion pipeline called it or wrote a result back into `properties.estimated_value`/`price_per_sqft`. Those columns stayed `NULL` forever regardless of how much data had been ingested.

**Fix:** Added `_maybe_update_estimated_value()` to `backend/db/queries.py`: after either `save_blueprint_fields()` or `save_inspection_form()` runs, it checks whether the property now has both `sqft` and `year_built`, and if so computes `estimated_value` via the same `calculate_base_value()` used by the MCP tools (using the `fetch_local_ppsf()` stub — same $180/sqft illustrative default documented in that function, not a real market lookup) and persists it. Called from both save functions since either one could be the one that completes the pair (blueprint usually supplies `sqft`, inspection form usually supplies `year_built`).

**Verified:** Ran against property #1 (`sqft=2201, year_built=2006`) — `estimated_value` correctly computed as `$316,944` (same figure as the earlier direct MCP tool test), confirmed live in the dashboard (PropertyCard now shows "$316,944" instead of "Value pending").

**Scope note:** Like the MCP tools, this is still using the `fetch_local_ppsf()` stub — a real integration would need actual local comp data per the source PDF's own explicit warning against using a statewide average.

### 24. New SVG logo — dark variant rendered as a broken image (`naturalWidth: 0`)

**Symptom:** After recreating the `design/` PNG logo as light/dark SVG variants and wiring a theme-based swap into `App.vue`, the light variant rendered correctly but the dark variant showed a broken-image icon. `img.naturalWidth` evaluated to `0` in the browser despite the file serving `200 OK` with valid-looking SVG content via `curl`.

**Cause:** The dark SVG's descriptive comment referenced CSS custom property names directly: `<!-- ... --color-primary (#00CFFF) ... --color-text-main (#E0E0E0) ... -->`. XML/SVG comments cannot contain a literal `--` anywhere except at the comment's opening/closing delimiters — `--color-primary` starts with `--`, which is invalid. `curl` doesn't parse/validate XML, so the raw bytes looked fine there; the browser's XML parser (invoked when an SVG is loaded as a standalone document via `<img src>`) treated the malformed comment as a fatal parse error and rendered nothing. The light variant's comment happened not to contain a `--` sequence, so it worked by accident.

**Secondary issue found while fixing this:** the theme-swap mechanism itself was also broken independently — see below.

**Fix:** Reworded the dark SVG's comment to avoid any `--` sequence (described the CSS token purpose in prose instead of naming the literal `--color-*` custom property).

**Verified:** `img.naturalWidth` now evaluates to `255` (a real decoded image) in both themes; screenshots confirm the dark variant renders the icon in the app's dark-mode accent color (`#00CFFF`) with a legible light wordmark.

### 25. Theme-based logo swap didn't work — Vue scoped CSS `:global()` selector silently dropped

**Symptom:** Independent of bug #24's XML issue, the CSS meant to show/hide the light-vs-dark `<img>` based on `[data-theme]` never applied at all — inspecting the live page after toggling dark mode showed `.logo-light` still `display: block` and `.logo-dark` still `display: none`, i.e. no swap happened.

**Cause:** The CSS was written as `:global([data-theme='dark']) .logo-light { display: none; }` inside a Vue SFC `<style scoped>` block, intending "when `<html data-theme=dark>`, hide the light logo." Inspecting the actual compiled stylesheet in the browser showed this rule (and its `.logo-dark` counterpart) were missing entirely — only the unconditional `.logo-dark[data-v-xxx] { display: none }` default survived compilation. Vite's Vue SFC compiler doesn't reliably support `:global(selector) .scopedClass` as a descendant combinator in this position; it silently dropped the rule instead of erroring.

**Fix:** Replaced the CSS-only approach with a small piece of reactive state in `App.vue`: a `MutationObserver` watches `<html>`'s `data-theme` attribute (which `ThemeToggle.vue` sets directly, with no prop/emit connection to the parent) and updates an `isDarkMode` ref, which then drives a `v-if`/`v-else` between the two `<img>` tags — plain Vue reactivity instead of relying on scoped-CSS global-selector edge cases.

**Verified:** Same test as #24 — `naturalWidth` and screenshots confirm the correct variant now renders in each theme, and toggling between them live in the browser swaps the image immediately.

### 26. `pii.py` — fixed the PHONE_NUMBER false positive on currency ranges (#13) via context, not confidence

**Approach (suggested by user, based on observing the actual data):** a real phone number is essentially never directly followed by "USD"/"$"/"dollars." Rather than trying to distinguish false positives by confidence score (rejected in #13 — both cases scored identically), check the text immediately after each `PHONE_NUMBER` match for a currency marker, and skip redacting that specific match if one is found.

**Fix:** Added `_looks_like_currency()` to `backend/redaction/pii.py` — a small regex checking the ~12 characters after a match for `USD`/`$`/`dollars` (case-insensitive). `redact_and_tokenize()` now filters `PHONE_NUMBER` results through this check before building the token map, so currency-adjacent digit-hyphen-digit spans are left alone while everything else is unaffected. This only touches `PHONE_NUMBER` matches with that specific adjacent context — it doesn't change confidence scoring or any other entity type, so it can't reintroduce the risk identified in #13 (suppressing real, contextless phone number redaction elsewhere).

**Verified:**
- `"4000-9000 USD"` / `"3000-7000 USD"` → no longer redacted (unit test + full `parse_inspection_form()` re-run against the real inspection form — all 7 renovation cost ranges came back clean).
- `"214-555-0199"` with no currency context → still correctly redacted (confirms the filter is specific to the currency-adjacent case, not a blanket exemption).
- Confirmed live: re-ingested through the running API, `/property/1`'s renovation breakdown now shows real dollar amounts instead of `[PHONE_NUMBER_...]` placeholders.

### 27. `blueprint_agent.py` — extraction returned `0` instead of `null` for bedrooms/bathrooms on a sheet with no room info, clobbering good data

**Symptom:** Re-ingesting the Ground Floor blueprint (which has no bedroom/bathroom info — see #21) after the room-numbering prompt fix caused `properties.bedrooms`/`bathrooms` to drop from the correct `4`/`3` (set earlier by the Upper Floor sheet) down to `0`/`0`.

**Cause:** The room-numbering fix from #21 added instructions about *counting* rooms, and GPT-4o apparently started interpreting "no bedroom info on this sheet" as "0 bedrooms" rather than "unknown/not applicable" for some runs. Since `0` is not `NULL`, `save_blueprint_fields()`'s `COALESCE(?, existing)` treated it as real data and overwrote the correct `4`/`3` with `0`/`0`.

**Fix — two parts, defense in depth (given this exact field has now caused two separate incidents — #21 and this one):**
1. `blueprint_agent.py`: added an explicit instruction that a sheet with no bedroom/bathroom/sqft info must return `null` for those fields, not `0` — a partial sheet isn't "a home with zero bedrooms."
2. `backend/db/queries.py`'s `save_blueprint_fields()`: changed `COALESCE(?, existing)` to `COALESCE(NULLIF(?, 0), existing)` for `sqft`/`bedrooms`/`bathrooms`, so even if the model returns `0` again in the future, the persistence layer won't let it clobber a real existing count. Not relying on the prompt alone this time.

**Verified:** Manually repaired the corrupted `bedrooms`/`bathrooms` values in the live DB, restarted the backend to load both fixes, then re-ingested the Ground Floor blueprint through the real API — correctly returned `bedrooms: null, bathrooms: null` this time, and the existing `4`/`3` from the Upper Floor sheet stayed intact. Confirmed live in the dashboard.

### 28. `pii.py` — all matches of one entity type collapsed into a single token, corrupting de-tokenization (found in robustness review)

**Symptom (latent — found by code review, then reproduced in a unit test):** with two different people in one document ("Inspector John Smith met the owner, Mary Johnson"), both names were redacted to the *same* token, and `de_tokenize()` restored both to whichever name was processed last. Two distinct people silently became one; the "unique token per match" design was broken in practice.

**Cause:** the code generated a unique token per match but handed them to Presidio's anonymizer via `operators[r.entity_type] = OperatorConfig(...)` — a dict keyed by entity *type*, not per match. Each new PERSON match overwrote the previous operator, so the anonymizer replaced every PERSON span with the last-generated token. The token map still contained all tokens, but only one ever appeared in the text (the rest were orphans), and reversal mapped it to only one original value.

**Fix:** dropped `presidio_anonymizer` for the replacement step entirely — the analyzer already reports exact spans, so `redact_and_tokenize()` now splices each match's own token directly into the text (iterating spans from the end backwards so offsets stay valid). Added `_drop_overlaps()` to keep only the highest-scoring match when Presidio reports overlapping spans, since splicing two tokens into overlapping ranges would garble the text.

**Verified:** `tests/unit/test_pii.py` — the two-person round trip now restores both names exactly; all person tokens in the redacted text are unique. Email/phone round trip and the #26 currency filter re-verified in the same suite.

### 29. `preprocess.py` — `str.replace(".", "_safe.")` broke on filenames with extra dots; unreadable images crashed with an opaque OpenCV error

**Symptom (latent):** `blur_faces_and_plates()` built its output path with `image_path.replace(".", "_safe.")`, which replaces *every* dot — `kitchen.v2.jpg` became `kitchen_safe.v2_safe.jpg`, and any dot in a directory name corrupted the path outright. Separately, `cv2.imread()` returns `None` (no exception) for missing/corrupt files, so a bad upload crashed later inside `detectMultiScale` with an unrelated-looking OpenCV assertion.

**Fix:** output path now built with `os.path.splitext` (via a shared `safe_output_path()` helper, also used by `main.py` — see #32); explicit `ValueError` with the filename when `imread` returns `None`; `imwrite`'s return value checked.

### 30. `main.py` — uploads written to `/tmp/{file.filename}`: path traversal + silent overwrite between uploads

**Symptom (latent, security-relevant):** the multipart `filename` field is client-controlled, and it was interpolated directly into `/tmp/{filename}` — a crafted name like `../../some/path` escaped the directory, and two uploads sharing a name overwrote each other mid-processing.

**Fix:** uploads now spool to `tempfile.gettempdir()/transom_{uuid4}{ext}`, keeping only the file *extension* from the client (validated against a per-doc-type allowlist first — photos: jpg/jpeg/png/webp; blueprints: those + pdf; inspection: pdf only, since PyMuPDF page-rendering is the pipeline). Unsupported types get a `415` naming the allowed extensions. Spooled files are deleted after processing. Also in the same hardening pass: ingest/chat endpoints changed from `async def` to `def` so their multi-second synchronous OCR/Vision/RAG work runs in FastAPI's threadpool instead of blocking the event loop; agent failures map to `502` with the actual reason instead of a bare 500 stack; `/property/{id}` returns a proper `404` for unknown IDs; blank chat messages get `422`; CORS narrowed from `*` to the two Vite dev origins.

**Verified:** live curl tests — `.txt` upload → `415` with allowlist in the message; `filename=../../etc/cron.pdf` → spooled safely to a uuid temp path, then failed as a clean 502 ("Failed to open file … as type pdf") with no DB rows written. Endpoint suite in `tests/unit/test_api.py` pins all of these.

### 31. `RenovationTable.vue` — contractor dropdown reset to the first option on every sort/re-render

**Symptom:** picking a contractor in a row's dropdown, then sorting or filtering the table, snapped the selection back to the first option.

**Cause:** a read/write key mismatch — the selected value was *written* under the mapped contractor-category key (`CATEGORY_MAP[...]`, e.g. "Kitchen & Bathroom Updates") but *read back* under the row's own category key (e.g. "kitchen remodel"), so the read never found the stored choice and fell back to `options[0]`.

**Fix:** reads and writes both key by the row's lowercased category via one `rowKey()` helper.

### 32. `main.py` refactor briefly broke photo persistence — caught by the live E2E run, then pinned with endpoint tests

**Symptom:** during this hardening pass, the new shared `_run_ingestion()` helper called every save function as `save(property_id, result)` — but `save_photo_assessment` takes `(property_id, image_path, assessment)`. Photo uploads 500'd (and, because unhandled 500s bypass the CORS middleware's headers, the browser reported it as "could not reach the API" rather than a server error). A second, subtler issue: the spooled upload is now deleted after processing, so persisting *its* path in `property_images.image_path` (the old behavior) would have left a dangling reference.

**Fix:** `_run_ingestion()` passes `(property_id, result, spooled_path)` to a per-endpoint save lambda; the photo endpoint persists `safe_output_path(spooled_path)` — the blurred `_safe` sibling that the preprocessing step writes and keeps — instead of the deleted original.

**Verified:** live upload through the real UI → success toast, and `property_images` row stores the `…_safe.jpeg` path with the assessment fields. `tests/unit/test_api.py::test_photo_ingest_persists_safe_image_path` pins the wiring (with the vision agent mocked, so it runs without API keys).

### 33. RAG agent answered "not covered" for a plainly covered defect — three compounding flaws in the graph

**Symptom:** "Is a 1/8 inch crack in the drywall covered?" — previously verified to answer yes with a § 7 citation — now returned a bare `"not covered"` with no citations, consistently.

**Cause (three layers, found by running the graph node-by-node):**
1. **The relevance grader was deterministically wrong.** `gpt-4o-mini`, asked "Are these docs relevant? YES or NO" over the concatenated excerpts, answered NO every time — even though the § 7 drywall-crack clause was the top retrieval. It appeared to anchor on the first (stucco) excerpt. That sent every request into the rewrite loop.
2. **`rewrite_node` overwrote the user's question.** Each rewrite replaced `state["question"]` itself, so after two loops the answer node answered a twice-mutated paraphrase — and the #20 measurement comparison ran against that mutated text too. Retrieval on the rewritten query also surfaced worse chunks.
3. **The #20 computed fact never fired on real retrievals.** `compare_measurement_to_sources()` required *all* inch values in the combined context to agree, but real retrieved context mixes thresholds from several performance standards (stucco 1/8", ceiling bows 1/2", drywall cracks 1/32", crowning 1/4") — so the deterministic comparison returned `None` and the yes/no conclusion was back to unaided LLM judgment, which flip-flopped (1 of 3 runs concluded "not covered" even *after* fixes 1–2).

**Fix:**
1. `grade_node` now numbers each excerpt (with its section header) and asks *which* excerpts help, answering NONE if none do — forcing per-excerpt consideration. Verified 3/3 correct on the drywall question and 2/2 NONE on an off-topic control before adopting.
2. Added a separate `retrieval_query` state field: rewrites only ever update the search query; `question` stays what the user asked, for both grading and answering.
3. `compare_measurement_to_sources()` now narrows deterministically before requiring agreement: first to sentences mentioning *all* the question's subject nouns (e.g. "crack" + "drywall" → § 7(c) only), then any subject noun, then the whole text — taking the first level that yields exactly one threshold value, else `None` as before.

**Verified:** 5/5 consecutive live `/chat` runs answer "covered" with the computed fact (0.125" > 0.03125") and a `§ 7` citation; the 1/64" variant correctly answers within-tolerance/not covered; the off-topic car question still answers "not covered". Sentence-scoping logic pinned in `tests/unit/test_measurement.py` with the real mixed-threshold text.

### 34. Dashboard displayed the pre-renovation base value mislabeled as if it reflected renovations (never actually "improved")

**Symptom:** User reported the dashboard's price figure ($316,944 for property #1) as "the current improved estimate," asking for it to be tagged as such and for a pre-renovation figure to be shown alongside it.

**Cause:** `properties.estimated_value` — the only valuation figure ever surfaced on the dashboard — was computed by `_maybe_update_estimated_value()` in `backend/db/queries.py` using `calculate_base_value()` alone (Section 1 of the formulas PDF: price/sqft × sqft × age factor). The renovation-adjusted calculation, `calculate_renovation_impact()` (Section 2: applies each renovation's ROI multiplier and sums the uplift), has existed since Milestone 4 and was correctly unit-tested and wired into the MCP `calculate_renovation_roi` tool — but nothing in the ingestion/dashboard path ever called it. So the number shown was always the *pre*-renovation base value; relabeling it "Improved Estimate" as initially requested would have made a true number say something false.

**Fix (built the real feature instead of relabeling):**
1. `backend/valuation/calculator.py`: added `RENOVATION_CATEGORY_ALIASES` (maps the inspection form's free-text categories — "Roof replacement", "HVAC system", etc. — to `ROI_TABLE`'s fixed keys; categories with no PDF-defined multiplier, e.g. "Paint (interior)", are intentionally left unmapped rather than guessed), `parse_cost_estimate()` (turns a handwritten range like "8000-10000 USD" into its midpoint), and `estimate_renovation_uplift()` (feeds a property's actual parsed `renovation_cost_estimate` rows through `calculate_renovation_impact()`, skipping any row with an unmapped category or unparseable cost; returns `None` if nothing was usable).
2. `GET /property/{id}` now returns a `valuation` object: `previous_estimate` (the existing pre-renovation base value) and `improved_estimate` (the real renovation-adjusted figure, or `null` when there's no usable renovation data yet).
3. `PropertyCard.vue`: shows `improved_estimate` as the primary price with an "IMPROVED ESTIMATE" tag and `previous_estimate` as a secondary line *only* when an improved figure actually exists to contrast it with; falls back to the plain base value (no tag) when it doesn't, so the label is never applied to a number that isn't actually renovation-adjusted.

**Verified:** live against property #1's real data — `previous_estimate: $316,944`, `improved_estimate: $384,899` (base + $12,600 uplift from the roof-replacement row's $9,000 midpoint × 1.40 multiplier, plus the other renovation rows), confirmed in the browser with the tag, primary price, and previous-estimate line all rendering correctly. Unit tests cover the cost-range parser, the category mapping (including the unmapped-category skip), and both endpoint cases (with and without usable renovation data) — see `tests/test_log.txt` Test 42.

## Open

_15b. RAG answer grounding is improved but not guaranteed — no automated check yet confirms a generated citation's section number actually appears in the chunks that were retrieved for that answer (see #15 residual risk). This is also why #20's fix can't help on runs where retrieval itself misses the relevant chunk — the reasoning fix only kicks in once the right source is actually in context._

_17b. `save_inspection_form()` doesn't extract `inspector_name_token`/`inspection_date`/`total_reno_cost` — the current inspection_parser.py prompt only pulls condition/checkbox fields, not the inspector-identity fields or a parsed cost total. `total_reno_cost` is left null; the full per-category cost breakdown is still available in `parsed_fields` JSON._

_20b. The measurement-comparison fix (#20, extended in #33) only covers fraction/decimal-of-an-inch comparisons — the one pattern that recurs throughout this specific warranty document. Other numeric comparison types (percentages, year counts, dollar amounts) in other documents would still rely on the LLM's unstructured reasoning and could exhibit the same kind of run-to-run inconsistency. Not generalized further since no other case has been observed in testing yet._
