"""
Step 4b — Smart Retrieval

Applies query-type-specific retrieval strategies using ChromaDB + knowledge graph.
Each strategy returns a ranked list of chunks with full metadata.

Strategies:
  causal_trace        → vector search + sort by event_date + graph thread expansion
  contributor_profile → filter by author/contributor + vector search within subset
  conflict_detect     → two-pass: supporting + opposing retrieval, merged
  audit_chain         → vector search + 2-hop reference graph walk
  onboarding          → filter early phases + approved docs + vector search
  general             → standard top-k vector search
"""

import json
from collections import defaultdict

import google.generativeai as genai

from config import GEMINI_API_KEY, EMBEDDING_MODEL, TOP_K, CHROMA_COLLECTION, CHROMA_DIR
from router import ClassificationResult
from graph_builder import load_graph, expand_from_docs, get_org_structure, MANAGES, REPORTS_TO

import chromadb

genai.configure(api_key=GEMINI_API_KEY)

# ── ChromaDB helpers ──────────────────────────────────────────────────────────

def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(CHROMA_COLLECTION)


def _embed_query(query: str) -> list[float]:
    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=query,
        task_type="RETRIEVAL_QUERY",
    )
    return result["embedding"]


def _query_collection(
    embedding: list[float],
    n: int,
    where: dict | None = None,
) -> list[dict]:
    """Raw ChromaDB query → list of hit dicts."""
    collection = _get_collection()
    total = collection.count()
    if total == 0:
        return []

    kwargs = {
        "query_embeddings": [embedding],
        "n_results":        min(n, total),
        "include":          ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    res = collection.query(**kwargs)

    hits = []
    for cid, doc, meta, dist in zip(
        res["ids"][0], res["documents"][0],
        res["metadatas"][0], res["distances"][0],
    ):
        hits.append({
            "chunk_id":      cid,
            "score":         round(1 - dist, 4),
            "text":          doc,
            "doc_id":        meta.get("doc_id", ""),
            "file_type":     meta.get("file_type", ""),
            "author":        meta.get("author", ""),
            "contributors":  meta.get("contributors", "[]"),
            "event_date":    meta.get("event_date", ""),
            "project_phase": meta.get("project_phase", ""),
            "topics":        meta.get("topics", "[]"),
            "references_docs": meta.get("references_docs", "[]"),
            "chunk_index":   meta.get("chunk_index", 0),
            "chunk_total":   meta.get("chunk_total", 1),
            "thread_id":     meta.get("thread_id", ""),
        })
    return hits


def _fetch_chunks_by_doc_ids(doc_ids: list[str], limit_per_doc: int = 2) -> list[dict]:
    """Fetch the top chunk(s) for specific doc_ids (for graph expansion)."""
    collection = _get_collection()
    if not doc_ids:
        return []

    results = collection.get(
        where={"doc_id": {"$in": doc_ids}},
        include=["documents", "metadatas"],
        limit=limit_per_doc * len(doc_ids),
    )

    hits = []
    for cid, doc, meta in zip(
        results["ids"], results["documents"], results["metadatas"]
    ):
        hits.append({
            "chunk_id":      cid,
            "score":         0.0,   # no similarity score for graph-fetched chunks
            "text":          doc,
            "doc_id":        meta.get("doc_id", ""),
            "file_type":     meta.get("file_type", ""),
            "author":        meta.get("author", ""),
            "contributors":  meta.get("contributors", "[]"),
            "event_date":    meta.get("event_date", ""),
            "project_phase": meta.get("project_phase", ""),
            "topics":        meta.get("topics", "[]"),
            "references_docs": meta.get("references_docs", "[]"),
            "chunk_index":   meta.get("chunk_index", 0),
            "chunk_total":   meta.get("chunk_total", 1),
            "thread_id":     meta.get("thread_id", ""),
            "retrieval_method": "graph_expansion",
        })
    return hits


def _dedupe_and_rank(hits: list[dict], max_per_doc: int = 2) -> list[dict]:
    """
    Remove duplicate chunks from the same doc, keep highest-scoring chunk
    per doc, enforce max_per_doc, sort by score descending.
    """
    best: dict[str, dict] = {}
    for h in hits:
        doc_id = h["doc_id"]
        if doc_id not in best or h["score"] > best[doc_id]["score"]:
            best[doc_id] = h

    return sorted(best.values(), key=lambda x: -x["score"])


# ── Project filter helper ─────────────────────────────────────────────────────

def _with_project(where: dict | None, project_id: str | None) -> dict | None:
    """Merge an existing where clause with a project_id filter for ChromaDB."""
    if not project_id:
        return where
    pid_filter: dict = {"project_id": project_id}
    if not where:
        return pid_filter
    return {"$and": [pid_filter, where]}


# ── Strategy implementations ──────────────────────────────────────────────────

def retrieve_causal_trace(query: str, n: int, project_id: str | None = None) -> list[dict]:
    """
    Vector search → sort by event_date → expand graph thread.
    Causal questions need temporal ordering and thread context.
    """
    emb = _embed_query(query)
    hits = _query_collection(emb, n=n * 2, where=_with_project(None, project_id))

    # Sort primary hits by date (oldest first for causal chain)
    dated = [h for h in hits if h["event_date"]]
    undated = [h for h in hits if not h["event_date"]]
    dated.sort(key=lambda h: h["event_date"])
    hits = dated + undated

    # Graph expansion: pull related docs via REFERENCES + TRIGGERED edges
    G = load_graph()
    if G:
        seed_ids = list({h["doc_id"] for h in hits[:6]})
        expanded = expand_from_docs(
            G, seed_ids, hops=1,
            rel_types=["REFERENCES", "TRIGGERED", "SUPERSEDES"]
        )
        if expanded["expanded_doc_ids"]:
            extra = _fetch_chunks_by_doc_ids(expanded["expanded_doc_ids"], limit_per_doc=1)
            for e in extra:
                e["retrieval_method"] = "graph_causal"
            hits = hits + extra

    hits = _dedupe_and_rank(hits, max_per_doc=2)
    return hits[:n]


def retrieve_contributor_profile(query: str, n: int, person: str | None, project_id: str | None = None) -> list[dict]:
    """
    Filter by contributor name first, then vector search within that subset.
    Person-specific: prioritise docs they authored.
    """
    emb = _embed_query(query)

    authored_hits: list[dict] = []
    contributed_hits: list[dict] = []

    if person:
        # 1. Docs authored by this person
        try:
            authored_hits = _query_collection(
                emb, n=n, where=_with_project({"author": person}, project_id)
            )
            for h in authored_hits:
                h["retrieval_method"] = "authored"
        except Exception:
            pass

        # 2. Docs they contributed to (contributors is a JSON string)
        # ChromaDB doesn't support JSON list contains — do post-filter
        all_hits = _query_collection(emb, n=n * 3, where=_with_project(None, project_id))
        for h in all_hits:
            try:
                contribs = json.loads(h.get("contributors", "[]"))
            except Exception:
                contribs = []
            if person in contribs and h["doc_id"] not in {a["doc_id"] for a in authored_hits}:
                h["retrieval_method"] = "contributed"
                contributed_hits.append(h)

    # 3. Fallback: general search if nothing found
    if not authored_hits and not contributed_hits:
        fallback = _query_collection(emb, n=n, where=_with_project(None, project_id))
        for h in fallback:
            h["retrieval_method"] = "vector_fallback"
        return _dedupe_and_rank(fallback, max_per_doc=2)[:n]

    # Authored chunks rank highest, then contributed
    combined = authored_hits + contributed_hits
    return _dedupe_and_rank(combined, max_per_doc=2)[:n]


def retrieve_conflict_detect(query: str, n: int, project_id: str | None = None) -> list[dict]:
    """
    Two-pass retrieval: find supporting AND opposing content.
    Returns chunks labelled with their retrieval pass.
    """
    emb = _embed_query(query)

    # Pass 1: direct semantic search
    pass1 = _query_collection(emb, n=n * 2, where=_with_project(None, project_id))
    for h in pass1:
        h["retrieval_method"] = "primary"

    # Pass 2: specifically target known conflict pairs
    # (versioned docs, early vs late phases, draft vs approved)
    conflict_targets = []

    # Retrieve draft/v1 docs
    try:
        drafts = _query_collection(emb, n=6, where=_with_project({"approval_status": "draft"}, project_id))
        for h in drafts:
            h["retrieval_method"] = "conflict_draft"
        conflict_targets.extend(drafts)
    except Exception:
        pass

    # Retrieve approved/v2 docs
    try:
        approved = _query_collection(emb, n=6, where=_with_project({"approval_status": "approved"}, project_id))
        for h in approved:
            h["retrieval_method"] = "conflict_approved"
        conflict_targets.extend(approved)
    except Exception:
        pass

    combined = pass1 + conflict_targets
    return _dedupe_and_rank(combined, max_per_doc=2)[:n]


def retrieve_audit_chain(query: str, n: int, project_id: str | None = None) -> list[dict]:
    """
    Vector search + 2-hop reference graph walk.
    Audit questions need the full provenance chain.
    """
    emb = _embed_query(query)

    # Primary: bias toward policy, audit, and work docs
    hits = []
    for ft in ["policy_doc", "word_doc", "meeting_minutes", "sas_script"]:
        try:
            ft_hits = _query_collection(emb, n=4, where=_with_project({"file_type": ft}, project_id))
            for h in ft_hits:
                h["retrieval_method"] = f"audit_{ft}"
            hits.extend(ft_hits)
        except Exception:
            pass

    if not hits:
        hits = _query_collection(emb, n=n * 2, where=_with_project(None, project_id))

    # Graph walk: follow references 2 hops
    G = load_graph()
    if G:
        seed_ids = list({h["doc_id"] for h in hits[:5]})
        expanded = expand_from_docs(
            G, seed_ids, hops=2,
            rel_types=["REFERENCES", "TRIGGERED", "SUPERSEDES"]
        )
        if expanded["expanded_doc_ids"]:
            extra = _fetch_chunks_by_doc_ids(expanded["expanded_doc_ids"], limit_per_doc=1)
            for e in extra:
                e["retrieval_method"] = "audit_graph"
            hits = hits + extra

    return _dedupe_and_rank(hits, max_per_doc=2)[:n]


def retrieve_onboarding(query: str, n: int, project_id: str | None = None) -> list[dict]:
    """
    Filter early phases (initiation, planning, development) + approved docs.
    Onboarding needs the foundational documents in logical order.
    """
    emb = _embed_query(query)
    hits = []

    # Target the key phases a new person should read
    for phase in ["initiation", "planning", "development", "approval"]:
        try:
            phase_hits = _query_collection(emb, n=4, where=_with_project({"project_phase": phase}, project_id))
            for h in phase_hits:
                h["retrieval_method"] = f"onboard_{phase}"
            hits.extend(phase_hits)
        except Exception:
            pass

    # Also pull the final/approved methodology docs
    try:
        approved = _query_collection(emb, n=4, where=_with_project({"approval_status": "approved"}, project_id))
        for h in approved:
            h["retrieval_method"] = "onboard_approved"
        hits.extend(approved)
    except Exception:
        pass

    if not hits:
        hits = _query_collection(emb, n=n * 2, where=_with_project(None, project_id))

    # Sort by phase order for logical reading sequence
    PHASE_ORDER = {
        "initiation": 0, "planning": 1, "development": 2,
        "review": 3, "approval": 4, "implementation": 5,
        "audit": 6, "operations": 7, "closeout": 8, "": 9,
    }
    deduped = _dedupe_and_rank(hits, max_per_doc=1)
    deduped.sort(key=lambda h: PHASE_ORDER.get(h["project_phase"], 9))
    return deduped[:n]


def retrieve_org_lookup(query: str, person: str | None) -> dict:
    """
    Three-tier org lookup — no vector search, no API calls.

    Tier 1 — Person named in query → return their full profile
    Tier 2 — Team keyword detected → return matching team + members
    Tier 3 — Skill/topic keyword → match against person skills arrays
    Fallback → return full org structure
    """
    org = get_org_structure()
    if "error" in org:
        return {"org_answer": None, "org_data": {}, "query_mode": "error"}

    q = query.lower()

    # ── Tier 1: specific person named ────────────────────────────────────────
    if person and person in org["people"]:
        return {
            "org_answer": org["people"][person],
            "org_data":   org,
            "query_mode": "person_lookup",
        }

    # ── Tier 2: team keyword ──────────────────────────────────────────────────
    team_keywords = {
        "data_technical": ["data team", "data sub", "technical team", "data management", "database team"],
        "nop_project":    ["nop team", "project team", "whole team", "full team", "nop project"],
    }
    for team_id, keywords in team_keywords.items():
        if any(kw in q for kw in keywords):
            team = org["teams"].get(team_id)
            if team:
                # Attach member profiles
                members_detail = {
                    m: org["people"][m]
                    for m in team["members"]
                    if m in org["people"]
                }
                return {
                    "org_answer": {**team, "members_detail": members_detail},
                    "org_data":   org,
                    "query_mode": "team_lookup",
                }

    # ── Tier 3: skill/topic keyword matching ──────────────────────────────────
    from enricher import TOPIC_VOCABULARY
    matched_people = []
    for topic in TOPIC_VOCABULARY:
        # Convert topic tag to readable keywords (e.g. sas_implementation → sas)
        keywords = topic.replace("_", " ").split()
        if any(kw in q for kw in keywords):
            for name, pdata in org["people"].items():
                if topic in pdata.get("skills", []) and name not in matched_people:
                    matched_people.append(name)

    # Also match against scope text directly
    if not matched_people:
        q_words = set(q.split())
        for name, pdata in org["people"].items():
            scope_words = set(pdata.get("scope", "").lower().split())
            # Need at least 2 meaningful word overlaps
            overlap = q_words & scope_words - {"the", "a", "an", "is", "in", "of", "and", "for", "to", "what"}
            if len(overlap) >= 2:
                matched_people.append(name)

    if matched_people:
        return {
            "org_answer": {
                "matched_people": {
                    name: org["people"][name]
                    for name in matched_people
                    if name in org["people"]
                }
            },
            "org_data":   org,
            "query_mode": "skill_match",
        }

    # ── Fallback: full org ────────────────────────────────────────────────────
    return {
        "org_answer": None,
        "org_data":   org,
        "query_mode": "full_org",
    }


def retrieve_general(query: str, n: int, project_id: str | None = None) -> list[dict]:
    """Standard top-k similarity search."""
    emb = _embed_query(query)
    hits = _query_collection(emb, n=n * 2, where=_with_project(None, project_id))
    return _dedupe_and_rank(hits, max_per_doc=2)[:n]


# ── Main retrieval dispatcher ─────────────────────────────────────────────────

def retrieve(query: str, classification: ClassificationResult, n: int = TOP_K, project_id: str | None = None) -> dict:
    """
    Route to the correct strategy based on classification result.
    Returns: { query_type, chunks, retrieval_meta }
    project_id: when set, scopes all ChromaDB queries to that project's chunks only.
    """
    qt = classification.query_type

    if qt == "org_lookup":
        org_result = retrieve_org_lookup(query, classification.person_hint)
        return {
            "query_type":        "org_lookup",
            "confidence":        classification.confidence,
            "person_hint":       classification.person_hint,
            "total_chunks":      0,
            "source_mix":        {},
            "retrieval_methods": {"org_graph": 1},
            "chunks":            [],
            "org":               org_result,
        }

    if qt == "causal_trace":
        chunks = retrieve_causal_trace(query, n, project_id=project_id)
    elif qt == "contributor_profile":
        chunks = retrieve_contributor_profile(query, n, classification.person_hint, project_id=project_id)
    elif qt == "conflict_detect":
        chunks = retrieve_conflict_detect(query, n, project_id=project_id)
    elif qt == "audit_chain":
        chunks = retrieve_audit_chain(query, n, project_id=project_id)
    elif qt == "onboarding":
        chunks = retrieve_onboarding(query, n, project_id=project_id)
    else:
        chunks = retrieve_general(query, n, project_id=project_id)

    # Summary for debugging / API response
    from collections import Counter
    source_types = Counter(c["file_type"] for c in chunks)
    methods      = Counter(c.get("retrieval_method", "vector") for c in chunks)

    return {
        "query_type":     qt,
        "confidence":     classification.confidence,
        "person_hint":    classification.person_hint,
        "total_chunks":   len(chunks),
        "source_mix":     dict(source_types),
        "retrieval_methods": dict(methods),
        "chunks":         chunks,
    }


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from router import classify

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
        "Why was the geographic weight changed from 5% to 15%?"

    print(f"Query: {query}\n")
    cl = classify(query)
    print(f"Type: {cl.query_type} ({cl.confidence})")
    if cl.person_hint:
        print(f"Person: {cl.person_hint}")
    print()

    result = retrieve(query, cl, n=8)

    print(f"Retrieved {result['total_chunks']} chunks")
    print(f"Source mix: {result['source_mix']}")
    print(f"Methods:    {result['retrieval_methods']}")
    print()

    for i, c in enumerate(result["chunks"], 1):
        method = c.get("retrieval_method", "vector")
        print(f"[{i}] score={c['score']:.3f} | {c['doc_id']:45s} | "
              f"{c['file_type']:18s} | {c['event_date']:12s} | {method}")
        print(f"     {c['text'][:120].strip()}...")
        print()
