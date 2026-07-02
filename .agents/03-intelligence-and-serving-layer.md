# Property Intelligence System — Module 3: Intelligence & Serving Layer

> Part 3 of 4. See also: [01 — Overview & Architecture](./01-overview-and-architecture.md), [02 — Data Layer & Ingestion](./02-data-layer-and-ingestion.md), [04 — Frontend & Delivery](./04-frontend-and-delivery.md).

---

## Table of Contents

9. [Valuation Module (Deterministic)](#9-valuation-module-deterministic)
10. [RAG Subsystem (LangChain + LangGraph)](#10-rag-subsystem-langchain--langgraph)
11. [MCP Server](#11-mcp-server)
12. [Observability with Logfire](#12-observability-with-logfire)
13. [Backend API (FastAPI)](#13-backend-api-fastapi)

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

**Previous:** [02 — Data Layer & Ingestion](./02-data-layer-and-ingestion.md) · **Next:** [04 — Frontend & Delivery](./04-frontend-and-delivery.md)
