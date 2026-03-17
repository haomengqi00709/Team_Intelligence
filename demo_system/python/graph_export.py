"""
Graph export for D3.js visualization.

Reads cache/knowledge_graph.json, writes cache/graph_d3.json in D3
force-directed format:
  { "nodes": [...], "links": [...] }

Node fields:   id, label, type, group, size, metadata
Link fields:   source, target, rel, source_type (rule/gemini)

Run:
    python3 graph_export.py              # full graph
    python3 graph_export.py --people     # people + docs only (no topic/phase nodes)
    python3 graph_export.py --core       # people + docs + key edge types only
"""

import json
import sys
from collections import Counter

from graph_builder import load_graph, get_graph_stats
from config import CACHE_DIR

# ── Node group numbers (D3 uses these for color mapping) ─────────────────────
NODE_GROUPS = {
    "person":   1,
    "document": 2,
    "topic":    3,
    "phase":    4,
    "team":     5,
}

# ── Source folder → sub-group for documents (for color differentiation) ──────
FOLDER_GROUPS = {
    "email":    21,
    "meetings": 22,
    "work":     23,
    "guide":    24,
}

# ── Edge types to include per mode ───────────────────────────────────────────
EDGE_SETS = {
    "full": None,   # None = all edges
    "people": {
        "AUTHORED", "CONTRIBUTED_TO", "APPROVED", "OPPOSED", "EXPERT_IN",
        "MANAGES", "MEMBER_OF", "LEADS",
    },
    "core": {
        "AUTHORED", "REFERENCES", "SUPERSEDES", "TRIGGERED", "APPROVED", "OPPOSED",
        "MANAGES", "MEMBER_OF", "LEADS",
    },
    "org": {
        "MANAGES", "REPORTS_TO", "MEMBER_OF", "LEADS",
    },
}

# Node types to include per mode
NODE_TYPE_SETS = {
    "full":   {"person", "document", "topic", "phase", "team"},
    "people": {"person", "document", "team"},
    "core":   {"person", "document", "team"},
    "org":    {"person", "team"},
}


def export_graph(mode: str = "full") -> dict:
    G = load_graph()
    if G is None:
        raise FileNotFoundError("knowledge_graph.json not found — run python3 graph_builder.py first")

    allowed_node_types = NODE_TYPE_SETS.get(mode, NODE_TYPE_SETS["full"])
    allowed_edge_rels  = EDGE_SETS.get(mode)   # None = all

    # ── Compute degree for node sizing ────────────────────────────────────────
    degree = dict(G.degree())

    # ── Build node list ───────────────────────────────────────────────────────
    node_ids_included: set[str] = set()
    nodes_out = []

    for node_id, data in G.nodes(data=True):
        node_type = data.get("node_type", "document")
        if node_type not in allowed_node_types:
            continue

        # Group for D3 color mapping
        if node_type == "document":
            folder = data.get("source_folder", "")
            group = FOLDER_GROUPS.get(folder, NODE_GROUPS["document"])
        else:
            group = NODE_GROUPS.get(node_type, 2)

        # Size proportional to degree (capped)
        raw_size = degree.get(node_id, 1)
        size = max(8, min(40, raw_size * 2))

        meta: dict = {}
        if node_type == "document":
            meta = {
                "file_type":        data.get("file_type", ""),
                "source_folder":    data.get("source_folder", ""),
                "event_date":       data.get("event_date", ""),
                "project_phase":    data.get("project_phase", ""),
                "approval_status":  data.get("approval_status", ""),
                "document_version": data.get("document_version", ""),
            }
        elif node_type == "person":
            meta = {
                "title":           data.get("title", ""),
                "employment_type": data.get("employment_type", ""),
                "team":            data.get("team", ""),
                "contact":         data.get("contact", ""),
            }
        elif node_type == "team":
            meta = {
                "goal":        data.get("goal", ""),
                "description": data.get("description", ""),
                "lead":        data.get("lead", ""),
            }

        nodes_out.append({
            "id":    node_id,
            "label": data.get("label", node_id),
            "type":  node_type,
            "group": group,
            "size":  size,
            "meta":  meta,
        })
        node_ids_included.add(node_id)

    # ── Build link list ───────────────────────────────────────────────────────
    # Deduplicate: MultiDiGraph can have multiple edges between same pair
    seen_links: set[tuple] = set()
    links_out = []

    for src, tgt, data in G.edges(data=True):
        rel = data.get("rel", "UNKNOWN")

        if allowed_edge_rels is not None and rel not in allowed_edge_rels:
            continue
        if src not in node_ids_included or tgt not in node_ids_included:
            continue

        key = (src, tgt, rel)
        if key in seen_links:
            continue
        seen_links.add(key)

        links_out.append({
            "source":      src,
            "target":      tgt,
            "rel":         rel,
            "data_source": data.get("source", "rule"),   # "rule" or "gemini"
            "description": data.get("description", ""),
        })

    # ── Summary stats (passed to frontend for legend) ─────────────────────────
    node_type_counts = Counter(n["type"]  for n in nodes_out)
    edge_rel_counts  = Counter(l["rel"]   for l in links_out)

    return {
        "meta": {
            "mode":             mode,
            "total_nodes":      len(nodes_out),
            "total_links":      len(links_out),
            "nodes_by_type":    dict(node_type_counts),
            "links_by_rel":     dict(edge_rel_counts),
        },
        "nodes": nodes_out,
        "links": links_out,
    }


def run_export(mode: str = "full", verbose: bool = True) -> dict:
    data = export_graph(mode)
    out_path = CACHE_DIR / f"graph_d3_{mode}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    if verbose:
        m = data["meta"]
        print(f"Mode    : {mode}")
        print(f"Nodes   : {m['total_nodes']}  {m['nodes_by_type']}")
        print(f"Links   : {m['total_links']}  {m['links_by_rel']}")
        print(f"Output  : {out_path}")

    return data


if __name__ == "__main__":
    mode = "full"
    if "--people" in sys.argv:
        mode = "people"
    elif "--core" in sys.argv:
        mode = "core"

    run_export(mode)
