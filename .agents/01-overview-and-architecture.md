# Property Intelligence System — Module 1: Overview & Architecture

**A multimodal AI platform for automated property assessment, valuation, and renovation intelligence.**

Built for the RealPage builder submission. Ingests property photos, blueprints, inspection forms, and legal/valuation PDFs; produces structured property intelligence queryable in natural language via an MCP server.

> Part 1 of 4. See also: [02 — Data Layer & Ingestion](./02-data-layer-and-ingestion.md), [03 — Intelligence & Serving Layer](./03-intelligence-and-serving-layer.md), [04 — Frontend & Delivery](./04-frontend-and-delivery.md).

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Tech Stack](#2-tech-stack)
3. [The Core Design Principle: Right Tool Per Input](#3-the-core-design-principle-right-tool-per-input)
4. [Repository Structure](#4-repository-structure)

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

**Next:** [02 — Data Layer & Ingestion](./02-data-layer-and-ingestion.md)
