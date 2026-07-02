# Property Intelligence System — Implementation Reference

**A multimodal AI platform for automated property assessment, valuation, and renovation intelligence.**

Built for the RealPage builder submission. Ingests property photos, blueprints, inspection forms, and legal/valuation PDFs; produces structured property intelligence queryable in natural language via an MCP server.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Tech Stack](#2-tech-stack)
3. [The Core Design Principle: Right Tool Per Input](#3-the-core-design-principle-right-tool-per-input)
4. [Repository Structure](#4-repository-structure)
5. [Environment Setup](#5-environment-setup)
6. [Data Layer — SQLite Schema](#6-data-layer--sqlite-schema)
7. [PII Redaction Layer](#7-pii-redaction-layer)
8. [Ingestion Pipelines](#8-ingestion-pipelines)
9. [Valuation Module (Deterministic)](#9-valuation-module-deterministic)
10. [RAG Subsystem (LangChain + LangGraph)](#10-rag-subsystem-langchain--langgraph)
11. [MCP Server](#11-mcp-server)
12. [Observability with Logfire](#12-observability-with-logfire)
13. [Backend API (FastAPI)](#13-backend-api-fastapi)
14. [Frontend (Vue.js)](#14-frontend-vuejs)
15. [End-to-End Flow](#15-end-to-end-flow)
16. [Build Order / Milestones](#16-build-order--milestones)
17. [Demo Script](#17-demo-script)

---

## 1. System Overview

The Property Intelligence System takes messy, multimodal property data and turns it into a structured, queryable knowledge base. A property manager or underwriter uploads:

- **Photos** of the property (interior/exterior)
- **Blueprints** (floor plans, PDF or image)
- **Inspection forms** (the standardized checkbox form, filled and scanned)
- **Legal/reference PDFs** (warranty documents, valuation formula references, historical inspection reports)

The system processes each through the appropriate pipeline, stores structured results in SQLite and long-form documents in Pinecone, and exposes everything through an MCP server so an AI assistant (Claude/GPT-4o) can answer natural-language questions with cited, grounded answers.

**Key outputs:**
- Property condition score (1–10)
- Estimated current value + breakdown
- Renovation needs, ranked by priority, with cost and value-uplift estimates
- Recommended contractors per renovation category
- Warranty coverage answers with legal citations

---

## 2. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Vue.js 3 + Composition API | Chat UI, file upload, results dashboard |
| UI components | shadcn-vue / Tailwind | Component library |
| Backend | FastAPI (async) | REST endpoints, orchestration |
| Structured DB | SQLite | Property records, extracted fields, token map |
| Vector DB | Pinecone | Long-document RAG (warranty, reports) |
| RAG framework | LangChain + LangGraph | Retrieval, reranking, multi-step agent |
| Vision / LLM | GPT-4o, GPT-4o-mini | Image analysis, synthesis, answering |
| OCR | Mistral OCR | PDF/blueprint text extraction |
| Image preprocessing | OpenCV | Face/plate blurring before Vision |
| PII redaction | Microsoft Presidio | Detect + tokenize PII pre-LLM |
| Embeddings | OpenAI text-embedding-3-small | Vectorize document chunks |
| Reranking | BAAI/bge-reranker-base (cross-encoder) | Improve retrieval precision |
| Observability | Pydantic Logfire | Trace every AI call, latency, cost, PII events |
| Agent interface | MCP (Model Context Protocol) | Expose tools to AI assistant |

---

## 3. The Core Design Principle: Right Tool Per Input

**Do not use RAG for everything.** The single most important architectural decision in this system is matching each input type to the right processing approach. Applying RAG universally is a common mistake that makes the system slower, more expensive, and more prone to hallucination.

Decision rule for each input: *Do I know the questions people will ask, and do those questions map to specific fields?*

- **Yes** → structured extraction into SQLite → SQL queries
- **No, source is a formula/calculation** → parse once → code constants + MCP tools
- **No, source is long and open-ended** → RAG with Pinecone

| Input type | Nature | Approach | Storage |
|---|---|---|---|
| Property photos | Known fields (condition, materials) | GPT-4o Vision → structured JSON | SQLite |
| Blueprints | Known fields (sqft, rooms, layout) | OCR + LLM → structured fields | SQLite |
| Inspection form | Fixed checkbox fields | OCR + form parser | SQLite |
| Contractor list | Relational data | Direct insert | SQLite |
| Valuation formulas PDF | Deterministic formulas | Parse once → Python constants | Code + MCP tools |
| Warranty document | Long, legal, open-ended queries | RAG + structural chunking | Pinecone |
| Historical inspection reports | Long, open-ended queries | RAG | Pinecone |

**Why this matters for the demo:** you can tell RealPage "Pinecone handles long-form document retrieval, SQLite handles structured property intelligence, and deterministic formulas run as code — the right tool for each job." That reads as production thinking, not a prototype that reaches for RAG reflexively.

---

## 4. Repository Structure

```
property-intelligence/
├── README.md
├── requirements.txt
├── .env.example
├── docker-compose.yml
│
├── backend/
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # Settings, env vars
│   ├── db/
│   │   ├── schema.sql             # SQLite schema
│   │   ├── setup_db.py            # DB initialization
│   │   └── queries.py             # SQL query helpers
│   │
│   ├── redaction/
│   │   └── pii.py                 # Presidio redact + tokenize
│   │
│   ├── ingestion/
│   │   ├── image_agent.py         # Photo → GPT-4o Vision → JSON
│   │   ├── blueprint_agent.py     # Blueprint → OCR + LLM → fields
│   │   ├── inspection_parser.py   # Inspection form → structured fields
│   │   └── preprocess.py          # OpenCV face/plate blur
│   │
│   ├── valuation/
│   │   └── calculator.py          # Deterministic value formulas
│   │
│   ├── rag/
│   │   ├── ingestion.py           # LangChain: parse→redact→chunk→embed
│   │   ├── retrieval.py           # Retriever + reranker
│   │   └── graph.py               # LangGraph multi-step agent
│   │
│   ├── mcp/
│   │   └── server.py              # MCP tool definitions
│   │
│   └── observability/
│       └── logfire_config.py      # Logfire setup
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.vue
│       ├── components/
│       │   ├── ChatPanel.vue
│       │   ├── FileUpload.vue
│       │   ├── PropertyCard.vue
│       │   └── RenovationTable.vue
│       └── api/
│           └── client.js
│
└── docs/
    ├── warranty_template.pdf
    ├── valuation_formulas.pdf
    └── architecture.pdf
```

---

## 5. Environment Setup

### requirements.txt

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
python-multipart==0.0.12
pydantic==2.9.0
pydantic-settings==2.6.0

# LLM / AI
openai==1.54.0
mistralai==1.2.0

# RAG
langchain==0.3.7
langchain-openai==0.2.8
langchain-community==0.3.5
langchain-pinecone==0.2.0
langgraph==0.2.45
pinecone-client==5.0.1

# PII
presidio-analyzer==2.2.355
presidio-anonymizer==2.2.355
spacy==3.7.5

# Image
opencv-python==4.10.0.84
pillow==11.0.0

# Reranking
sentence-transformers==3.3.0

# Observability
logfire==2.6.0

# MCP
mcp==1.1.0
```

### .env.example

```
OPENAI_API_KEY=sk-...
MISTRAL_API_KEY=...
PINECONE_API_KEY=...
PINECONE_INDEX=property-intelligence
LOGFIRE_TOKEN=...
DATABASE_PATH=./property_intel.db
```

### Install

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_lg
python backend/db/setup_db.py
```

---

## 6. Data Layer — SQLite Schema

`backend/db/schema.sql`

```sql
CREATE TABLE properties (
    id                INTEGER PRIMARY KEY,
    address           TEXT,
    city_state_zip    TEXT,
    builder           TEXT,
    year_built        INTEGER,
    sqft              INTEGER,
    lot_sqft          INTEGER,
    bedrooms          INTEGER,
    bathrooms         REAL,
    property_type     TEXT,
    listed_price      REAL,
    price_per_sqft    REAL,
    condition_score   REAL,       -- 1-10, AI assessed
    estimated_value   REAL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE property_images (
    id                INTEGER PRIMARY KEY,
    property_id       INTEGER,
    image_path        TEXT,
    ai_assessment     TEXT,       -- full JSON from Vision
    condition_score   INTEGER,
    issues_detected   TEXT,       -- JSON array
    confidence        TEXT,       -- high/medium/low
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE material_assessment (
    id                INTEGER PRIMARY KEY,
    property_id       INTEGER,
    floor_type        TEXT,
    floor_condition   TEXT,
    floor_score       INTEGER,
    wood_species      TEXT,
    wood_grade        TEXT,
    paint_condition   TEXT,
    source            TEXT,       -- 'ai_photo' | 'inspection' | 'blueprint'
    confidence        TEXT,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE maintenance_needs (
    id                INTEGER PRIMARY KEY,
    property_id       INTEGER,
    issue             TEXT,
    priority          TEXT,       -- urgent | moderate | low
    estimated_cost    REAL,
    value_uplift      REAL,
    roi_percent       REAL,
    category          TEXT,       -- maps to contractor category
    source            TEXT,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE inspection_forms (
    id                INTEGER PRIMARY KEY,
    property_id       INTEGER,
    inspector_name_token TEXT,    -- tokenized PII
    inspection_date   TEXT,
    parsed_fields     TEXT,       -- full JSON of checkbox results
    total_reno_cost   REAL,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE documents (
    id                INTEGER PRIMARY KEY,
    property_id       INTEGER,
    doc_type          TEXT,       -- warranty | valuation_ref | inspection_report
    file_path         TEXT,
    pinecone_namespace TEXT,      -- null if not RAG'd
    key_findings      TEXT,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE renovation_companies (
    id                INTEGER PRIMARY KEY,
    category          TEXT,
    company_name      TEXT,
    website           TEXT,
    location          TEXT,
    phone             TEXT
);

CREATE TABLE pii_token_map (
    id                INTEGER PRIMARY KEY,
    doc_id            TEXT,
    token             TEXT,
    original_value    TEXT,
    entity_type       TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Seed the contractors table with the four known companies:

```sql
INSERT INTO renovation_companies (category, company_name, website, location, phone) VALUES
('Curb Appeal & Exterior Upgrades', 'Power HRG', 'https://www.powerhrg.com/', 'McKinney, TX', '214-306-7611'),
('Kitchen & Bathroom Updates', 'Spruced - Decorating Den', 'https://spruced.decoratingden.com/', 'Dallas, TX', '(214) 516-7677'),
('Flooring & Square Footage Upgrades', 'EFS Flooring and Remodeling', 'https://www.efsflooringandremodeling.com/', 'Irving, TX', '(972) 330-7615'),
('Essential System & Energy Updates', 'Kohler Home Energy', 'https://www.kohlerhomeenergy.rehlko.com/', 'Nationwide', '1-844-731-7989');
```

---

## 7. PII Redaction Layer

**Critical rule: redaction happens at the injection point** — immediately after OCR/Vision extracts text, before that text touches any downstream LLM, chunker, or embedder. The window between extraction and redaction must contain no storage, no logging, no network hop.

`backend/redaction/pii.py`

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
import sqlite3, uuid
import logfire

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

PII_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
                "US_SSN", "CREDIT_CARD", "US_BANK_NUMBER", "LOCATION"]

@logfire.instrument()
def redact_and_tokenize(text: str, doc_id: str, db_path: str) -> str:
    results = analyzer.analyze(text=text, entities=PII_ENTITIES, language="en")

    token_map = {}
    operators = {}
    for r in results:
        token = f"[{r.entity_type}_{uuid.uuid4().hex[:6].upper()}]"
        original = text[r.start:r.end]
        token_map[token] = (original, r.entity_type)
        operators[r.entity_type] = OperatorConfig("replace", {"new_value": token})

    logfire.info("pii_detected", count=len(results),
                 types=[r.entity_type for r in results])

    anonymized = anonymizer.anonymize(
        text=text, analyzer_results=results, operators=operators)

    _store_token_map(doc_id, token_map, db_path)
    return anonymized.text


def _store_token_map(doc_id, token_map, db_path):
    conn = sqlite3.connect(db_path)
    for token, (original, etype) in token_map.items():
        conn.execute(
            "INSERT INTO pii_token_map (doc_id, token, original_value, entity_type) "
            "VALUES (?, ?, ?, ?)", (doc_id, token, original, etype))
    conn.commit()
    conn.close()


@logfire.instrument()
def de_tokenize(text: str, doc_id: str, db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT token, original_value FROM pii_token_map WHERE doc_id = ?",
        (doc_id,)).fetchall()
    conn.close()
    for token, original in rows:
        text = text.replace(token, original)
    return text
```

**Per-input PII handling:**

| Input | External API that sees raw data | Redact after |
|---|---|---|
| Photos | GPT-4o Vision (unavoidable) | Text output from Vision |
| Blueprints | Mistral OCR (unavoidable) | Text output from OCR |
| PDF docs | Mistral OCR (unavoidable) | Text output from OCR — highest PII risk |

For photos, additionally run OpenCV face/plate blur **before** sending to Vision (images can't be pre-redacted by Presidio, which works on text).

---

## 8. Ingestion Pipelines

### 8.1 Image Agent

`backend/ingestion/image_agent.py`

```python
import base64, json
from openai import OpenAI
from .preprocess import blur_faces_and_plates
from ..redaction.pii import redact_and_tokenize
import logfire

client = OpenAI()

@logfire.instrument()
def analyze_property_image(image_path: str, property_id: str, doc_id: str, db_path: str):
    # 1. Preprocess: blur faces / license plates BEFORE Vision
    safe_image_path = blur_faces_and_plates(image_path)

    with open(safe_image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    # 2. Vision analysis
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": """
Analyze this property image. Return ONLY JSON:
{
  "floor_type": "hardwood/tile/vinyl/carpet/laminate/unknown",
  "floor_condition": "excellent/good/fair/worn/poor",
  "wood_species": "oak/pine/walnut/unknown/na",
  "paint_condition": "fresh/good/fair/poor",
  "condition_score": 0-10,
  "visible_issues": ["..."],
  "estimated_age_years": number,
  "confidence": "high/medium/low"
}
"""}
            ]
        }]
    )
    raw = resp.choices[0].message.content.replace("```json", "").replace("```", "")

    # 3. Redact any PII in the text output before storing
    clean = redact_and_tokenize(raw, doc_id, db_path)
    return json.loads(clean)
```

### 8.2 Preprocessing (OpenCV)

`backend/ingestion/preprocess.py`

```python
import cv2

def blur_faces_and_plates(image_path: str) -> str:
    img = cv2.imread(image_path)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(img, 1.1, 4)
    for (x, y, w, h) in faces:
        img[y:y+h, x:x+w] = cv2.GaussianBlur(img[y:y+h, x:x+w], (99, 99), 30)
    out_path = image_path.replace(".", "_safe.")
    cv2.imwrite(out_path, img)
    return out_path
```

### 8.3 Blueprint Agent

`backend/ingestion/blueprint_agent.py`

```python
from mistralai import Mistral
from openai import OpenAI
from ..redaction.pii import redact_and_tokenize
import os, json, logfire

mistral = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
openai_client = OpenAI()

@logfire.instrument()
def process_blueprint(pdf_path: str, property_id: str, doc_id: str, db_path: str):
    # 1. OCR (unavoidable — external API sees raw)
    with open(pdf_path, "rb") as f:
        ocr_resp = mistral.ocr.process(
            model="mistral-ocr-latest",
            document={"type": "document", "document": f.read()})
    raw_text = ocr_resp.text

    # 2. Redact IMMEDIATELY after OCR
    clean_text = redact_and_tokenize(raw_text, doc_id, db_path)

    # 3. Extract structured fields from clean text
    resp = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"""
Extract from this blueprint text. Return ONLY JSON:
{{"sqft": number, "bedrooms": number, "bathrooms": number,
  "rooms": ["..."], "layout_type": "..."}}

TEXT: {clean_text}
"""}]
    )
    raw = resp.choices[0].message.content.replace("```json","").replace("```","")
    return json.loads(raw)
```

### 8.4 Inspection Form Parser

The inspection form has **fixed, known fields** — this is a parser, not RAG.

`backend/ingestion/inspection_parser.py`

```python
from mistralai import Mistral
from openai import OpenAI
from ..redaction.pii import redact_and_tokenize
import os, json, logfire

@logfire.instrument()
def parse_inspection_form(pdf_path: str, property_id: str, doc_id: str, db_path: str):
    mistral = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
    with open(pdf_path, "rb") as f:
        ocr = mistral.ocr.process(model="mistral-ocr-latest",
                                  document={"type":"document","document":f.read()})
    clean_text = redact_and_tokenize(ocr.text, doc_id, db_path)

    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role":"user","content":f"""
Extract the checked options and values from this inspection form.
Return ONLY JSON with keys: floor_type, floor_condition, wood_grade,
paint_condition, roof_condition, hvac_age_years, kitchen_condition,
bathroom_condition, renovation_cost_estimate, overall_condition_score.

FORM TEXT: {clean_text}
"""}]
    )
    raw = resp.choices[0].message.content.replace("```json","").replace("```","")
    return json.loads(raw)
```

---

## 9. Valuation Module (Deterministic)

The valuation formulas PDF is **parsed once into code** — never RAG'd. These are deterministic functions exposed as MCP tools.

`backend/valuation/calculator.py`

```python
# ROI multipliers from the Texas Property Valuation Formulas reference doc
ROI_TABLE = {
    "roof_replacement":     {"multiplier": 1.40, "priority": "urgent",
                             "cost_range": (8000, 14000)},
    "hvac_replacement":     {"multiplier": 1.20, "priority": "urgent",
                             "cost_range": (5500, 10000)},
    "kitchen_remodel":      {"multiplier": 1.50, "priority": "moderate",
                             "cost_range": (9000, 18000)},
    "bathroom_updates":     {"multiplier": 1.25, "priority": "moderate",
                             "cost_range": (5000, 12000)},
    "flooring_refinish":    {"multiplier": 1.42, "priority": "moderate",
                             "cost_range": (4000, 9000)},
    "curb_appeal_exterior": {"multiplier": 1.50, "priority": "low",
                             "cost_range": (3000, 7000)},
}

def calculate_base_value(sqft, year_built, price_per_sqft,
                         depreciation_rate=0.010, current_year=2026):
    """Section 1 — Base value formula."""
    age = current_year - year_built
    age_factor = max(1 - (depreciation_rate * age), 0.60)
    return round(price_per_sqft * sqft * age_factor, 2)


def calculate_renovation_impact(base_value, renovations, local_median_ppsf,
                                 sqft, ceiling_multiplier=1.20):
    """Section 2 — Renovation-adjusted value with neighborhood ceiling."""
    breakdown = []
    total_uplift = 0
    total_cost = 0
    for r in renovations:
        cat = r["category"]
        mult = ROI_TABLE[cat]["multiplier"]
        uplift = r["cost"] * mult
        total_uplift += uplift
        total_cost += r["cost"]
        breakdown.append({
            "category": cat,
            "cost": r["cost"],
            "value_uplift": round(uplift, 2),
            "roi_percent": round(mult * 100, 1),
            "priority": ROI_TABLE[cat]["priority"]
        })

    raw_updated = base_value + total_uplift
    ceiling = local_median_ppsf * sqft * ceiling_multiplier
    updated_value = min(raw_updated, ceiling)

    return {
        "base_value": base_value,
        "total_renovation_cost": total_cost,
        "total_value_uplift": round(total_uplift, 2),
        "updated_value": round(updated_value, 2),
        "net_equity_gain": round(total_uplift - total_cost, 2),
        "ceiling_applied": raw_updated > ceiling,
        "breakdown": breakdown
    }
```

---

## 10. RAG Subsystem (LangChain + LangGraph)

Only for **long, open-ended documents**: warranty, historical inspection reports, legal contracts.

### 10.1 Ingestion

`backend/rag/ingestion.py`

```python
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from ..redaction.pii import redact_and_tokenize
import logfire

@logfire.instrument()
def ingest_document(pdf_path, property_id, doc_id, db_path, doc_type="warranty"):
    loader = PyMuPDFLoader(pdf_path)
    raw_text = "\n\n".join(d.page_content for d in loader.load())

    # Redact PII (builder name/phone/email/address in headers)
    clean_text = redact_and_tokenize(raw_text, doc_id, db_path)

    # Structural chunking — split on section markers first
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800, chunk_overlap=100,
        separators=["\n§ ", "\n(a)", "\n(b)", "\n\n", "\n", " "])
    chunks = splitter.create_documents(
        [clean_text],
        metadatas=[{"doc_id": doc_id, "doc_type": doc_type,
                    "property_id": property_id, "source": pdf_path}])

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    namespace = f"property_{property_id}_{doc_type}"
    PineconeVectorStore.from_documents(
        documents=chunks, embedding=embeddings,
        index_name="property-intelligence", namespace=namespace)

    logfire.info("document_ingested", chunks=len(chunks), namespace=namespace)
    return {"chunks": len(chunks), "namespace": namespace}
```

### 10.2 Retriever + Reranker

`backend/rag/retrieval.py`

```python
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

def build_retriever(property_id, doc_type="warranty"):
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vs = PineconeVectorStore(
        index_name="property-intelligence", embedding=embeddings,
        namespace=f"property_{property_id}_{doc_type}")
    base = vs.as_retriever(search_type="mmr",
                           search_kwargs={"k": 5, "fetch_k": 20, "lambda_mult": 0.5})
    reranker = CrossEncoderReranker(
        model=HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base"),
        top_n=3)
    return ContextualCompressionRetriever(
        base_compressor=reranker, base_retriever=base)
```

### 10.3 LangGraph Agent

`backend/rag/graph.py`

```python
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from .retrieval import build_retriever
import re, logfire

class RAGState(TypedDict):
    question: str
    property_id: str
    doc_type: str
    documents: List[dict]
    is_relevant: bool
    answer: str
    citations: List[str]
    iterations: int

def retrieve_node(state):
    retriever = build_retriever(state["property_id"], state["doc_type"])
    docs = retriever.invoke(state["question"])
    return {**state, "documents":
            [{"content": d.page_content, "metadata": d.metadata} for d in docs]}

def grade_node(state):
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    txt = "\n\n".join(d["content"] for d in state["documents"])
    g = llm.invoke([SystemMessage(content="Are these docs relevant? YES or NO only."),
                    HumanMessage(content=f"Q: {state['question']}\n\n{txt}")])
    return {**state, "is_relevant": "YES" in g.content.upper()}

def rewrite_node(state):
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    r = llm.invoke([SystemMessage(content="Rewrite to improve retrieval."),
                    HumanMessage(content=state["question"])])
    return {**state, "question": r.content, "iterations": state["iterations"]+1}

def answer_node(state):
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    txt = "\n\n".join(f"[{d['metadata'].get('source')} chunk {i}]\n{d['content']}"
                      for i, d in enumerate(state["documents"]))
    r = llm.invoke([
        SystemMessage(content="Answer using ONLY the sources. Cite section "
                              "numbers (Section X). Say 'not covered' if absent."),
        HumanMessage(content=f"Sources:\n{txt}\n\nQ: {state['question']}")])
    cites = re.findall(r'[Ss]ection\s+\d+', r.content)
    return {**state, "answer": r.content, "citations": cites}

def should_rewrite(state):
    if state["is_relevant"] or state["iterations"] >= 2:
        return "answer"
    return "rewrite"

def build_rag_graph():
    g = StateGraph(RAGState)
    g.add_node("retrieve", retrieve_node)
    g.add_node("grade", grade_node)
    g.add_node("rewrite", rewrite_node)
    g.add_node("answer", answer_node)
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", should_rewrite,
                            {"rewrite": "rewrite", "answer": "answer"})
    g.add_edge("rewrite", "retrieve")
    g.add_edge("answer", END)
    return g.compile()

rag_agent = build_rag_graph()
```

The graph flow: `retrieve → grade → (relevant? answer : rewrite → retrieve, max 2 loops) → answer → END`. The grading + rewrite loop catches wrong retrievals before they reach the answer, which matters for legal text where an incorrect answer has consequences.

---

## 11. MCP Server

`backend/mcp/server.py`

```python
from mcp.server.fastmcp import FastMCP
from ..valuation.calculator import (calculate_base_value,
                                     calculate_renovation_impact, ROI_TABLE)
from ..rag.graph import rag_agent
from ..db.queries import (get_property, get_maintenance_needs,
                          get_contractors_by_category, fetch_local_ppsf)
import logfire

mcp = FastMCP("property-intelligence")

@mcp.tool()
@logfire.instrument()
def get_property_summary(property_id: str) -> dict:
    """Return the full structured summary for a property."""
    return get_property(property_id)

@mcp.tool()
@logfire.instrument()
def get_maintenance(property_id: str, priority: str = None) -> dict:
    """Get maintenance needs, optionally filtered by priority."""
    return get_maintenance_needs(property_id, priority)

@mcp.tool()
@logfire.instrument()
def estimate_property_value(sqft: int, year_built: int, zip_code: str) -> dict:
    """Calculate base value using the Texas valuation formula (Section 1)."""
    ppsf = fetch_local_ppsf(zip_code)
    base = calculate_base_value(sqft, year_built, ppsf)
    return {"base_value": base, "price_per_sqft": ppsf}

@mcp.tool()
@logfire.instrument()
def calculate_renovation_roi(property_id: str, renovations: list,
                             zip_code: str) -> dict:
    """Calculate renovation value uplift capped at neighborhood ceiling."""
    prop = get_property(property_id)
    ppsf = fetch_local_ppsf(zip_code)
    base = calculate_base_value(prop["sqft"], prop["year_built"], ppsf)
    return calculate_renovation_impact(base, renovations, ppsf, prop["sqft"])

@mcp.tool()
@logfire.instrument()
def get_contractors(category: str) -> dict:
    """Get recommended contractors for a renovation category."""
    return get_contractors_by_category(category)

@mcp.tool()
@logfire.instrument()
def get_warranty_coverage(property_id: str, question: str) -> dict:
    """Search the warranty document (RAG) for coverage on an issue."""
    result = rag_agent.invoke({
        "question": question, "property_id": property_id,
        "doc_type": "warranty", "documents": [],
        "is_relevant": False, "answer": "", "citations": [], "iterations": 0})
    return {"answer": result["answer"], "citations": result["citations"]}

if __name__ == "__main__":
    mcp.run()
```

---

## 12. Observability with Logfire

`backend/observability/logfire_config.py`

```python
import logfire
import os

def init_logfire():
    logfire.configure(token=os.environ["LOGFIRE_TOKEN"], service_name="property-intel")
    # Auto-instrument FastAPI, OpenAI, and HTTP calls
    logfire.instrument_openai()
    logfire.instrument_pydantic()
```

Every function decorated with `@logfire.instrument()` produces a trace span. Key things surfaced in the dashboard:
- Every AI call (which model, prompt tokens, completion tokens, latency, cost)
- Every PII detection event (count + types redacted per document — via `logfire.info("pii_detected", ...)`)
- Every MCP tool call and its arguments
- RAG graph steps: retrievals, grading results, rewrite loops
- End-to-end latency per property ingestion

In the demo, show the live Logfire dashboard as you upload a property — the traces streaming in are a strong visual proof of production-readiness.

---

## 13. Backend API (FastAPI)

`backend/main.py`

```python
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from .observability.logfire_config import init_logfire
from .ingestion.image_agent import analyze_property_image
from .ingestion.blueprint_agent import process_blueprint
from .ingestion.inspection_parser import parse_inspection_form
from .rag.ingestion import ingest_document
import uuid, shutil, logfire

init_logfire()
app = FastAPI(title="Property Intelligence API")
logfire.instrument_fastapi(app)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

DB_PATH = "./property_intel.db"

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

@app.post("/ingest/document")
async def ingest_doc(property_id: str = Form(...), doc_type: str = Form("warranty"),
                     file: UploadFile = File(...)):
    path = f"/tmp/{file.filename}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    result = ingest_document(path, property_id, str(uuid.uuid4()), DB_PATH, doc_type)
    return {"status": "ok", **result}

@app.post("/chat")
async def chat(property_id: str = Form(...), message: str = Form(...)):
    # Routes to MCP tools / RAG agent based on the question
    from .rag.graph import rag_agent
    result = rag_agent.invoke({
        "question": message, "property_id": property_id, "doc_type": "warranty",
        "documents": [], "is_relevant": False, "answer": "",
        "citations": [], "iterations": 0})
    return {"answer": result["answer"], "citations": result["citations"]}
```

---

## 14. Frontend (Vue.js)

`frontend/src/api/client.js`

```javascript
const API = "http://localhost:8000";

export async function uploadFile(endpoint, propertyId, file) {
  const form = new FormData();
  form.append("property_id", propertyId);
  form.append("file", file);
  const res = await fetch(`${API}/ingest/${endpoint}`, {
    method: "POST", body: form });
  return res.json();
}

export async function sendChat(propertyId, message) {
  const form = new FormData();
  form.append("property_id", propertyId);
  form.append("message", message);
  const res = await fetch(`${API}/chat`, { method: "POST", body: form });
  return res.json();
}
```

`frontend/src/App.vue` (skeleton)

```vue
<script setup>
import { ref } from 'vue'
import FileUpload from './components/FileUpload.vue'
import ChatPanel from './components/ChatPanel.vue'
import PropertyCard from './components/PropertyCard.vue'

const propertyId = ref('142')
const propertyData = ref(null)
</script>

<template>
  <div class="app">
    <h1>Property Intelligence</h1>
    <FileUpload :propertyId="propertyId" @ingested="propertyData = $event" />
    <PropertyCard v-if="propertyData" :data="propertyData" />
    <ChatPanel :propertyId="propertyId" />
  </div>
</template>
```

Components to build:
- `FileUpload.vue` — drag-drop zones for photos, blueprint, inspection form, documents; routes each to its `/ingest/*` endpoint
- `PropertyCard.vue` — renders the structured summary (condition score, value, features)
- `RenovationTable.vue` — the ranked renovation list with cost, uplift, ROI, and contractor per row
- `ChatPanel.vue` — conversational box that calls `/chat` and renders answers with citation chips

---

## 15. End-to-End Flow

```
1. USER uploads photos + blueprint + inspection form + warranty PDF
   via Vue frontend
        │
2. FastAPI receives each file, routes to the correct pipeline:
        │
   ┌────┼─────────────────────────────────────────────────────┐
   │    │                                                       │
 PHOTOS │  BLUEPRINT      INSPECTION FORM       WARRANTY PDF     │
   │    │      │                │                    │          │
 OpenCV │   Mistral OCR     Mistral OCR          PyMuPDF load    │
 blur   │      │                │                    │          │
   │    │   Presidio ◄──── injection-point redaction ───►       │
 GPT-4o │   GPT-4o          GPT-4o parser       structural      │
 Vision │   extract         (fixed fields)      chunking        │
   │    │      │                │                    │          │
 Presidio      │                │              OpenAI embed     │
   │    │      │                │                    │          │
   └────┴──────┴────────────────┴──────► SQLite      Pinecone   │
                                            │           │       │
3. All AI calls traced in LOGFIRE ──────────┴───────────┘       │
        │                                                        │
4. MCP SERVER exposes tools over SQLite + Pinecone + valuation code
        │
5. AI ASSISTANT (Claude/GPT-4o) answers user questions:
   - "condition score?"        → SQL (get_property_summary)
   - "value after roof+kitchen?"→ code (calculate_renovation_roi)
   - "contractors for roof?"    → SQL (get_contractors)
   - "is cracked drywall covered?" → RAG (get_warranty_coverage)
```

---

## 16. Build Order / Milestones

Build in this sequence — each milestone is independently demoable.

**Milestone 1 — Foundation (Day 1)**
- Repo scaffold, `requirements.txt`, `.env`
- SQLite schema + `setup_db.py` + seed contractors
- Logfire config
- Basic FastAPI app that boots

**Milestone 2 — Photo pipeline (Day 2)**
- OpenCV preprocessing
- Image agent → GPT-4o Vision → JSON
- Presidio redaction layer
- `/ingest/photo` endpoint working end-to-end
- Verify traces in Logfire

**Milestone 3 — Structured extraction (Day 3)**
- Blueprint agent (Mistral OCR + GPT-4o)
- Inspection form parser
- Store results in SQLite
- `/ingest/blueprint` and `/ingest/inspection` endpoints

**Milestone 4 — Valuation module (Day 3)**
- Deterministic calculator from the formulas PDF
- Unit tests against the PDF's worked examples ($288k base, $355k after all renos)

**Milestone 5 — RAG subsystem (Day 4)**
- LangChain ingestion with structural chunking
- Pinecone index setup
- Retriever + cross-encoder reranker
- LangGraph agent (retrieve→grade→answer)
- Ingest the warranty PDF, test queries

**Milestone 6 — MCP server (Day 5)**
- All six MCP tools wired to SQLite / code / RAG
- Connect to Claude Desktop, test each tool live

**Milestone 7 — Frontend (Day 6)**
- Vue upload + property card + renovation table + chat
- Wire to FastAPI

**Milestone 8 — Polish + demo (Day 7)**
- Record the demo video
- Clean README, architecture diagram
- Verify Logfire dashboard tells a clear story

---

## 17. Demo Script

**Minute 1 — The problem.** RealPage manages millions of units. Property assessment is manual: someone opens each photo, reads each PDF, re-enters data by hand.

**Minute 2 — Multimodal upload.** Drop in property photos, a blueprint, a filled inspection form, and the warranty PDF. Show each routing to its pipeline. Point out the OpenCV face-blur on a photo (before/after) and the Presidio redaction event in Logfire.

**Minute 3 — Structured intelligence.** Show the generated property card: condition score 6.2/10, estimated value $385k, ranked renovation list with cost, value uplift, and ROI per item. Note that this came from SQL + deterministic formulas, not RAG.

**Minute 4 — The chat / MCP.** Open Claude Desktop connected to the MCP server. Ask: *"What's the value after replacing the roof and remodeling the kitchen?"* → deterministic tool. Then: *"Is a 1/8 inch crack in the master bath drywall covered under warranty?"* → RAG returns a cited answer (Section 7, 1/32 inch threshold).

**Minute 5 — The scale pitch.** Every AI call traced in Logfire. Right tool per input — SQL for structured, code for formulas, RAG only for long legal docs. PII redacted before any external LLM. "This is the 10–100x leverage RealPage is looking for: turning a pile of photos, blueprints, and PDFs into structured, queryable, auditable property intelligence — instantly, at scale."

---

*End of implementation reference.*
