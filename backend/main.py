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
async def ingest_photo(property_id: str = Form(...), file: UploadFile = File(...)):
    path = f"/tmp/{file.filename}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    result = analyze_property_image(path, property_id, str(uuid.uuid4()), DB_PATH)
    return {"status": "ok", "assessment": result}


@app.post("/ingest/blueprint")
async def ingest_blueprint(property_id: str = Form(...), file: UploadFile = File(...)):
    path = f"/tmp/{file.filename}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    result = process_blueprint(path, property_id, str(uuid.uuid4()), DB_PATH)
    return {"status": "ok", "fields": result}


@app.post("/ingest/inspection")
async def ingest_inspection(property_id: str = Form(...), file: UploadFile = File(...)):
    path = f"/tmp/{file.filename}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    result = parse_inspection_form(path, property_id, str(uuid.uuid4()), DB_PATH)
    return {"status": "ok", "fields": result}
