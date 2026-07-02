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

## Open

_None currently._
