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

## Open

_13. `pii.py` phone-number recognizer can misflag numeric cost ranges (e.g. "4000-9000") as PHONE_NUMBER when no context words are present — accepted trade-off, not fixed (see #13 above)._
