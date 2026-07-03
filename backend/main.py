from dotenv import load_dotenv

# Load .env before any module-level code (e.g. OpenAI() client init in
# ingestion agents) that reads API keys from the environment at import time.
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from .observability.logfire_config import init_logfire
from .ingestion.image_agent import analyze_property_image
from .ingestion.blueprint_agent import process_blueprint
from .ingestion.inspection_parser import parse_inspection_form
from .db.queries import (save_photo_assessment, save_blueprint_fields,
                         save_inspection_form, get_property, get_renovation_breakdown,
                         get_contractors_by_category)
from .rag.graph import rag_agent
import os, uuid, shutil, logfire

init_logfire()
app = FastAPI(title="Property Intelligence API")
logfire.instrument_fastapi(app)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.environ.get("DATABASE_PATH", "./property_intel.db")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ingest/photo")
async def ingest_photo(property_id: int = Form(...), file: UploadFile = File(...)):
    path = f"/tmp/{file.filename}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    result = analyze_property_image(path, str(property_id), str(uuid.uuid4()), DB_PATH)
    save_photo_assessment(property_id, path, result)
    return {"status": "ok", "assessment": result}


@app.post("/ingest/blueprint")
async def ingest_blueprint(property_id: int = Form(...), file: UploadFile = File(...)):
    path = f"/tmp/{file.filename}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    result = process_blueprint(path, str(property_id), str(uuid.uuid4()), DB_PATH)
    save_blueprint_fields(property_id, result)
    return {"status": "ok", "fields": result}


@app.post("/ingest/inspection")
async def ingest_inspection(property_id: int = Form(...), file: UploadFile = File(...)):
    path = f"/tmp/{file.filename}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    result = parse_inspection_form(path, str(property_id), str(uuid.uuid4()), DB_PATH)
    save_inspection_form(property_id, result)
    return {"status": "ok", "fields": result}


@app.get("/property/{property_id}")
async def get_property_detail(property_id: int):
    """Combined view for the frontend's PropertyCard + RenovationTable:
    the property's core fields plus the renovation cost/priority/ROI
    breakdown parsed from its most recent inspection form.
    """
    prop = get_property(property_id)
    renovations = get_renovation_breakdown(property_id)
    return {"property": prop, "renovations": renovations}


@app.get("/contractors")
async def list_contractors(category: str):
    return {"contractors": get_contractors_by_category(category)}


@app.post("/chat")
async def chat(property_id: int = Form(...), message: str = Form(...)):
    # Routes the question to the RAG agent (warranty doc). Other question
    # types (valuation, contractors) are exposed as MCP tools for an
    # assistant to call directly rather than routed through here.
    result = rag_agent.invoke({
        "question": message, "property_id": str(property_id), "doc_type": "warranty",
        "documents": [], "is_relevant": False, "answer": "",
        "citations": [], "iterations": 0})
    return {"answer": result["answer"], "citations": result["citations"]}
