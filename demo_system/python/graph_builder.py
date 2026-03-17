"""
Step 2.5 — Knowledge Graph Construction

Builds a typed, directed multigraph from cache/enriched_docs.json.
Writes cache/knowledge_graph.json.

Node types:
  document   doc:{doc_id}
  person     person:{canonical_name}
  topic      topic:{tag}
  phase      phase:{phase_name}

Edge types (rule-based, no LLM):
  AUTHORED        person  → document
  CONTRIBUTED_TO  person  → document
  REFERENCES      document → document
  TAGGED_WITH     document → topic
  IN_PHASE        document → phase
  SUPERSEDES      document → document  (older → newer, inferred from version)
  EXPERT_IN       person  → topic      (authored 2+ docs with that topic)

Edge types (optional Gemini pass):
  APPROVED        person  → document
  OPPOSED         person  → document
  TRIGGERED       document → document

Edge types (org chart):
  MANAGES         person  → person
  REPORTS_TO      person  → person

Resume-safe: run with --no-gemini to skip the Gemini pass.
"""

import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import google.generativeai as genai

from config import CACHE_DIR, GEMINI_API_KEY, GENERATION_MODEL_FLASH, GRAPH_PATH
from enricher import load_enriched_docs, SYSTEM_CONTEXT, LINKABLE_DOCS
from metadata_rules import CANONICAL_NAMES

ORG_CHART_PATH = GRAPH_PATH.parent.parent.parent.parent / "org_chart.json"  # /Team intelligence/org_chart.json

genai.configure(api_key=GEMINI_API_KEY)

# ── Edge type constants ───────────────────────────────────────────────────────

AUTHORED       = "AUTHORED"
CONTRIBUTED_TO = "CONTRIBUTED_TO"
REFERENCES     = "REFERENCES"
TAGGED_WITH    = "TAGGED_WITH"
IN_PHASE       = "IN_PHASE"
SUPERSEDES     = "SUPERSEDES"
EXPERT_IN      = "EXPERT_IN"
APPROVED       = "APPROVED"
OPPOSED        = "OPPOSED"
TRIGGERED      = "TRIGGERED"
MANAGES        = "MANAGES"
REPORTS_TO     = "REPORTS_TO"
MEMBER_OF      = "MEMBER_OF"
LEADS          = "LEADS"

KNOWN_PEOPLE = set(CANONICAL_NAMES.values())  # canonical names only

# ── Node ID helpers ───────────────────────────────────────────────────────────

def _doc(doc_id: str)    -> str: return f"doc:{doc_id}"
def _person(name: str)   -> str: return f"person:{name}"
def _topic(tag: str)     -> str: return f"topic:{tag}"
def _phase(phase: str)   -> str: return f"phase:{phase}"
def _team(team_id: str)  -> str: return f"team:{team_id}"


# ── Phase 1: build graph from metadata (no LLM) ──────────────────────────────

def build_graph_from_docs(docs: list[dict], verbose: bool = True) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()

    # ── Pass 1: add all nodes ─────────────────────────────────────────────────
    all_people: set[str] = set()
    all_topics: set[str] = set()
    all_phases: set[str] = set()

    for doc in docs:
        G.add_node(
            _doc(doc["doc_id"]),
            node_type="document",
            label=doc["doc_id"],
            file_type=doc.get("file_type", ""),
            source_folder=doc.get("source_folder", ""),
            event_date=doc.get("event_date") or "",
            document_version=doc.get("document_version") or "",
            approval_status=doc.get("approval_status", "unknown"),
            project_phase=doc.get("project_phase") or "",
        )
        if doc.get("author"):
            all_people.add(doc["author"])
        all_people.update(doc.get("contributors", []))
        all_topics.update(doc.get("topics", []))
        if doc.get("project_phase"):
            all_phases.add(doc["project_phase"])

    for name in all_people:
        G.add_node(_person(name), node_type="person", label=name)
    for tag in all_topics:
        G.add_node(_topic(tag), node_type="topic", label=tag)
    for phase in all_phases:
        G.add_node(_phase(phase), node_type="phase", label=phase)

    if verbose:
        print(f"  Nodes added: {G.number_of_nodes()} "
              f"({len(docs)} docs, {len(all_people)} people, "
              f"{len(all_topics)} topics, {len(all_phases)} phases)")

    # ── Pass 2: structural edges ──────────────────────────────────────────────
    author_topic_count: dict[str, Counter] = defaultdict(Counter)

    for doc in docs:
        dn = _doc(doc["doc_id"])
        author = doc.get("author")

        # AUTHORED
        if author:
            G.add_edge(_person(author), dn, rel=AUTHORED, source="rule")
            for tag in doc.get("topics", []):
                author_topic_count[author][tag] += 1

        # CONTRIBUTED_TO (skip if same as author)
        for contrib in doc.get("contributors", []):
            if contrib != author:
                G.add_edge(_person(contrib), dn, rel=CONTRIBUTED_TO, source="rule")

        # REFERENCES  (guard: target must exist in graph)
        for ref in doc.get("references_docs", []):
            rn = _doc(ref)
            if rn in G and rn != dn:
                G.add_edge(dn, rn, rel=REFERENCES, source="rule")

        # TAGGED_WITH
        for tag in doc.get("topics", []):
            G.add_edge(dn, _topic(tag), rel=TAGGED_WITH, source="rule")

        # IN_PHASE
        if doc.get("project_phase"):
            G.add_edge(dn, _phase(doc["project_phase"]), rel=IN_PHASE, source="rule")

    # ── Pass 3: EXPERT_IN  (person → topic, authored ≥ 2 docs with that topic) ─
    for person, topic_counts in author_topic_count.items():
        for tag, count in topic_counts.items():
            if count >= 2:
                G.add_edge(_person(person), _topic(tag),
                           rel=EXPERT_IN, doc_count=count, source="rule")

    # ── Pass 4: SUPERSEDES  (infer from version patterns in doc_id) ──────────
    VERSION_RE = re.compile(
        r'_(v\d+(?:_\d+)?|draft|final)$', re.IGNORECASE
    )

    families: dict[str, list[dict]] = defaultdict(list)
    for doc in docs:
        base = VERSION_RE.sub("", doc["doc_id"].lower())
        # MSG-012-V1 / MSG-012 special case
        base = re.sub(r'-(v\d+)$', '', base, flags=re.IGNORECASE)
        families[base].append(doc)

    def _version_sort_key(doc: dict) -> tuple:
        v = (doc.get("document_version") or "").lower()
        if re.match(r'v(\d+)', v):
            return (int(re.match(r'v(\d+)', v).group(1)), 0)
        if "final" in v:
            return (99, 1)
        if "draft" in v:
            return (0, 0)
        date = doc.get("event_date") or "0000-00-00"
        return (50, date)  # middle ground for unknown versions

    supersedes_added = 0
    for base, group in families.items():
        if len(group) < 2:
            continue
        sorted_group = sorted(group, key=_version_sort_key)
        for i in range(len(sorted_group) - 1):
            older = _doc(sorted_group[i]["doc_id"])
            newer = _doc(sorted_group[i + 1]["doc_id"])
            if older != newer:
                G.add_edge(older, newer, rel=SUPERSEDES, source="rule")
                supersedes_added += 1

    if verbose:
        e_breakdown = Counter(d["rel"] for _, _, d in G.edges(data=True))
        print(f"  Edges added (rule-based): {G.number_of_edges()}")
        for rel, cnt in sorted(e_breakdown.items()):
            print(f"    {rel:20s}: {cnt}")

    return G


# ── Phase 2: Gemini relationship extraction ───────────────────────────────────

def _gemini_rel_prompt(doc: dict) -> str:
    content   = doc.get("raw_text", "")[:4000]
    doc_id    = doc["doc_id"]
    contribs  = doc.get("contributors", [])
    known_str = ", ".join(sorted(KNOWN_PEOPLE))
    links_str = "\n".join(f"  - {d}" for d in LINKABLE_DOCS)

    return f"""
{SYSTEM_CONTEXT}

---
DOCUMENT: {doc_id}
CONTRIBUTORS: {', '.join(contribs)}

CONTENT:
{content}
---

TASK: Identify EXPLICIT relationship events in this document.
Return ONLY valid JSON — no markdown, no explanation.

OUTPUT FORMAT:
{{
  "approved":    [{{"person": "Name", "description": "what they approved"}}],
  "opposed":     [{{"person": "Name", "description": "what they opposed"}}],
  "triggered_by":[{{"doc_id": "linkable_doc_id", "reason": "brief reason"}}]
}}

Rules:
- approved / opposed: person must be one of: {known_str}
- triggered_by: doc_id must be one of the LINKABLE DOCS listed below
- Only include HIGH-CONFIDENCE relationships explicitly stated in the text
- Return empty arrays if nothing applies — do NOT invent relationships

LINKABLE DOCS:
{links_str}
""".strip()


def enrich_graph_with_gemini(
    G: nx.MultiDiGraph, docs: list[dict], verbose: bool = True
) -> nx.MultiDiGraph:
    """Add APPROVED, OPPOSED, TRIGGERED edges via Gemini (optional pass)."""

    # Only process docs with contributors where decisions are plausible
    candidates = [
        d for d in docs
        if d.get("contributors")
        and d.get("project_phase") in (
            "approval", "review", "initiation", "audit", "closeout"
        )
    ]

    # Resume-safe: skip docs that already have Gemini edges pointing to them
    already_enriched = {
        v.replace("doc:", "")
        for _, v, d in G.edges(data=True)
        if d.get("source") == "gemini" and v.startswith("doc:")
    }
    candidates = [d for d in candidates if d["doc_id"] not in already_enriched]

    if not candidates:
        if verbose:
            print("  All candidates already Gemini-enriched. Nothing to do.")
        return G

    model = genai.GenerativeModel(GENERATION_MODEL_FLASH)

    if verbose:
        print(f"\nGemini relationship pass: {len(candidates)} candidates\n")

    for i, doc in enumerate(candidates, 1):
        dn = _doc(doc["doc_id"])
        if verbose:
            print(f"[{i:3}/{len(candidates)}] {doc['doc_id'][:55]:55s}", end=" ", flush=True)

        prompt = _gemini_rel_prompt(doc)
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            result = json.loads(response.text.strip())
            if not isinstance(result, dict):
                if verbose: print("✗ bad format")
                time.sleep(0.5)
                continue
        except Exception as e:
            if verbose: print(f"✗ {e}")
            time.sleep(0.5)
            continue

        added = 0

        for item in result.get("approved", []):
            person = (item.get("person") or "").strip()
            if person in KNOWN_PEOPLE:
                G.add_edge(_person(person), dn,
                           rel=APPROVED, source="gemini",
                           description=item.get("description", ""))
                added += 1

        for item in result.get("opposed", []):
            person = (item.get("person") or "").strip()
            if person in KNOWN_PEOPLE:
                G.add_edge(_person(person), dn,
                           rel=OPPOSED, source="gemini",
                           description=item.get("description", ""))
                added += 1

        for item in result.get("triggered_by", []):
            from_doc = (item.get("doc_id") or "").strip()
            fn = _doc(from_doc)
            if from_doc in LINKABLE_DOCS and fn in G and fn != dn:
                G.add_edge(fn, dn,
                           rel=TRIGGERED, source="gemini",
                           reason=item.get("reason", ""))
                added += 1

        if verbose:
            print(f"✓ +{added} edges")

        time.sleep(0.5)

    return G


# ── Persistence ───────────────────────────────────────────────────────────────

def save_graph(G: nx.MultiDiGraph) -> Path:
    data = nx.node_link_data(G, edges="edges")
    with open(GRAPH_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return GRAPH_PATH


def load_graph() -> nx.MultiDiGraph | None:
    if not GRAPH_PATH.exists():
        return None
    with open(GRAPH_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return nx.node_link_graph(data, directed=True, multigraph=True, edges="edges")


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_person_profile(G: nx.MultiDiGraph, name: str) -> dict:
    """All docs a person authored, contributed to, approved, or opposed + expertise."""
    node = _person(name)
    if node not in G:
        return {"error": f"Person '{name}' not in graph"}

    profile: dict = {
        "person": name,
        "authored": [], "contributed_to": [], "approved": [],
        "opposed": [], "expert_in": [],
    }

    for _, target, data in G.out_edges(node, data=True):
        rel = data.get("rel")
        if rel == AUTHORED:
            profile["authored"].append(target.replace("doc:", ""))
        elif rel == CONTRIBUTED_TO:
            profile["contributed_to"].append(target.replace("doc:", ""))
        elif rel == APPROVED:
            profile["approved"].append(target.replace("doc:", ""))
        elif rel == OPPOSED:
            profile["opposed"].append(target.replace("doc:", ""))
        elif rel == EXPERT_IN:
            profile["expert_in"].append({
                "topic": target.replace("topic:", ""),
                "doc_count": data.get("doc_count", 0),
            })

    profile["expert_in"].sort(key=lambda x: -x["doc_count"])
    profile["doc_count"] = len(set(profile["authored"] + profile["contributed_to"]))
    return profile


def expand_from_docs(
    G: nx.MultiDiGraph,
    doc_ids: list[str],
    hops: int = 1,
    rel_types: list[str] | None = None,
) -> dict:
    """
    Given doc_ids (e.g. from vector retrieval), expand via graph edges.
    Returns additional related doc_ids and context (people/topics/phases touched).
    Used in Step 4 for hybrid vector+graph retrieval.
    """
    if rel_types is None:
        rel_types = [REFERENCES, TRIGGERED, SUPERSEDES]

    seed_nodes = {_doc(d) for d in doc_ids if _doc(d) in G}
    visited    = set(seed_nodes)
    frontier   = set(seed_nodes)

    for _ in range(hops):
        next_frontier: set[str] = set()
        for node in frontier:
            for _, tgt, data in G.out_edges(node, data=True):
                if data.get("rel") in rel_types and tgt not in visited:
                    next_frontier.add(tgt)
            for src, _, data in G.in_edges(node, data=True):
                if data.get("rel") in rel_types and src not in visited:
                    next_frontier.add(src)
        visited   |= next_frontier
        frontier   = next_frontier

    expanded_docs = [
        n.replace("doc:", "") for n in visited
        if G.nodes[n].get("node_type") == "document" and n not in seed_nodes
    ]
    context = {
        "persons": [n.replace("person:", "") for n in visited
                    if G.nodes[n].get("node_type") == "person"],
        "topics":  [n.replace("topic:", "")  for n in visited
                    if G.nodes[n].get("node_type") == "topic"],
        "phases":  [n.replace("phase:", "")  for n in visited
                    if G.nodes[n].get("node_type") == "phase"],
    }
    return {"expanded_doc_ids": expanded_docs, "context": context}


def find_approval_chain(G: nx.MultiDiGraph, doc_id: str) -> dict:
    """Trace SUPERSEDES lineage + collect all actors (author, approver, opposer)."""
    dn = _doc(doc_id)
    if dn not in G:
        return {"error": f"doc_id '{doc_id}' not in graph"}

    # Walk SUPERSEDES chain backwards (find predecessors = older versions)
    version_chain = []
    current = dn
    visited_chain: set[str] = {current}
    for _ in range(10):
        prev_nodes = [
            src for src, _, d in G.in_edges(current, data=True)
            if d.get("rel") == SUPERSEDES and src not in visited_chain
        ]
        if not prev_nodes:
            break
        prev = prev_nodes[0]
        version_chain.append(prev.replace("doc:", ""))
        visited_chain.add(prev)
        current = prev

    # Collect all actors on the target document
    actors = []
    seen_actor_pairs: set[tuple] = set()
    for src, _, data in G.in_edges(dn, data=True):
        rel = data.get("rel")
        if rel in (AUTHORED, CONTRIBUTED_TO, APPROVED, OPPOSED):
            pair = (src, rel)
            if pair not in seen_actor_pairs:
                actors.append({
                    "person":      src.replace("person:", ""),
                    "role":        rel,
                    "confidence":  data.get("source", "rule"),
                    "description": data.get("description", ""),
                })
                seen_actor_pairs.add(pair)

    return {
        "doc_id":          doc_id,
        "approval_status": G.nodes[dn].get("approval_status"),
        "project_phase":   G.nodes[dn].get("project_phase"),
        "version_chain":   list(reversed(version_chain)),  # oldest → current
        "actors":          actors,
    }


def get_graph_stats(G: nx.MultiDiGraph) -> dict:
    node_types = Counter(d.get("node_type", "?") for _, d in G.nodes(data=True))
    edge_types = Counter(d.get("rel", "?")      for _, _, d in G.edges(data=True))

    doc_nodes  = [n for n, d in G.nodes(data=True) if d.get("node_type") == "document"]
    top_docs   = sorted(
        [(n.replace("doc:", ""), G.degree(n)) for n in doc_nodes],
        key=lambda x: -x[1]
    )[:10]

    return {
        "total_nodes":      G.number_of_nodes(),
        "total_edges":      G.number_of_edges(),
        "nodes_by_type":    dict(node_types),
        "edges_by_type":    dict(edge_types),
        "top_connected_docs": top_docs,
        "has_gemini_edges": any(
            d.get("source") == "gemini" for _, _, d in G.edges(data=True)
        ),
    }


# ── Org chart loader ──────────────────────────────────────────────────────────

def load_org_chart() -> dict | None:
    if not ORG_CHART_PATH.exists():
        return None
    with open(ORG_CHART_PATH, encoding="utf-8") as f:
        return json.load(f)


def enrich_graph_with_org(G: nx.MultiDiGraph, verbose: bool = True) -> nx.MultiDiGraph:
    """
    Read org_chart.json and:
    1. Add team nodes with goal/description attributes
    2. Enrich person nodes with title, scope, bio, skills, contact, team
    3. Add MANAGES, REPORTS_TO, MEMBER_OF, LEADS edges
    """
    org = load_org_chart()
    if not org:
        if verbose:
            print("  org_chart.json not found — skipping org enrichment")
        return G

    added_edges = 0
    enriched_nodes = 0

    # ── Add team nodes ────────────────────────────────────────────────────────
    for team in org.get("teams", []):
        tid = _team(team["id"])
        G.add_node(
            tid,
            node_type  = "team",
            label      = team["name"],
            team_id    = team["id"],
            goal       = team.get("goal", ""),
            description= team.get("description", ""),
            lead       = team.get("lead", ""),
        )
        # LEADS edge: team lead → team
        lead_node = _person(team["lead"])
        if lead_node in G:
            G.add_edge(lead_node, tid, rel=LEADS, source="org_chart")
            added_edges += 1

        # MEMBER_OF edges: member → team
        for member in team.get("members", []):
            mnode = _person(member)
            if mnode not in G:
                G.add_node(mnode, node_type="person", label=member)
            G.add_edge(mnode, tid, rel=MEMBER_OF, source="org_chart")
            added_edges += 1

    # ── Enrich person nodes ───────────────────────────────────────────────────
    for person in org.get("people", []):
        canonical = person["canonical"]
        node_id   = _person(canonical)

        if node_id not in G:
            G.add_node(node_id, node_type="person", label=canonical)

        G.nodes[node_id].update({
            "title":           person.get("title", ""),
            "employment_type": person.get("employment_type", "staff"),
            "scope":           person.get("scope", ""),
            "bio":             person.get("bio", ""),
            "skills":          json.dumps(person.get("skills", [])),
            "contact":         person.get("contact", ""),
            "team":            person.get("team") or "",
        })
        enriched_nodes += 1

        # MANAGES / REPORTS_TO
        for report in person.get("manages", []):
            rnode = _person(report)
            if rnode not in G:
                G.add_node(rnode, node_type="person", label=report)
            G.add_edge(node_id, rnode, rel=MANAGES,    source="org_chart")
            G.add_edge(rnode, node_id, rel=REPORTS_TO, source="org_chart")
            added_edges += 2

    if verbose:
        print(f"  Org chart: {enriched_nodes} people, "
              f"{len(org.get('teams', []))} teams, {added_edges} org edges")

    return G


def get_org_structure() -> dict:
    """Return full org: teams + people with doc stats, for API and generation."""
    G   = load_graph()
    org = load_org_chart()
    if not G or not org:
        return {"error": "Graph or org_chart.json not found"}

    # ── Teams ─────────────────────────────────────────────────────────────────
    teams_data = {}
    for team in org.get("teams", []):
        teams_data[team["id"]] = {
            "id":          team["id"],
            "name":        team["name"],
            "goal":        team.get("goal", ""),
            "description": team.get("description", ""),
            "lead":        team.get("lead", ""),
            "members":     team.get("members", []),
        }

    # ── People ────────────────────────────────────────────────────────────────
    people_data = {}
    for person in org.get("people", []):
        canonical = person["canonical"]
        node_id   = _person(canonical)

        authored    = sum(1 for _, _, d in G.out_edges(node_id, data=True)
                         if d.get("rel") == AUTHORED)
        contributed = sum(1 for _, _, d in G.out_edges(node_id, data=True)
                         if d.get("rel") == CONTRIBUTED_TO)
        expert_in   = [
            t.replace("topic:", "")
            for _, t, d in G.out_edges(node_id, data=True)
            if d.get("rel") == EXPERT_IN
        ]

        # Resolve team name
        team_id   = person.get("team")
        team_name = teams_data.get(team_id, {}).get("name", "") if team_id else ""

        people_data[canonical] = {
            "canonical":       canonical,
            "title":           person.get("title", ""),
            "employment_type": person.get("employment_type", "staff"),
            "scope":           person.get("scope", ""),
            "bio":             person.get("bio", ""),
            "skills":          person.get("skills", []),
            "contact":         person.get("contact", ""),
            "reports_to":      person.get("reports_to"),
            "manages":         person.get("manages", []),
            "team":            team_id,
            "team_name":       team_name,
            "doc_stats": {
                "authored":    authored,
                "contributed": contributed,
                "total":       authored + contributed,
            },
            "expert_in": expert_in,
        }

    return {
        "organization": org.get("organization", ""),
        "department":   org.get("department", ""),
        "teams":        teams_data,
        "people":       people_data,
    }


# ── Pipeline entry points ─────────────────────────────────────────────────────

def run_graph_build(gemini_pass: bool = False, verbose: bool = True) -> nx.MultiDiGraph:
    docs = load_enriched_docs()
    if not docs:
        raise FileNotFoundError("enriched_docs.json not found — run Step 2 first")

    docs = [d for d in docs if d.get("enrichment_status") == "done"]

    if verbose:
        print(f"Building graph from {len(docs)} enriched documents...")

    G = build_graph_from_docs(docs, verbose=verbose)
    G = enrich_graph_with_org(G, verbose=verbose)

    if gemini_pass:
        G = enrich_graph_with_gemini(G, docs, verbose=verbose)

    path = save_graph(G)
    stats = get_graph_stats(G)

    if verbose:
        print(f"\n{'─'*60}")
        print(f"Nodes  : {stats['total_nodes']}")
        print(f"Edges  : {stats['total_edges']}")
        print(f"Output : {path}")

    return G


def get_graph_build_status() -> dict:
    if not GRAPH_PATH.exists():
        return {"status": "not_run", "total_nodes": 0, "total_edges": 0}
    G = load_graph()
    if G is None:
        return {"status": "corrupt"}
    return {"status": "ok", **get_graph_stats(G)}


if __name__ == "__main__":
    gemini = "--gemini" in sys.argv
    verbose = "--quiet" not in sys.argv
    run_graph_build(gemini_pass=gemini, verbose=verbose)
