# Property Intelligence System — Module 2: Data Layer & Ingestion

> Part 2 of 4. See also: [01 — Overview & Architecture](./01-overview-and-architecture.md), [03 — Intelligence & Serving Layer](./03-intelligence-and-serving-layer.md), [04 — Frontend & Delivery](./04-frontend-and-delivery.md).

---

## Table of Contents

5. [Environment Setup](#5-environment-setup)
6. [Data Layer — SQLite Schema](#6-data-layer--sqlite-schema)
7. [PII Redaction Layer](#7-pii-redaction-layer)
8. [Ingestion Pipelines](#8-ingestion-pipelines)

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

**Previous:** [01 — Overview & Architecture](./01-overview-and-architecture.md) · **Next:** [03 — Intelligence & Serving Layer](./03-intelligence-and-serving-layer.md)
