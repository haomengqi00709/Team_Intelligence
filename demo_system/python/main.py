"""
FastAPI backend — Team Intelligence demo system
Step 1: ingestion & inspection
Step 2: Gemini metadata enrichment
"""

import json
import re
from pathlib import Path

import google.generativeai as genai
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import CACHE_DIR, UPLOADS_DIR
from ingest import get_ingestion_status, load_parsed_docs, run_ingestion
from enricher import get_enrichment_status, load_enriched_docs, run_enrichment
from graph_builder import (
    run_graph_build, load_graph, get_graph_build_status,
    get_person_profile, expand_from_docs, find_approval_chain, get_graph_stats,
    get_org_structure,
)
from graph_export import export_graph
from chunker import run_chunking, get_chunking_status
from indexer import run_indexing, run_step3, get_index_stats, raw_search
from router import classify
from retriever import retrieve
from generator import generate

app = FastAPI(
    title="Team Intelligence API",
    description="Step-by-step RAG pipeline for project knowledge retrieval",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Upload ─────────────────────────────────────────────────────────────────────

# Extension → human-readable folder name (unknown exts use the ext itself)
_EXT_FOLDER: dict[str, str] = {
    ".eml": "email",  ".msg": "email",
    ".docx": "documents", ".doc": "documents", ".txt": "documents", ".pdf": "documents",
    ".xlsx": "spreadsheets", ".xls": "spreadsheets", ".csv": "spreadsheets",
    ".pptx": "presentations", ".ppt": "presentations",
    ".sas": "sas_code",
    ".log": "logs",
}

# In-memory job tracker  {doc_id: {status, filename, folder, message}}
_upload_jobs: dict[str, dict] = {}


def _process_upload(doc_id: str, file_path: Path, source_folder: str, project_id: str = "") -> None:
    """Incrementally parse → enrich → chunk → index a single uploaded file."""
    try:
        from ingest import parse_file, load_parsed_docs
        from enricher import run_enrichment, load_enriched_docs
        from chunker import chunk_document, flatten_metadata, load_chunks
        from indexer import run_indexing

        # 1. Parse
        doc = parse_file(source_folder, file_path)

        parsed_path = Path(CACHE_DIR) / "parsed_docs.json"
        existing = load_parsed_docs() or []
        existing = [d for d in existing if d["doc_id"] != doc_id]
        existing.append(doc)
        parsed_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))

        # 2. Enrich (skips already-enriched docs)
        run_enrichment(verbose=False)

        # 3. Chunk
        enriched = load_enriched_docs() or []
        new_doc = next((d for d in enriched if d["doc_id"] == doc_id), doc)
        texts = [t.strip() for t in chunk_document(new_doc) if t.strip()]
        new_chunks = [
            {"chunk_id": f"{doc_id}_c{i:03d}", "text": t,
             "metadata": flatten_metadata(new_doc, i, len(texts), project_id=project_id)}
            for i, t in enumerate(texts)
        ]

        chunks_path = Path(CACHE_DIR) / "chunks.json"
        existing_chunks = load_chunks() or []
        existing_chunks = [c for c in existing_chunks if not c["chunk_id"].startswith(f"{doc_id}_c")]
        existing_chunks.extend(new_chunks)
        chunks_path.write_text(json.dumps(existing_chunks, indent=2, ensure_ascii=False))

        # 4. Index (skips already-indexed chunk_ids)
        run_indexing(verbose=False)

        # 5. Update project → doc_id mapping
        if project_id:
            proj_map_path = Path(CACHE_DIR) / "project_doc_map.json"
            try:
                proj_map = json.loads(proj_map_path.read_text()) if proj_map_path.exists() else {}
            except Exception:
                proj_map = {}
            proj_map.setdefault(project_id, [])
            if doc_id not in proj_map[project_id]:
                proj_map[project_id].append(doc_id)
            proj_map_path.write_text(json.dumps(proj_map, indent=2))

        # 6. Rebuild knowledge graph so Team tab reflects the new document
        run_graph_build(gemini_pass=False, verbose=False)

        _upload_jobs[doc_id]["status"] = "ready"

    except Exception as exc:
        _upload_jobs[doc_id]["status"] = "error"
        _upload_jobs[doc_id]["message"] = str(exc)


@app.post("/api/upload", tags=["Upload"])
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: str = "",
):
    """Accept a file upload, save it to uploads/{folder}/, process in the background."""
    ext         = Path(file.filename).suffix.lower()
    folder_name = _EXT_FOLDER.get(ext, ext.lstrip(".") or "other")
    dest_dir    = UPLOADS_DIR / folder_name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest        = dest_dir / file.filename

    content = await file.read()
    dest.write_bytes(content)

    from ingest import make_doc_id
    doc_id = make_doc_id(folder_name, dest)

    _upload_jobs[doc_id] = {
        "status":   "processing",
        "filename": file.filename,
        "folder":   folder_name,
        "message":  "",
    }
    background_tasks.add_task(_process_upload, doc_id, dest, folder_name, project_id)
    return {"doc_id": doc_id, "filename": file.filename, "folder": folder_name}


@app.get("/api/upload/status/{doc_id}", tags=["Upload"])
def upload_status(doc_id: str):
    """Poll processing status for an uploaded file."""
    return _upload_jobs.get(doc_id, {"status": "unknown"})


# ── Step 1 endpoints ──────────────────────────────────────────────────────────

@app.post("/api/ingest/run", tags=["Step 1 — Ingest"])
def ingest_run():
    """
    Trigger the full ingestion pipeline.
    Walks all 4 data folders, parses every file, writes cache/parsed_docs.json.
    """
    docs = run_ingestion(verbose=False)
    status = get_ingestion_status()
    return {
        "message": "Ingestion complete",
        "summary": status,
    }


@app.get("/api/ingest/status", tags=["Step 1 — Ingest"])
def ingest_status():
    """
    Show current ingestion status and breakdown without re-running.
    """
    return get_ingestion_status()


@app.get("/api/docs", tags=["Step 1 — Ingest"])
def list_docs(
    folder: str | None = None,
    file_type: str | None = None,
    status: str | None = None,
):
    """
    List all parsed documents with basic info.
    Optional filters: folder, file_type, status (success/partial/failed)
    """
    docs = load_parsed_docs()
    if not docs:
        return {"total": 0, "docs": [], "hint": "Run POST /api/ingest/run first"}

    if folder:
        docs = [d for d in docs if d["source_folder"] == folder]
    if file_type:
        docs = [d for d in docs if d["file_type"] == file_type]
    if status:
        docs = [d for d in docs if d["parse_status"] == status]

    summary = [
        {
            "doc_id":       d["doc_id"],
            "source_folder": d["source_folder"],
            "file_type":    d["file_type"],
            "parse_status": d["parse_status"],
            "word_count":   d["word_count"],
            "parse_error":  d["parse_error"],
        }
        for d in docs
    ]
    return {"total": len(summary), "docs": summary}


@app.get("/api/docs/{doc_id}", tags=["Step 1 — Ingest"])
def get_doc(doc_id: str, include_text: bool = True):
    """
    Inspect a single document — metadata + optionally full raw text.
    """
    docs = load_parsed_docs()
    doc  = next((d for d in docs if d["doc_id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail=f"doc_id '{doc_id}' not found")

    result = {k: v for k, v in doc.items() if k != "raw_text"}
    if include_text:
        result["raw_text"] = doc["raw_text"]
    else:
        result["raw_text_preview"] = doc["raw_text"][:500] + (
            "…" if len(doc["raw_text"]) > 500 else ""
        )
    return result


# ── Step 2 endpoints ──────────────────────────────────────────────────────────

@app.post("/api/enrich/run", tags=["Step 2 — Enrich"])
def enrich_run():
    """
    Trigger Gemini metadata enrichment on all parsed documents.
    Skips already-enriched docs (resume-safe).
    Writes cache/enriched_docs.json.
    """
    docs = run_enrichment(verbose=False)
    status = get_enrichment_status()
    return {
        "message": "Enrichment complete",
        "summary": status,
    }


@app.get("/api/enrich/status", tags=["Step 2 — Enrich"])
def enrich_status():
    """
    Show current enrichment status — how many docs are done, failed, topic/phase coverage.
    """
    return get_enrichment_status()


@app.get("/api/docs/{doc_id}/meta", tags=["Step 2 — Enrich"])
def get_doc_meta(doc_id: str):
    """
    Show Gemini-enriched metadata for a single document (topics, project_phase, references).
    Falls back to parsed_docs.json if enriched_docs.json is not available.
    """
    enriched = load_enriched_docs()
    if enriched:
        doc = next((d for d in enriched if d["doc_id"] == doc_id), None)
    else:
        docs = load_parsed_docs()
        doc  = next((d for d in docs if d["doc_id"] == doc_id), None)

    if not doc:
        raise HTTPException(status_code=404, detail=f"doc_id '{doc_id}' not found")

    return {
        "doc_id":          doc["doc_id"],
        "file_type":       doc["file_type"],
        "event_date":      doc.get("event_date"),
        "author":          doc.get("author"),
        "topics":          doc.get("topics", []),
        "project_phase":   doc.get("project_phase"),
        "references_docs": doc.get("references_docs", []),
        "enrichment_status": doc.get("enrichment_status", "not_run"),
    }


@app.get("/api/stats/topics", tags=["Step 2 — Enrich"])
def stats_topics():
    """
    Show topic frequency across all enriched documents.
    """
    status = get_enrichment_status()
    if status.get("status") == "not_run":
        return {"hint": "Run POST /api/enrich/run first", "topics": {}}
    return {"topics": status.get("topic_frequency", {})}


@app.get("/api/stats/phases", tags=["Step 2 — Enrich"])
def stats_phases():
    """
    Show project phase breakdown across all enriched documents.
    """
    status = get_enrichment_status()
    if status.get("status") == "not_run":
        return {"hint": "Run POST /api/enrich/run first", "phases": {}}
    return {"phases": status.get("phase_breakdown", {})}


@app.get("/api/stats/references", tags=["Step 2 — Enrich"])
def stats_references():
    """
    Show top cross-document references (which documents are most cited).
    """
    docs = load_enriched_docs() or load_parsed_docs()
    if not docs:
        return {"hint": "Run POST /api/ingest/run and POST /api/enrich/run first", "references": {}}

    ref_counts: dict[str, int] = {}
    for doc in docs:
        for ref in doc.get("references_docs", []):
            ref_counts[ref] = ref_counts.get(ref, 0) + 1

    sorted_refs = dict(sorted(ref_counts.items(), key=lambda x: -x[1]))
    return {"total_links": sum(ref_counts.values()), "references": sorted_refs}


# ── Step 3 endpoints ──────────────────────────────────────────────────────────

@app.post("/api/index/build", tags=["Step 3 — Index"])
def index_build(chunk_only: bool = False, embed_only: bool = False):
    """
    Build the ChromaDB vector index.
    Default: runs chunking then embedding in sequence.
    chunk_only=true  → only split documents, write cache/chunks.json
    embed_only=true  → only embed+index (assumes chunks.json exists)
    """
    if chunk_only:
        run_chunking(verbose=False)
        return {"message": "Chunking complete", "summary": get_chunking_status()}
    if embed_only:
        stats = run_indexing(verbose=False)
        return {"message": "Indexing complete", "summary": stats}
    stats = run_step3(verbose=False)
    return {"message": "Step 3 complete", "summary": stats}


@app.get("/api/index/stats", tags=["Step 3 — Index"])
def index_stats():
    """Show ChromaDB collection stats — total chunks and breakdown by file type."""
    return get_index_stats()


@app.post("/api/search/raw", tags=["Step 3 — Index"])
def search_raw(query: str, n: int = 10, file_type: str | None = None):
    """
    Pure vector search — no LLM generation.
    Returns top-n chunks with scores and metadata.
    Optional filter: file_type (email | meeting_minutes | word_doc | ...)
    """
    stats = get_index_stats()
    if stats.get("status") != "ok":
        raise HTTPException(status_code=503, detail="Index not built — POST /api/index/build first")

    filter_meta = {"file_type": file_type} if file_type else None
    hits = raw_search(query, n=n, filter_meta=filter_meta)
    return {"query": query, "total": len(hits), "results": hits}


# ── Step 5 endpoints ──────────────────────────────────────────────────────────

@app.post("/api/query", tags=["Step 5 — Generate"])
def query(q: str, n: int = 10, project_id: str | None = None):
    """
    Full RAG pipeline: classify → retrieve → generate.
    Returns answer with inline citations and source cards.
    Optional project_id scopes retrieval to documents from that project only.
    """
    stats = get_index_stats()
    if stats.get("status") != "ok":
        raise HTTPException(status_code=503, detail="Index not built — POST /api/index/build first")

    cl             = classify(q)
    retrieval      = retrieve(q, cl, n=n, project_id=project_id or None)
    response       = generate(q, retrieval)
    return response


# ── Project search endpoint ───────────────────────────────────────────────────

class ProjectSnippet(BaseModel):
    id: str
    name: str
    team: str
    manager: str
    status: str
    snippet: str

class ProjectSearchRequest(BaseModel):
    query: str
    projects: list[ProjectSnippet]

@app.post("/api/project/generate", tags=["Projects"])
def generate_project_meta(name: str, status: str):
    """
    Generate project description, phase, and tags from just a name + status.
    Uses Gemini Flash for a fast, smooth project creation experience.
    """
    from config import GEMINI_API_KEY, GENERATION_MODEL_FLASH
    genai.configure(api_key=GEMINI_API_KEY)

    prompt = f"""You are a project metadata assistant for a government data analytics team at Transport Canada's Transportation of Dangerous Goods branch.

A team member is creating a new project named "{name}" with status "{status}".

Generate the following metadata in JSON:
- "desc": a concise 1–2 sentence professional description of what this project likely involves (data, analytics, safety, risk, compliance, or regulatory context)
- "phase": the appropriate project phase for status "{status}" (e.g. "Discovery", "Planning", "Development", "Review & Sign-off", "Production")
- "tags": array of 2–4 lowercase hyphenated tags relevant to the project name (e.g. "risk-model", "analytics", "compliance", "data-quality")

Return only raw JSON, no markdown, no explanation:
{{"desc": "...", "phase": "...", "tags": ["...", "..."]}}"""

    model = genai.GenerativeModel(GENERATION_MODEL_FLASH)
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(temperature=0.3),
    )

    text = response.text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
        return {
            "desc":  str(data.get("desc", "")),
            "phase": str(data.get("phase", "Discovery")),
            "tags":  [str(t) for t in data.get("tags", [status])],
        }
    except json.JSONDecodeError:
        return {"desc": "", "phase": "Discovery", "tags": [status]}


@app.post("/api/projects/search", tags=["Projects"])
def projects_search(req: ProjectSearchRequest):
    """
    LLM-ranked project discovery.
    Pass a natural-language query and a list of project snippets.
    Returns projects ranked by relevance with a one-sentence explanation each.
    """
    from config import GEMINI_API_KEY, GENERATION_MODEL_FLASH
    genai.configure(api_key=GEMINI_API_KEY)

    projects_text = "\n\n".join(
        f"[{i+1}] ID: {p.id}\n"
        f"Name: {p.name}\n"
        f"Team: {p.team} | Manager: {p.manager} | Status: {p.status}\n"
        f"{p.snippet}"
        for i, p in enumerate(req.projects)
    )

    prompt = f"""You are a project discovery assistant for a government transport safety branch.
Given a user query, identify which projects from the list below are meaningfully relevant.

USER QUERY: {req.query}

PROJECTS:
{projects_text}

Return a JSON array of relevant matches only, ranked by relevance (most relevant first).
Each item must have exactly these fields:
  "id"        — the project id string
  "relevance" — one of: "high" | "medium" | "low"
  "reason"    — one concise sentence (max 20 words) explaining why it matches the query

Rules:
- Only include projects with genuine relevance to the query. Omit irrelevant ones entirely.
- If nothing is relevant, return an empty array: []
- Return only the raw JSON array. No markdown, no explanation, no code fences.

RESPONSE:"""

    model = genai.GenerativeModel(GENERATION_MODEL_FLASH)
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(temperature=0.1),
    )

    text = response.text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        matches = json.loads(text)
    except json.JSONDecodeError:
        matches = []

    return {"query": req.query, "matches": matches}


def _load_project_doc_ids(project_id: str) -> set[str] | None:
    """Return set of doc_ids belonging to project_id, or None if map missing."""
    proj_map_path = Path(CACHE_DIR) / "project_doc_map.json"
    if not proj_map_path.exists():
        return None
    try:
        proj_map = json.loads(proj_map_path.read_text())
        return set(proj_map.get(project_id, []))
    except Exception:
        return None


@app.get("/api/timeline/summary", tags=["Projects"])
def timeline_summary(project_id: str | None = None):
    """LLM-synthesized milestone timeline, cached until new docs are ingested.
    Pass project_id to scope the timeline to a specific project's documents."""
    from pathlib import Path
    cache_suffix = f"_{project_id}" if project_id else ""
    cache_file = Path(CACHE_DIR) / f"timeline_summary{cache_suffix}.json"

    docs = load_enriched_docs() or []
    if not docs:
        return {"milestones": [], "cached": False}

    # Filter to project docs if project_id provided
    if project_id:
        allowed = _load_project_doc_ids(project_id)
        if allowed is not None:
            docs = [d for d in docs if d["doc_id"] in allowed]
    if not docs:
        return {"milestones": [], "cached": False}

    newest_ts = max((d.get("parse_timestamp") or "" for d in docs), default="")

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            if cached.get("generated_at", "") >= newest_ts:
                return {**cached, "cached": True}
        except Exception:
            pass

    # Build event log for the LLM
    events = []
    for d in docs:
        if d.get("parse_status") != "success" or not d.get("event_date"):
            continue
        sf = d.get("structured_fields") or {}
        subject = sf.get("subject") or sf.get("title") or sf.get("meeting_title") or ""
        topics = d.get("topics") or []
        if isinstance(topics, str):
            try: topics = json.loads(topics)
            except: topics = []
        events.append({
            "doc_id":       d["doc_id"],
            "file_type":    d.get("file_type", ""),
            "event_date":   d.get("event_date", ""),
            "author":       d.get("author") or "",
            "contributors": d.get("contributors") or [],
            "topics":       topics[:5],
            "phase":        d.get("project_phase") or "",
            "subject":      subject,
        })
    events.sort(key=lambda x: x["event_date"])

    events_text = "\n".join(
        f"[{e['event_date']}] {e['file_type']} {e['doc_id']}"
        f"{' | ' + e['subject'] if e['subject'] else ''}"
        f" | by {e['author']}"
        f" | contributors: {', '.join(e['contributors'])}"
        f" | phase: {e['phase']}"
        f" | topics: {', '.join(e['topics'])}"
        for e in events
    )

    prompt = f"""You are a project analyst for a Canadian government transport safety team.
Below is a chronological log of all project documents and communications for the NOP Risk Score Model Modernization project.
Synthesize this into 8–15 key milestones that tell the story of how the project unfolded.

DOCUMENT LOG:
{events_text}

Return a JSON array of milestone objects. Each object must have exactly these fields:
  "date_range"   — date or date range as a short human-readable string (e.g. "May 11, 2026" or "May 11–18, 2026")
  "title"        — short milestone title, 5–8 words, title case
  "summary"      — 2–3 sentences: what happened and why it matters
  "participants" — array of person name strings involved in this milestone
  "phase"        — one of: initiation | planning | analysis | review | approval | operations
  "docs"         — array of doc_id strings from the log that belong to this milestone

Rules:
- Group closely related events (same week, same topic thread) into one milestone
- Focus on meaningful turning points, decisions, or deliverables — not routine emails
- Write as if briefing a project manager who wants to understand the project arc
- Order chronologically
- Return only raw JSON array. No markdown, no code fences.

RESPONSE:"""

    from config import GEMINI_API_KEY, GENERATION_MODEL_FLASH
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GENERATION_MODEL_FLASH)
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(temperature=0.2),
    )

    text = response.text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        milestones = json.loads(text)
    except json.JSONDecodeError:
        milestones = []

    result = {"milestones": milestones, "generated_at": newest_ts}
    cache_file.write_text(json.dumps(result, indent=2))
    return {**result, "cached": False}


@app.get("/api/team/summary", tags=["Team"])
def team_summary(project_id: str | None = None):
    """LLM-synthesized project role summary per person, cached until new docs are ingested.
    Pass project_id to scope the summary to a specific project's documents."""
    from pathlib import Path
    cache_suffix = f"_{project_id}" if project_id else ""
    cache_file = Path(CACHE_DIR) / f"team_summary{cache_suffix}.json"

    docs = load_enriched_docs() or []
    if not docs:
        return {"members": [], "cached": False}

    # Filter to project docs if project_id provided
    if project_id:
        allowed = _load_project_doc_ids(project_id)
        if allowed is not None:
            docs = [d for d in docs if d["doc_id"] in allowed]
    if not docs:
        return {"members": [], "cached": False}

    newest_ts = max((d.get("parse_timestamp") or "" for d in docs), default="")

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            if cached.get("generated_at", "") >= newest_ts:
                return {**cached, "cached": True}
        except Exception:
            pass

    # Aggregate per-person activity from all docs
    person_stats: dict = {}
    for d in docs:
        if d.get("parse_status") != "success":
            continue
        author  = d.get("author") or ""
        contribs = d.get("contributors") or []
        people  = set(([author] if author else []) + contribs)
        topics  = (d.get("topics") or [])[:4]
        phase   = d.get("project_phase") or ""
        for p in people:
            if not p:
                continue
            if p not in person_stats:
                person_stats[p] = {"authored": 0, "appeared": 0, "topics": set(), "phases": set()}
            person_stats[p]["appeared"] += 1
            if p == author:
                person_stats[p]["authored"] += 1
            person_stats[p]["topics"].update(topics)
            if phase:
                person_stats[p]["phases"].add(phase)

    lines = [
        f"{p}: authored {s['authored']} docs, appeared in {s['appeared']} total, "
        f"phases: {', '.join(sorted(s['phases']))}, "
        f"topics: {', '.join(sorted(s['topics']))[:200]}"
        for p, s in sorted(person_stats.items())
    ]

    prompt = f"""You are summarizing team member contributions to a Canadian government project.

Project: NOP Risk Score Model Modernization — Transport Canada, Transportation of Dangerous Goods branch.
Goal: Modernize the National Oversight Plan risk scoring model used for carrier compliance inspections.

Based on each person's document activity below, write a concise description of their specific role and contributions to this project.

TEAM ACTIVITY:
{chr(10).join(lines)}

Return a JSON array. Each item must have exactly these fields:
  "name"              — the person's name as it appears above
  "project_role"      — 1 concise sentence describing their specific role in this project (not job title)
  "key_contributions" — array of 2–4 short phrases (max 5 words each) describing what they actually did
  "involvement"       — one of: "core" | "supporting" | "external"

Rules:
- "core" = deeply involved across multiple phases; "supporting" = contributed meaningfully in specific areas; "external" = appeared briefly or peripherally
- Write project-specific contributions, not generic job descriptions (e.g. "led SAS model validation" not "provided technical support")
- Return only raw JSON array. No markdown, no code fences.

RESPONSE:"""

    from config import GEMINI_API_KEY, GENERATION_MODEL_FLASH
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GENERATION_MODEL_FLASH)
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(temperature=0.2),
    )

    text = response.text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        members = json.loads(text)
    except json.JSONDecodeError:
        members = []

    result = {"members": members, "generated_at": newest_ts}
    cache_file.write_text(json.dumps(result, indent=2))
    return {**result, "cached": False}


# ── Step 4 endpoints ──────────────────────────────────────────────────────────

@app.post("/api/query/classify", tags=["Step 4 — Retrieve"])
def query_classify(query: str):
    """Classify a query into a type without running retrieval."""
    result = classify(query)
    return {
        "query":      query,
        "query_type": result.query_type,
        "confidence": result.confidence,
        "signals":    result.signals,
        "person_hint": result.person_hint,
    }


@app.post("/api/search/smart", tags=["Step 4 — Retrieve"])
def search_smart(query: str, n: int = 10):
    """
    Classify query then apply the matching retrieval strategy.
    Returns ranked chunks with metadata — no LLM generation.
    """
    stats = get_index_stats()
    if stats.get("status") != "ok":
        raise HTTPException(status_code=503, detail="Index not built — POST /api/index/build first")

    cl = classify(query)
    result = retrieve(query, cl, n=n)
    return result


# ── Step 2.5 endpoints ────────────────────────────────────────────────────────

@app.post("/api/graph/build", tags=["Step 2.5 — Graph"])
def graph_build(gemini_pass: bool = False):
    """
    Build the knowledge graph from enriched_docs.json.
    Add ?gemini_pass=true to run the optional Gemini relationship pass
    (adds APPROVED, OPPOSED, TRIGGERED edges).
    Writes cache/knowledge_graph.json.
    """
    G = run_graph_build(gemini_pass=gemini_pass, verbose=False)
    return {"message": "Graph built", "summary": get_graph_stats(G)}


@app.get("/api/graph/status", tags=["Step 2.5 — Graph"])
def graph_status():
    """Show graph build status — node/edge counts and type breakdowns."""
    return get_graph_build_status()


@app.get("/api/graph/stats", tags=["Step 2.5 — Graph"])
def graph_stats_endpoint():
    """Full graph statistics including top connected documents."""
    G = load_graph()
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not built — POST /api/graph/build first")
    return get_graph_stats(G)


@app.get("/api/graph/person/{person_name}", tags=["Step 2.5 — Graph"])
def graph_person(person_name: str):
    """
    Person profile from the graph: documents authored/contributed, expertise topics,
    approval and opposition records.
    person_name: canonical name e.g. 'Jason Hao', 'Dr. Aris', 'Marc'
    """
    G = load_graph()
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not built — POST /api/graph/build first")
    result = get_person_profile(G, person_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/graph/doc/{doc_id}/chain", tags=["Step 2.5 — Graph"])
def graph_doc_chain(doc_id: str):
    """
    Version lineage and all actors (author, contributors, approvers, opposers)
    for a document. Useful for tracing decision chains.
    """
    G = load_graph()
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not built — POST /api/graph/build first")
    result = find_approval_chain(G, doc_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/graph/d3", tags=["Step 2.5 — Graph"])
def graph_d3(mode: str = "full"):
    """
    Export graph in D3.js force-directed format for frontend visualization.
    mode: full | people | core
      - full   → all 135 nodes, all edge types
      - people → people + documents only (cleaner, good for contributor overview)
      - core   → people + documents, key edges only (AUTHORED, REFERENCES, APPROVED etc.)
    """
    if load_graph() is None:
        raise HTTPException(status_code=503, detail="Graph not built — POST /api/graph/build first")
    if mode not in ("full", "people", "core"):
        raise HTTPException(status_code=400, detail="mode must be: full | people | core")
    return export_graph(mode)


@app.get("/api/graph/org", tags=["Step 2.5 — Graph"])
def graph_org():
    """
    Return the full org chart with hierarchy, titles, bios, and doc stats per person.
    Answers 'who manages who', 'what is X's role', 'who reports to Marc' etc.
    """
    result = get_org_structure()
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return result


@app.get("/api/graph/org/{person_name}", tags=["Step 2.5 — Graph"])
def graph_org_person(person_name: str):
    """
    Return org chart entry for a specific person — title, bio, manages, reports_to, expertise.
    """
    result = get_org_structure()
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    person = result["people"].get(person_name)
    if not person:
        raise HTTPException(status_code=404, detail=f"'{person_name}' not in org chart")
    return person


@app.post("/api/graph/expand", tags=["Step 2.5 — Graph"])
def graph_expand(doc_ids: list[str], hops: int = 1):
    """
    Given a list of doc_ids (e.g. from vector retrieval), expand via graph edges
    to find related documents. Returns additional doc_ids + context nodes.
    This is the Step 4 hybrid retrieval integration point.
    Body: ["doc_id_1", "doc_id_2"]
    """
    G = load_graph()
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not built — POST /api/graph/build first")
    return expand_from_docs(G, doc_ids, hops=hops)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"])
def health():
    from config import GRAPH_PATH
    ingest_status  = get_ingestion_status()
    enrich_status  = get_enrichment_status()
    graph_status   = get_graph_build_status()
    parsed_ok      = (CACHE_DIR / "parsed_docs.json").exists()
    enriched_ok    = (CACHE_DIR / "enriched_docs.json").exists()
    graph_ok       = GRAPH_PATH.exists()
    return {
        "api":             "ok",
        "step1_ingest":    "ok" if parsed_ok  else "not run — POST /api/ingest/run",
        "step2_enrich":    "ok" if enriched_ok else "not run — POST /api/enrich/run",
        "step2_5_graph":   "ok" if graph_ok   else "not run — POST /api/graph/build",
        "step3_index":     "ok" if get_index_stats().get("status") == "ok" else "not run — POST /api/index/build",
        "docs_parsed":     ingest_status.get("total", 0),
        "docs_enriched":   enrich_status.get("done", 0),
        "graph_nodes":     graph_status.get("total_nodes", 0),
        "graph_edges":     graph_status.get("total_edges", 0),
    }


@app.get("/", tags=["System"])
def root():
    return {
        "message": "Team Intelligence API",
        "docs":    "http://localhost:8000/docs",
        "steps_available": [
            "Step 1   — POST /api/ingest/run",
            "Step 1   — GET  /api/ingest/status",
            "Step 1   — GET  /api/docs",
            "Step 1   — GET  /api/docs/{doc_id}",
            "Step 2   — POST /api/enrich/run",
            "Step 2   — GET  /api/enrich/status",
            "Step 2   — GET  /api/docs/{doc_id}/meta",
            "Step 2   — GET  /api/stats/topics",
            "Step 2   — GET  /api/stats/phases",
            "Step 2   — GET  /api/stats/references",
            "Step 3   — POST /api/index/build",
            "Step 3   — GET  /api/index/stats",
            "Step 3   — POST /api/search/raw",
            "Step 2.5 — POST /api/graph/build",
            "Step 2.5 — GET  /api/graph/status",
            "Step 2.5 — GET  /api/graph/stats",
            "Step 2.5 — GET  /api/graph/person/{person_name}",
            "Step 2.5 — GET  /api/graph/doc/{doc_id}/chain",
            "Step 2.5 — POST /api/graph/expand",
            "GET  /api/health",
        ],
    }
