# Team Intelligence — Progress Log

---

## Phase 1 — Mock Data Construction

### 1.1 Project Story & Workplan
- Defined the project narrative: **NOP Risk Model Modernization** at Transport Canada (fictional)
- Characters: Jason Hao (Technical Lead), Sean (Project Lead), Dr. Aris (Consultant), Dave (Inspector), Marc (Director), Carolyn (Manager), Roger (Sr. Analyst), Stephen (Auditor)
- Core story arc: 2015 risk model failing → 14% false negative rate → rebuild with 15% geographic weight → streamlining filter → audit → success
- Documented in `Workplan.md`

---

### 1.2 Email Data (`/Email/`)
- Created **10 JSON files** (`email1.json` – `email10.json`), 5 emails each = **50 emails** (`MSG-001` to `MSG-050`)
- Created **`meetings.json`** — 8 meeting invite emails (`MTG-001` to `MTG-008`)
- Created **`email_add.json`** — 5 versioned emails (`MSG-012-V1`, `MSG-013-V1`, `MSG-016-V2`, `MSG-019-V2`, `MSG-038-V1`) with attachment metadata to mock the v1/v2 back-and-forth
- Wrote `json_to_eml.py` to convert all JSON → proper `.eml` files
- Output: **63 `.eml` files** in `/Email/eml/` — RFC 2822 compliant, with MIME multipart structure for emails with attachments

---

### 1.3 Work Files (`/Work/`)
**Manually created (mock artifacts):**
- `Algorithm_Methodology_v1.0_Draft.txt` — Dr. Aris's initial methodology (Scenario A, 10% geo weight)
- `Algorithm_Methodology_v2.0_Final.txt` — Final methodology (Scenario B, 15% geo weight)
- `Conflict_Check_Report_v1.0.txt`
- `FY2026_Performance_Draft_Internal.txt` / `FY2026_Performance_Metric_Final.txt`
- `Internal_Audit_Memo_2027_01_Final.txt`
- `Maintenance_Manual_Section_4_Recalibration.txt`
- `North_York_Incident_Report_Summary.txt`
- `2027_Trend_Watch_Class3.txt`
- `Transport Canada NOP 2026-27 Modernization.pptx`

**Converted via `convert_work_files.py`:**
- `BC_Okanagan_Streamline_Audit_Data.json` → **`BC_Okanagan_Streamline_Audit_Data.csv`**
- `Impact_Summary_Table_v1_Aris_Draft.json` → **`Impact_Summary_Table_v1_Aris_Draft.xlsx`** (3 sheets: Metadata, Scenario Metrics, Regional Coverage %)
- `Impact_Summary_Table_v2_Jason_Sensitivity_Analysis.json` → **`Impact_Summary_Table_v2_Jason_Sensitivity_Analysis.xlsx`** (4 sheets: Metadata, Config & Performance, Regional Impact Matrix, Feasibility)
- `TDG_CORE_Data_Dictionary_v2.1.json` → **`TDG_CORE_Data_Dictionary_v2.1.xlsx`** (2 sheets: Fields, Change Log)
- `PROD_RUN_AUG01.log` → **`NOP_Risk_Model_PROD_AUG01.sas`** (54 lines, extracted from log)

**Original source files moved to `/Work/archive/`**

---

### 1.4 Guide / Policy Documents (`/guide/`)
- `TBS_Directive_on_Automated_Decision_Making_v3.txt` — Federal directive requiring AIA, HITL, traceability, data integrity
- `Vancouver_Maritime_Review_May_2026.txt` — External industry report validating the geographic weight change
- `Env_Canada_Technical_Brief_Winter2026.txt` — ECCC polar vortex brief explaining Class 3 spike
- `Internal_Audit_Guideline_ADS_202-B.txt` — TC internal audit guideline with Four Pillars framework

Each guide document maps to a specific decision or event in the project narrative.

---

### 1.5 Meeting Minutes (`/meetings/`)
- 8 meeting minutes files covering the full project lifecycle:

| File | Date | Key Event |
|---|---|---|
| `Meeting_Minutes_2026-06-05_Project_Kickoff.txt` | 2026-06-05 | Aris presents Scenario A, Dave pushes back |
| `Meeting_Minutes_2026-06-12_Technical_Review.txt` | 2026-06-12 | Jason reveals 11,240 legacy decay records |
| `Meeting_Minutes_2026-06-15_Scenario_Alignment.txt` | 2026-06-15 | Team aligns on Scenario B + Streamlining |
| `Meeting_Minutes_2026-06-17_Decision_Final_Signoff.txt` | 2026-06-17 | Marc approves 15% weight — production go-ahead |
| `Meeting_Minutes_2026-07-08_Technical_Implementation.txt` | 2026-07-08 | SAS logic mapping, UAT parallel run |
| `Meeting_Minutes_2026-10-15_Audit_Interview.txt` | 2026-10-15 | Stephen audits Jason's SAS code walk-through |
| `Meeting_Minutes_2027-01-20_Trend_Analysis.txt` | 2027-01-20 | Class 3 spike identified, proactive adjustment |
| `Meeting_Minutes_2027-03-10_Project_Closeout_Viya_Kickoff.txt` | 2027-03-10 | Fully Compliant audit result, Viya migration kick-off |

---

### 1.6 Data Quality Fixes
Cross-document consistency issues found and corrected manually:

| File | Fix |
|---|---|
| `Algorithm_Methodology_v1.0_Draft.txt` | W3 corrected 0.05 → 0.10, W1 corrected 0.45 → 0.40 to match Scenario A definition in all meetings and Impact Summary v1 |
| `Meeting_Minutes_2026-06-05_Project_Kickoff.txt` | "Next Meeting" date corrected June 17 → June 12 |
| `Meeting_Minutes_2026-10-15_Audit_Interview.txt` | SAS filter threshold corrected `01JAN1950` → `01JAN1901` to match actual production SAS code |
| `Env_Canada_Technical_Brief_Winter2026.txt` | Added Prairie region secondary risk paragraph to seed Jason's May 2027 Class 3 Prairie spike email |

---

## Phase 2 — Demo System

### 2.1 Architecture & Planning
- Defined tech stack: **Python FastAPI** (port 8000) + **Node.js Express** (port 3000) + **HTML/CSS/JS** frontend
- Embeddings: **Gemini `text-embedding-004`**
- Generation: **Gemini `gemini-2.0-flash`** (standard) / **`gemini-2.5-pro`** (complex reasoning)
- Vector store: **ChromaDB** (local, file-persisted)
- Defined full **metadata schema** for ChromaDB chunks
- Defined **6 core demo questions** with expected query types and key source documents
- Defined **7 build steps**, each with testable API endpoints
- Documented in `Architecture.md`

---

### 2.2 Step 1 — Ingestion & Parsing ✅

**Files created:**
- `demo_system/python/config.py` — all paths and tunables
- `demo_system/python/ingest.py` — file parser for all 8 file types
- `demo_system/python/metadata_rules.py` — rule-based metadata extraction (no LLM)
- `demo_system/python/main.py` — FastAPI app with Step 1 endpoints
- `demo_system/python/requirements.txt`

**Results: 90/90 files parsed successfully**

| Source | File type | Count |
|---|---|---|
| `/Email/eml/` | `email` | 63 |
| `/meetings/` | `meeting_minutes` | 8 |
| `/Work/` | `word_doc`, `excel_sheet`, `csv`, `sas_script`, `powerpoint`, `log_file` | 15 |
| `/guide/` | `policy_doc` | 4 |

**Rule-based metadata extracted without LLM:**

| Field | Coverage | Notes |
|---|---|---|
| `event_date` | 86/90 | 4 missing = Excel/CSV/SAS (no date in content) |
| `author` | 80/90 | Remaining = institutional authors, not personal names |
| `contributors` | 78/90 | Remaining = structural files (CSV, some Excel) |
| `document_version` | 18/90 | Versioned work files + emails all captured |
| `approval_status` | 90/90 | 100% coverage |
| `thread_id` | 63/63 emails | 9 threads reconstructed from In-Reply-To headers |
| `references_docs` | 3 docs | SAS → MSG-008, Data Dict → MSG-008, Impact v2 → MSG-016-V2 |

**Privacy hook fields defaulted (enforced in future):**
- `sensitivity_level` = `"internal"`
- `permitted_roles` = `["*"]`
- `owner_team` = `"Strategic Oversight"`

**Gemini will fill in Step 2:**
- `topics` = `[]`
- `project_phase` = `None`
- Prose-based `references_docs` (e.g. "as discussed in the June 17 meeting")
- Remaining dates (Excel, CSV, SAS)

**Live API endpoints (port 8000):**
```
POST /api/ingest/run
GET  /api/ingest/status
GET  /api/docs
GET  /api/docs/{doc_id}
GET  /api/health
```

**Output:** `demo_system/python/cache/parsed_docs.json` — 90 documents with full structural metadata

---

### 2.3 Step 2 — Gemini Metadata Enrichment ✅

**Files created:**
- `demo_system/python/enricher.py` — Gemini enrichment pipeline

**Results: 90/90 documents enriched successfully**

| Field | Result |
|---|---|
| `topics` | 2–5 controlled tags per doc, 24-tag vocabulary |
| `project_phase` | 1 phase per doc, 9-phase vocabulary |
| `references_docs` | 74 cross-document links added from prose |
| `event_date` | Filled for remaining docs where possible |

**Topic frequency highlights:** `risk_scoring` (48 docs), `geographic_weight` (43), `data_hygiene` (37), `streamlining` (31)

**Phase breakdown:** `operations` (23), `review` (21), `development` (10), `audit` (10)

**Top cited documents:**
- `TDG_CORE_Data_Dictionary_v2.1` — 14×
- `NOP_Risk_Model_PROD_AUG01.sas` — 11×
- `Algorithm_Methodology_v2.0_Final` — 10×

**Live API endpoints added:**
```
POST /api/enrich/run
GET  /api/enrich/status
GET  /api/docs/{doc_id}/meta
GET  /api/stats/topics
GET  /api/stats/phases
GET  /api/stats/references
```

**Output:** `demo_system/python/cache/enriched_docs.json`

---

### 2.4 Step 2.5 — Knowledge Graph ✅

**Files created:**
- `demo_system/python/graph_builder.py` — NetworkX MultiDiGraph from enriched metadata
- `demo_system/python/graph_export.py` — D3.js JSON export for frontend visualization

**Graph stats: 135 nodes, 947 edges**

| Node type | Count |
|---|---|
| document | 90 |
| person | 12 |
| topic | 24 |
| phase | 9 |

| Edge type | Count | Source |
|---|---|---|
| CONTRIBUTED_TO | 205 | rule-based |
| TAGGED_WITH | 399 | rule-based |
| AUTHORED | 80 | rule-based |
| REFERENCES | 74 | rule-based |
| IN_PHASE | 90 | rule-based |
| EXPERT_IN | 74 | rule-based |
| SUPERSEDES | 5 | rule-based |
| APPROVED | 11 | Gemini |
| OPPOSED | 3 | Gemini |
| TRIGGERED | 4 | Gemini |

**Query helpers built:**
- `get_person_profile()` — contributor fingerprint per person
- `expand_from_docs()` — graph expansion for hybrid vector+graph retrieval (Step 4)
- `find_approval_chain()` — trace version lineage and decision actors
- `get_graph_stats()` — node/edge breakdown

**D3.js export modes** (for frontend graph visualization):
- `full` — 135 nodes, 945 links (complete graph)
- `people` — 102 nodes, 299 links (people + docs only)
- `core` — 102 nodes, 177 links (key relationships only — best for demo)

**Live API endpoints added:**
```
POST /api/graph/build
GET  /api/graph/status
GET  /api/graph/stats
GET  /api/graph/d3?mode=full|people|core
GET  /api/graph/person/{person_name}
GET  /api/graph/doc/{doc_id}/chain
POST /api/graph/expand
```

**Output:** `demo_system/python/cache/knowledge_graph.json`, `cache/graph_d3_*.json`

---

### 2.5 Step 3 — Chunking + Embedding + ChromaDB Index ✅

**Files created:**
- `demo_system/python/chunker.py` — file-type-specific chunking strategies
- `demo_system/python/indexer.py` — Gemini embedding + ChromaDB storage

**Chunking strategies:**

| File type | Strategy |
|---|---|
| `email` | One chunk per email (short), sliding window if long |
| `meeting_minutes` | Split by section marker, then sliding window |
| `sas_script` | One chunk per PROC/DATA block |
| `excel_sheet` | Row groups with sheet name + column headers prepended |
| `csv` | Row groups with header row prepended |
| `policy_doc` | Split by numbered section, then sliding window |
| `word_doc`, `log_file`, `powerpoint` | Sliding window with overlap |

**Results: 128 chunks across 90 documents**

| File type | Chunks |
|---|---|
| email | 63 |
| meeting_minutes | 26 |
| policy_doc | 16 |
| excel_sheet | 6 |
| sas_script | 5 |
| word_doc | 9 |
| csv | 1 |
| powerpoint | 2 |

**Embedding model:** `models/gemini-embedding-001` (updated from deprecated `text-embedding-004`)

**ChromaDB:** Local persistent collection `team_intelligence`, cosine similarity, metadata filters enabled

**Live API endpoints added:**
```
POST /api/index/build
GET  /api/index/stats
POST /api/search/raw
```

**Output:** `demo_system/python/chroma_db/` — 128 embedded chunks with full metadata

---

### 2.6 Step 4 — Query Router + Smart Retrieval ✅

**Files created:**
- `demo_system/python/router.py` — keyword/pattern query classifier
- `demo_system/python/retriever.py` — strategy-based retrieval dispatcher

**Query types and strategies:**

| Type | Trigger | Retrieval strategy |
|---|---|---|
| `causal_trace` | why, reason, changed, decided | Vector search → sort by date → graph expand (REFERENCES + TRIGGERED) |
| `contributor_profile` | person name + did/contributed | ChromaDB filter by author → vector search within subset |
| `conflict_detect` | conflict, contradiction, disagree | Two-pass: vector + draft docs + approved docs merged |
| `audit_chain` | audit, compliance, evidence | Filter by file_type (policy/word/meetings) → 2-hop graph walk |
| `onboarding` | new, start, read first | Filter by early phases → sort by phase order |
| `org_lookup` | manages, reports to, team, scope | Pure graph/org data — zero API calls |
| `general` | fallback | Standard top-k vector search |

**Router accuracy: 12/12 on all test questions (6 demo + 6 org questions)**

**Org chart added** (`org_chart.json`):
- 8 people with title, scope, bio, skills, reporting line
- 2 teams (NOP Project Team, Data & Technical Sub-team) with goal + description
- Three-tier org lookup: person → team → skill matching — all in-memory, no API calls

**Graph additions:**
- `MANAGES` / `REPORTS_TO` edges (hierarchy)
- `MEMBER_OF` / `LEADS` edges (team membership)
- Person nodes enriched with title, employment_type, scope, bio, contact

**Live API endpoints added:**
```
POST /api/query/classify
POST /api/search/smart
GET  /api/graph/org
GET  /api/graph/org/{person_name}
```

---

### 2.7 Step 5 — Generation + Source Citation ✅

**Files created:**
- `demo_system/python/generator.py` — Gemini generation with inline citation enforcement

**Model routing:**
- `gemini-2.5-pro` — `conflict_detect`, `audit_chain` (multi-source reasoning)
- `gemini-2.0-flash` — all other query types

**System prompt enforces:**
- Every factual claim cited with `[Source: doc_id]`
- Contradictions stated explicitly, never silently resolved
- `audit_chain` answers formatted as sequential provenance chain
- `onboarding` answers formatted as a reading guide
- "Not found in project records." when answer unavailable

**Test results on 7 questions:**

| Question | Type | Model | Citations |
|---|---|---|---|
| Why was geographic weight changed? | `causal_trace` | flash | 3 sources |
| What did Jason contribute? | `contributor_profile` | flash | 10 sources |
| Any conflicts between documents? | `conflict_detect` | pro | 4 sources (real conflict found) |
| What should new person read first? | `onboarding` | flash | 7 sources |
| Full compliance audit chain? | `audit_chain` | pro | 15 sources |
| Role of ERAP in streamlining? | `general` | flash | answered correctly |
| Who manages Jason / his scope? | `org_lookup` | flash | org_chart cited |

**Live API endpoint added:**
```
POST /api/query?q=...
```

**Response format:**
```json
{
  "answer":          "...prose with [Source: doc_id] citations...",
  "query_type":      "causal_trace",
  "model_used":      "gemini-2.0-flash",
  "cited_sources":   ["MSG-020", "work_Algorithm_Methodology_v2_0_Final"],
  "all_sources":     [{ "doc_id", "file_type", "author", "event_date", "cited", "excerpt" }],
  "retrieval_count": 8
}
```

---

## Next Steps

| Step | Description | Status |
|---|---|---|
| Step 6 | Frontend — Node.js Express + HTML/CSS/JS + D3.js graph visualization | `[ ]` |
| Step 7 | Demo hardening — caching, health checks, demo mode | `[ ]` |
| Future | Adjacent team privacy feature | `[ ]` |
