# Team Intelligence — Architecture & Build Plan

## Status Legend
- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete
- `[!]` Blocked / needs decision

---

## Tech Stack

| Component | Choice | Notes |
|---|---|---|
| File parsing | `unstructured.io` (Python) | Handles all file types in one library |
| Embeddings | Gemini `text-embedding-004` | 768-dim, 2048 token limit |
| Metadata extraction | Gemini `gemini-2.0-flash` | Fast + cheap for structured extraction |
| Generation (standard) | Gemini `gemini-2.0-flash` | causal_trace, contributor_profile, general |
| Generation (complex) | Gemini `gemini-2.5-pro` | conflict_detect, audit_chain |
| Vector store | `ChromaDB` | Local, file-persisted, no server needed |
| Backend API | `Python FastAPI` (port 8000) | Each RAG step exposed as testable endpoint |
| Frontend server | `Node.js + Express` (port 3000) | Serves HTML, proxies /api/* to FastAPI |
| Frontend | Custom `HTML + CSS + Vanilla JS` | No framework, full control |

---

## Folder Structure

```
/Team intelligence/
  /demo_system/
    /python/
      main.py            ← FastAPI app entry point
      ingest.py          ← Step 1: parsing pipeline
      enricher.py        ← Step 2: Gemini metadata extraction
      chunker.py         ← Step 3: chunking strategies
      router.py          ← Step 4: query classification
      retriever.py       ← Step 4: ChromaDB retrieval
      generator.py       ← Step 5: Gemini generation + citation
      privacy.py         ← stub (always present, enforced later)
      config.py          ← all tunables
      requirements.txt
      /cache/
        parsed_docs.json
        enriched_docs.json
      /chroma_db/
      /logs/

    /node/
      server.js          ← Express server + API proxy
      package.json
      /public/
        index.html
        style.css
        app.js
```

---

## Data Sources

| Folder | File Types | Count | Description |
|---|---|---|---|
| `/Email/eml/` | `.eml` | 63 | Emails + meeting invites |
| `/meetings/` | `.txt` | 8 | Meeting minutes |
| `/Work/` | `.txt`, `.xlsx`, `.csv`, `.sas`, `.log`, `.pptx` | ~15 | Project work files |
| `/guide/` | `.txt` | 4 | Policy and reference documents |

---

## Metadata Schema

Every chunk stored in ChromaDB carries this metadata:

```python
{
  # Identity
  "doc_id":             str,   # e.g. "email_042", "meeting_003"
  "source_path":        str,   # absolute path to original file
  "file_type":          str,   # "email" | "meeting_minutes" | "sas_script" |
                               # "excel_sheet" | "csv" | "word_doc" |
                               # "policy_doc" | "log_file" | "powerpoint"
  # Temporal
  "event_date":         str,   # sent/written/meeting date (ISO format)

  # Authorship
  "author":             str,   # primary author
  "contributors":       list,  # ["Jason Hao", "Dr. Aris"]

  # Topical
  "topics":             list,  # ["geographic_weight", "data_hygiene", "streamlining"]
  "project_phase":      str,   # "development" | "review" | "approval" | "audit"

  # Cross-document linking
  "thread_id":          str,   # email thread or meeting series ID
  "references_docs":    list,  # doc_ids explicitly mentioned in this doc
  "referenced_by_docs": list,  # populated in second pass

  # Version / Status
  "document_version":   str,   # "v1" | "v2" | "final" | "draft"
  "approval_status":    str,   # "approved" | "draft" | "superseded"

  # Privacy hook (populated now, enforced later)
  "sensitivity_level":  str,   # "public" | "internal" | "restricted"
  "permitted_roles":    list,  # ["*"] default = all roles
  "owner_team":         str,   # team that owns this document

  # Chunk position
  "chunk_index":        int,
  "chunk_total":        int,
  "parent_doc_id":      str
}
```

---

## Query Types & Routing

| Type | Trigger signals | Retrieval strategy | Model |
|---|---|---|---|
| `causal_trace` | why, reason, changed, decided | Sort by date + expand thread | Flash |
| `contributor_profile` | person name + did/contributed | Filter by contributor → similarity | Flash |
| `conflict_detect` | conflict, contradiction, mismatch | Two-pass: retrieve → compare clusters | Pro |
| `audit_chain` | audit, compliance, provenance, evidence | Walk references_docs graph | Pro |
| `onboarding` | new person, start, read first | Rank by version + phase centrality | Flash |
| `general` | fallback | Standard top-k similarity | Flash |

---

## 6 Core Demo Questions

| # | Question | Expected query type | Key sources |
|---|---|---|---|
| 1 | "Why was the geographic weight changed from 5% to 15%?" | `causal_trace` | Emails, meetings, Vancouver Maritime Review, Sensitivity Analysis v2 |
| 2 | "What did Jason contribute technically to this project?" | `contributor_profile` | SAS script, emails, meeting minutes |
| 3 | "Are there any conflicts or contradictions between documents?" | `conflict_detect` | Algorithm v1 vs v2, emails vs meeting decisions |
| 4 | "What should a new person read first to understand this project?" | `onboarding` | process.md, methodology docs, key meeting minutes |
| 5 | "Show the full compliance audit chain for the risk model." | `audit_chain` | TBS Directive → meetings → SAS script → Excel output |
| 6 | "Why can I see Jason's name but not open his SAS file?" | `privacy_routing` | Adjacent team feature (deferred) |

---

## Build Steps

---

### Step 1 — Ingestion & Parsing
**Status:** `[x]`

**What gets built:** `ingest.py` — walks all 4 data folders, routes each file to the correct parser, outputs `cache/parsed_docs.json`

**Chunking rules by file type:**

| File type | Strategy | Target size |
|---|---|---|
| `.eml` | One chunk per email | ~300 tokens |
| Meeting `.txt` | One chunk per agenda section | ~400 tokens |
| Doc `.txt` | Sliding window with overlap | 512 tokens, 128 overlap |
| `.sas` / code | One chunk per PROC/DATA block | Variable |
| `.xlsx` sheets | Row groups with column headers prepended | ~200 tokens |
| `.csv` | Row groups with column headers prepended | ~200 tokens |
| Policy `.txt` | One chunk per numbered section | ~600 tokens |

**API endpoints:**
```
POST /api/ingest/run          ← triggers the pipeline
GET  /api/ingest/status       ← count per file type + failures
GET  /api/docs                ← list all parsed docs
GET  /api/docs/{doc_id}       ← inspect one doc's raw text
```

**Test criteria:**
- All files have `parse_status: success`
- Email files show sender, recipients, date as separate fields
- Excel files show per-sheet content with sheet name prepended
- SAS file preserves code structure and comments

---

### Step 2 — Metadata Enrichment
**Status:** `[ ]`

**What gets built:** `enricher.py` — sends each parsed doc to `gemini-2.0-flash` with a structured extraction prompt, outputs `cache/enriched_docs.json`

**API endpoints:**
```
POST /api/enrich/run            ← triggers enrichment pass
GET  /api/docs/{doc_id}/meta    ← inspect one doc's metadata
GET  /api/stats/contributors    ← contributor frequency across corpus
GET  /api/stats/topics          ← topic frequency across corpus
GET  /api/stats/references      ← cross-document reference graph
```

**Test criteria:**
- Jason Hao appears as contributor in: SAS files, emails, meeting minutes
- "geographic_weight" topic appears across 5+ different documents
- `references_docs` contains actual links (e.g. SAS log references MSG-008)
- All docs have a non-null `event_date`

---

### Step 3 — Chunking + Embedding + Vector Index
**Status:** `[ ]`

**What gets built:** `chunker.py` splits documents per file-type rules → `text-embedding-004` embeds each chunk → loads into ChromaDB

**API endpoints:**
```
POST /api/index/build             ← chunks + embeds + stores in ChromaDB
GET  /api/index/stats             ← total chunks, breakdown per file type
POST /api/search/raw              ← pure vector search, NO LLM
  body: { "query": "...", "n": 10, "filter": { "file_type": "email" } }
```

**Test criteria:**
- Raw query `"geographic weight"` returns chunks from: emails + meetings + spreadsheet (not just one type)
- Raw query `"Jason Hao SAS"` returns SAS code chunks
- Raw query `"1900 date legacy decay"` returns email, meeting, and SAS log chunks
- Excel chunks all contain column headers in the chunk text

---

### Step 4 — Query Router + Smart Retrieval
**Status:** `[ ]`

**What gets built:** `router.py` classifies query type → `retriever.py` applies the matching strategy

**API endpoints:**
```
POST /api/query/classify
  body: { "query": "Why was the geographic weight changed?" }
  → { "type": "causal_trace", "confidence": 0.91 }

POST /api/search/smart
  body: { "query": "...", "n": 10 }
  → ranked chunks with full metadata, NO generation
```

**Test criteria:**
- All 6 demo questions classify to the correct type
- `causal_trace` query returns mix of emails + meetings (not just one source type)
- `contributor_profile` query for Jason returns SAS + emails + meeting content
- `conflict_detect` returns documents from both sides of a known discrepancy

---

### Step 5 — Generation + Source Citation
**Status:** `[ ]`

**What gets built:** `generator.py` — takes retrieved chunks, builds context prompt, calls Gemini, returns structured response with inline `[Source: doc_id]` citations

**System prompt (enforced):**
```
You are a project knowledge assistant for the NOP Risk Model project.
Answer using ONLY the provided source documents.
Every factual claim must be followed by [Source: doc_id].
If sources contradict each other, state the contradiction explicitly and cite both.
If you cannot answer from provided sources, say: "Not found in project records."
```

**API endpoints:**
```
POST /api/query
  body: { "query": "..." }
  → {
      "answer": "The weight was changed because... [Source: MSG-013-V1]...",
      "query_type": "causal_trace",
      "model_used": "gemini-2.0-flash",
      "sources": [
        {
          "doc_id": "MSG-013-V1",
          "file_type": "email",
          "contributor": "Dave",
          "date": "2026-06-13",
          "excerpt": "..."
        }
      ],
      "retrieval_count": 8
    }
```

**Test criteria:**
- All 6 demo questions return answers with at least 2 cited sources
- Every cited `doc_id` exists in the retrieval result (no hallucinated sources)
- Conflict detection question explicitly flags the contradiction (does not silently pick one side)
- Audit chain question shows a sequential provenance path

---

### Step 6 — Frontend (HTML + Node.js)
**Status:** `[ ]`

**What gets built:** Node.js Express serves the HTML frontend and proxies API calls to FastAPI

**Node.js responsibilities:**
- Serves static files from `/node/public/`
- Proxies all `/api/*` requests to `http://localhost:8000`
- Future: adds auth headers, enforces team-level access before proxying

**Frontend layout (3 panels):**

*Left sidebar:*
- Project name + team identifier
- 6 pre-loaded demo question buttons
- Step tester panel — individual buttons for: ingest, enrich, index, classify, raw search, full query

*Main chat area:*
- Query input box
- Answer display with clickable `[Source: X]` citation links
- Query type badge (`causal_trace`, `audit_chain`, etc.)
- Model used indicator

*Right panel:*
- Source cards per cited document: filename, type, date, contributor, excerpt
- Expandable to full chunk text
- Provenance chain view for `audit_chain` queries (linear path display)

**Test criteria:**
- All 6 demo question buttons fire and return answers
- Source cards render with correct metadata
- Clicking a citation highlights the matching source card
- Step tester panel can trigger each step independently and show results

---

### Step 7 — Demo Hardening
**Status:** `[ ]`

**What gets built:** Reliability and caching layer

- **Response cache** — `POST /api/query/warm` pre-runs all 6 demo questions, caches results
- **Retrieval logging** — every query writes to `/logs/YYYYMMDD.jsonl`
- **Health check** — `GET /api/health` returns status of ChromaDB + Gemini API + cache
- **Demo mode** — `DEMO_MODE=true` in `config.py` serves only cached responses, no live API calls

**API endpoints:**
```
POST /api/query/warm     ← pre-caches all 6 demo questions
GET  /api/health         ← system status
GET  /api/logs/latest    ← last N query logs
```

**Test criteria:**
- `GET /api/health` returns all green
- With `DEMO_MODE=true`, all 6 demo questions serve without any API calls
- `/logs/` has a valid JSONL entry for every query run

---

## Future: Adjacent Team Feature
**Status:** `[ ]` — deferred until main system complete

**Concept:** When a user from Team A queries about Team B's project, the system returns a brief summary (expert name + skill tags) but never exposes raw documents.

**Architecture hook — already in place:**
- `sensitivity_level`, `permitted_roles`, `owner_team` fields exist in the metadata schema from Step 2
- `privacy.py` stub exists from day one with the correct interface
- Node.js proxy layer is where user session/team identity is read and injected as a header

**What still needs to be built:**
- Second project's data ingested under a different `owner_team`
- `privacy.py` filter logic implemented (currently passes everything through)
- User session model in Node.js (login → team assignment)
- "Expert card" response format for cross-team queries

---

## Known Risks

| Risk | Mitigation |
|---|---|
| Metadata extraction quality — if Step 2 misses topics/contributors, all cross-doc queries degrade | Validate coverage stats before proceeding to Step 3; set minimum thresholds |
| Email thread reconstruction — `In-Reply-To` headers must be used to stitch threads; failure = random ordering in causal trace | Dedicated thread reconstruction pass in Step 1 using email headers as primary key |
| Excel chunking loses context — naive chunking produces rows without column names | Always prepend sheet name + column headers to every Excel chunk |
| Conflict detection needs two-pass retrieval — standard RAG can't do this | Dedicated `conflict_detect_chain()` function, not routed through standard pipeline |
| Demo speed — reranking adds 2-4x latency | Skip reranking; use metadata pre-filtering to narrow candidates instead |

---

## Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-03-15 | Gemini family for embeddings + generation | User requirement |
| 2026-03-15 | Custom HTML + Node.js frontend instead of Gradio | User requirement — full control over UI |
| 2026-03-15 | Python FastAPI for backend, Node.js as proxy/gateway | Python best for RAG pipeline; Node.js handles frontend + future auth |
| 2026-03-15 | Single ChromaDB collection with metadata filters | Corpus small enough; simpler than per-type sub-indexes |
| 2026-03-15 | Adjacent team feature deferred | Build main system first, privacy hook kept in schema |
