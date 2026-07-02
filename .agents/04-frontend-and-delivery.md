# Property Intelligence System — Module 4: Frontend & Delivery

> Part 4 of 4. See also: [01 — Overview & Architecture](./01-overview-and-architecture.md), [02 — Data Layer & Ingestion](./02-data-layer-and-ingestion.md), [03 — Intelligence & Serving Layer](./03-intelligence-and-serving-layer.md).

---

## Table of Contents

14. [Frontend (Vue.js)](#14-frontend-vuejs)
15. [End-to-End Flow](#15-end-to-end-flow)
16. [Build Order / Milestones](#16-build-order--milestones)
17. [Demo Script](#17-demo-script)

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

**Previous:** [03 — Intelligence & Serving Layer](./03-intelligence-and-serving-layer.md)

*End of implementation reference.*
