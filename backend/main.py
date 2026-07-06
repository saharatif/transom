from dotenv import load_dotenv

# Load .env before any module-level code (e.g. OpenAI() client init in
# ingestion agents) that reads API keys from the environment at import time.
load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from .observability.logfire_config import init_logfire
from .ingestion.image_agent import analyze_property_image
from .ingestion.preprocess import safe_output_path
from .ingestion.blueprint_agent import process_blueprint
from .ingestion.inspection_parser import parse_inspection_form
from .db.queries import (save_photo_assessment, save_blueprint_fields,
                         save_inspection_form, get_property, get_renovation_breakdown,
                         get_contractors_by_category, reset_property_data,
                         get_property_images, get_image_record)
from .db.setup_db import setup_db
from .rag.graph import rag_agent
import os, shutil, sqlite3, tempfile, uuid, logfire

init_logfire()
app = FastAPI(title="Property Intelligence API")
logfire.instrument_fastapi(app)

# Vite dev server origins only — this API fronts local ingestion pipelines
# with real API keys behind it, so it shouldn't answer arbitrary origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.environ.get("DATABASE_PATH", "./property_intel.db")

# Where uploaded property photos (their blurred _safe copies) are kept so
# the dashboard can display them. The temp spool directory won't do — the
# OS reaps it, and nothing serves it over HTTP.
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", "./uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


def _ensure_db():
    """Create the schema on first boot (fresh deployments have no DB
    file) — setup_db.py's manual run stays the local-dev path."""
    conn = sqlite3.connect(DB_PATH)
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='properties'"
        ).fetchone()
    finally:
        conn.close()
    if not exists:
        setup_db()


_ensure_db()

# What each ingestion pipeline can actually process: photos go to OpenCV +
# GPT-4o Vision (images only), blueprints to Mistral OCR (PDF or image),
# inspection forms to PyMuPDF page rendering (PDF only).
ALLOWED_EXTENSIONS = {
    "photo": {".jpg", ".jpeg", ".png", ".webp"},
    "blueprint": {".pdf", ".jpg", ".jpeg", ".png", ".webp"},
    "inspection": {".pdf"},
}


def _spool_upload(file: UploadFile, doc_type: str) -> str:
    """Write the upload to a unique temp path and return it.

    The filename that arrives in multipart form data is client-controlled —
    writing to /tmp/{file.filename} directly (the previous behavior) let a
    crafted name escape the directory, and two uploads with the same name
    silently overwrote each other. A uuid-based name with only the
    (validated) extension kept from the original avoids both.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    allowed = ALLOWED_EXTENSIONS[doc_type]
    if ext not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type {ext or '(none)'} for {doc_type}. "
                   f"Allowed: {', '.join(sorted(allowed))}")
    path = os.path.join(tempfile.gettempdir(), f"transom_{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return path


def _run_ingestion(doc_type: str, property_id: int, file: UploadFile,
                   agent, save):
    """Shared spool -> agent -> persist -> cleanup flow for all three
    ingest endpoints. Agent failures (LLM/OCR API errors, unparseable
    model output) surface as a 502 with the reason, not a bare 500.

    `save` receives (property_id, result, spooled_path) — the photo
    pipeline needs the path to persist its blurred _safe sibling as the
    stored image_path; the others ignore it.
    """
    path = _spool_upload(file, doc_type)
    try:
        result = agent(path, str(property_id), str(uuid.uuid4()), DB_PATH)
    except HTTPException:
        raise
    except ValueError as e:
        # parse_llm_json / preprocess raise ValueError with a clear message.
        raise HTTPException(status_code=502, detail=f"{doc_type} ingestion failed: {e}")
    except Exception as e:
        logfire.error("ingestion_failed", doc_type=doc_type, error=str(e))
        raise HTTPException(
            status_code=502,
            detail=f"{doc_type} ingestion failed: {type(e).__name__}: {e}")
    finally:
        # The temp copy has served its purpose either way. The photo
        # pipeline's blurred _safe sibling is intentionally kept — its path
        # is persisted in property_images.image_path.
        try:
            os.remove(path)
        except OSError:
            pass
    # A save callback may return an identifier for what it persisted
    # (the photo one returns its property_images row id); pass it through.
    return result, save(property_id, result, path)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Ingest endpoints are plain `def`, not `async def`: each one runs
# multi-second synchronous OCR/Vision/redaction work, which would block
# the whole event loop inside a coroutine. FastAPI runs sync endpoints in
# its threadpool, so other requests (health checks, property fetches)
# stay responsive during an ingestion.

def _persist_photo(property_id: int, assessment: dict, spooled_path: str):
    """Move the blurred _safe copy (written by the preprocessing step next
    to the spooled upload, which _run_ingestion deletes) into UPLOADS_DIR
    so it survives temp cleanup and can be served back to the dashboard,
    then record that final path.
    """
    safe_path = safe_output_path(spooled_path)
    final_path = os.path.join(UPLOADS_DIR, os.path.basename(safe_path))
    shutil.move(safe_path, final_path)
    return save_photo_assessment(property_id, final_path, assessment)


@app.post("/ingest/photo")
def ingest_photo(property_id: int = Form(..., gt=0), file: UploadFile = File(...)):
    result, image_id = _run_ingestion("photo", property_id, file,
                                      analyze_property_image, _persist_photo)
    # image_id lets the frontend scope its photo tiles to the uploads
    # made in the current session.
    return {"status": "ok", "assessment": result, "image_id": image_id}


@app.post("/ingest/blueprint")
def ingest_blueprint(property_id: int = Form(..., gt=0), file: UploadFile = File(...)):
    result, _ = _run_ingestion(
        "blueprint", property_id, file, process_blueprint,
        lambda pid, res, _path: save_blueprint_fields(pid, res))
    return {"status": "ok", "fields": result}


@app.post("/ingest/inspection")
def ingest_inspection(property_id: int = Form(..., gt=0), file: UploadFile = File(...)):
    result, _ = _run_ingestion(
        "inspection", property_id, file, parse_inspection_form,
        lambda pid, res, _path: save_inspection_form(pid, res))
    return {"status": "ok", "fields": result}


@app.get("/property/{property_id}")
def get_property_detail(property_id: int):
    """Combined view for the frontend's PropertyCard + RenovationTable:
    the property's core fields plus the renovation cost/priority/ROI
    breakdown parsed from its most recent inspection form.
    """
    prop = get_property(property_id)
    if prop is None:
        raise HTTPException(status_code=404,
                            detail=f"Property {property_id} not found")
    renovations = get_renovation_breakdown(property_id)
    # Only photos whose file still exists on disk — rows from before the
    # uploads/ directory existed point at reaped temp files.
    images = [{"id": img["id"], "url": f"/images/{img['id']}"}
              for img in get_property_images(property_id)
              if os.path.exists(img["image_path"])]
    return {"property": prop, "renovations": renovations, "images": images}


@app.get("/images/{image_id}")
def serve_image(image_id: int):
    """Serve an uploaded property photo (its blurred _safe copy) by its
    property_images row id."""
    record = get_image_record(image_id)
    if record is None or not os.path.exists(record["image_path"]):
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found")
    return FileResponse(record["image_path"])


@app.get("/contractors")
def list_contractors(category: str):
    return {"contractors": get_contractors_by_category(category)}


@app.post("/reset")
def reset_data():
    """Clear all ingested property data for a fresh start. Keeps the
    seeded contractor list and the Pinecone warranty index (see
    reset_property_data's docstring). The frontend gates this behind a
    two-step confirm in Settings.
    """
    deleted = reset_property_data()
    logfire.info("database_reset", deleted=deleted)
    return {"status": "ok", "deleted": deleted}


@app.post("/chat")
def chat(property_id: int = Form(..., gt=0), message: str = Form(...)):
    # Routes the question to the RAG agent (warranty doc). Other question
    # types (valuation, contractors) are exposed as MCP tools for an
    # assistant to call directly rather than routed through here.
    message = message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message must not be empty")
    try:
        result = rag_agent.invoke({
            "question": message, "retrieval_query": "",
            "property_id": str(property_id), "doc_type": "warranty",
            "documents": [], "is_relevant": False, "answer": "",
            "citations": [], "iterations": 0})
    except Exception as e:
        logfire.error("chat_failed", error=str(e))
        raise HTTPException(status_code=502,
                            detail=f"Warranty agent failed: {type(e).__name__}: {e}")
    return {"answer": result["answer"], "citations": result["citations"]}


# Serve the built frontend (frontend/dist, created by `npm run build`)
# from this same server — one origin, so deployments need no CORS setup
# and no hardcoded API address in the frontend. Mounted last so every
# API route above takes precedence. In dev this directory usually
# doesn't exist and the Vite dev server (:5173) is used instead.
_FRONTEND_DIST = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.isdir(_FRONTEND_DIST):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
