"""
Step 5 — Generation + Source Citation

Takes retrieved chunks (or org data) and produces a final answer via Gemini
with inline [Source: doc_id] citations.

Model selection:
  gemini-2.0-flash  — causal_trace, contributor_profile, onboarding, general, org_lookup
  gemini-2.5-pro    — conflict_detect, audit_chain  (need careful multi-source reasoning)

Response format:
  {
    "answer":          str,   # prose with inline [Source: doc_id] citations
    "query_type":      str,
    "model_used":      str,
    "cited_sources":   list,  # only doc_ids actually cited in the answer
    "all_sources":     list,  # all retrieved sources passed to the model
    "retrieval_count": int,
  }
"""

import json
import re

import google.generativeai as genai

from config import GEMINI_API_KEY, GENERATION_MODEL_FLASH, GENERATION_MODEL_PRO

genai.configure(api_key=GEMINI_API_KEY)

# ── Model routing ─────────────────────────────────────────────────────────────

COMPLEX_QUERY_TYPES = {"conflict_detect", "audit_chain"}

def _select_model(query_type: str) -> str:
    return GENERATION_MODEL_PRO if query_type in COMPLEX_QUERY_TYPES \
           else GENERATION_MODEL_FLASH


# ── System prompt ─────────────────────────────────────────────────────────────

BASE_SYSTEM = """
You are a project knowledge assistant for the NOP Risk Model Modernization project at Transport Canada.

RULES:
- Answer using ONLY the provided source documents or organizational data.
- Every factual claim must end with [Source: X] where X is the exact doc_id value (e.g. [Source: MSG-018] or [Source: work_Algorithm_Methodology_v2_0_Final]). Never write "doc_id:" inside the brackets.
- If two sources contradict each other, state the contradiction explicitly and cite both sides.
- If the answer cannot be found in the provided sources, say exactly: "Not found in project records."
- Be concise and direct. Do not pad your answer.
- Do not invent facts, dates, names, or decisions not present in the sources.
""".strip()

EXTRA_INSTRUCTIONS = {
    "conflict_detect": """
ADDITIONAL INSTRUCTION:
Actively look for contradictions, disagreements, or version differences between the sources.
Present each conflict as: "Conflict: [description] — [Source: A] vs [Source: B]"
Do NOT silently pick one side. If no conflict is found, say so explicitly.
""".strip(),

    "audit_chain": """
ADDITIONAL INSTRUCTION:
Present your answer as a sequential provenance chain showing how each document
connects to the next. Use this format where applicable:
  Step 1: [earliest event] [Source: X]
  Step 2: [next event] [Source: Y]
  ...
""".strip(),

    "onboarding": """
ADDITIONAL INSTRUCTION:
Structure your answer as a reading guide in logical order (earliest/foundational first).
For each recommended document, explain in one sentence why a new person should read it.
""".strip(),

    "org_lookup": """
ADDITIONAL INSTRUCTION:
Answer from the organizational data provided. Include the person's title, scope,
reporting line, and team where relevant. Be specific about responsibilities.
""".strip(),
}


# ── Prompt builders ───────────────────────────────────────────────────────────

def _format_chunk(i: int, chunk: dict) -> str:
    topics = chunk.get("topics", "[]")
    try:
        topics_list = json.loads(topics) if isinstance(topics, str) else topics
        topics_str  = ", ".join(topics_list[:3]) if topics_list else ""
    except Exception:
        topics_str = ""

    header = (
        f"[{i}] doc_id: {chunk['doc_id']} | "
        f"type: {chunk['file_type']} | "
        f"date: {chunk.get('event_date', 'unknown')} | "
        f"author: {chunk.get('author', 'unknown')}"
    )
    if topics_str:
        header += f" | topics: {topics_str}"

    return f"{header}\n---\n{chunk['text']}\n---"


def _build_chunk_prompt(query: str, query_type: str, chunks: list[dict]) -> str:
    sources_text = "\n\n".join(_format_chunk(i + 1, c) for i, c in enumerate(chunks))
    extra = EXTRA_INSTRUCTIONS.get(query_type, "")

    return f"""{BASE_SYSTEM}

{extra}

SOURCES:
{sources_text}

QUESTION: {query}

ANSWER:"""


def _build_org_prompt(query: str, org: dict) -> str:
    extra = EXTRA_INSTRUCTIONS.get("org_lookup", "")

    # Condense org data for the prompt
    org_text_parts = []

    if org.get("org_answer"):
        answer = org["org_answer"]

        if "canonical" in answer:
            # Person lookup
            p = answer
            org_text_parts.append(
                f"PERSON: {p['canonical']}\n"
                f"Title: {p['title']}\n"
                f"Employment: {p.get('employment_type', '')}\n"
                f"Reports to: {p.get('reports_to', 'N/A')}\n"
                f"Manages: {', '.join(p.get('manages', [])) or 'N/A'}\n"
                f"Team: {p.get('team_name', p.get('team', 'N/A'))}\n"
                f"Skills: {', '.join(p.get('skills', []))}\n"
                f"Scope: {p.get('scope', '')}\n"
                f"Bio: {p.get('bio', '')}\n"
                f"Doc stats: authored={p.get('doc_stats', {}).get('authored', 0)}, "
                f"contributed={p.get('doc_stats', {}).get('contributed', 0)}"
            )

        elif "name" in answer and "goal" in answer:
            # Team lookup
            t = answer
            org_text_parts.append(
                f"TEAM: {t['name']}\n"
                f"Goal: {t['goal']}\n"
                f"Description: {t['description']}\n"
                f"Lead: {t['lead']}\n"
                f"Members: {', '.join(t.get('members', []))}"
            )
            for mname, mdata in answer.get("members_detail", {}).items():
                org_text_parts.append(
                    f"\nMEMBER: {mname}\n"
                    f"Title: {mdata['title']}\n"
                    f"Scope: {mdata.get('scope', '')}"
                )

        elif "matched_people" in answer:
            # Skill match
            for mname, mdata in answer["matched_people"].items():
                org_text_parts.append(
                    f"PERSON: {mname}\n"
                    f"Title: {mdata['title']}\n"
                    f"Skills: {', '.join(mdata.get('skills', []))}\n"
                    f"Scope: {mdata.get('scope', '')}"
                )

    else:
        # Full org
        org_data = org.get("org_data", org)
        for pname, pdata in org_data.get("people", {}).items():
            org_text_parts.append(
                f"PERSON: {pname} | Title: {pdata['title']} | "
                f"Reports to: {pdata.get('reports_to', 'N/A')} | "
                f"Manages: {', '.join(pdata.get('manages', [])) or 'N/A'}"
            )
        for tid, tdata in org_data.get("teams", {}).items():
            org_text_parts.append(
                f"TEAM: {tdata['name']} | Lead: {tdata['lead']} | "
                f"Members: {', '.join(tdata.get('members', []))}\n"
                f"Goal: {tdata['goal']}"
            )

    org_text = "\n\n".join(org_text_parts)

    return f"""{BASE_SYSTEM}

{extra}

ORGANIZATIONAL DATA:
{org_text}

QUESTION: {query}

ANSWER (cite org data as [Source: org_chart]):"""


# ── Citation extractor ────────────────────────────────────────────────────────

def _extract_citations(answer: str, chunks: list[dict], is_org: bool) -> list[str]:
    """Pull [Source: X] doc_ids from the answer text."""
    pattern = re.compile(r'\[Source:\s*(?:doc_id:\s*)?([^\]]+)\]')
    cited_raw = pattern.findall(answer)
    cited = [c.strip() for c in cited_raw]

    if is_org:
        return ["org_chart"] if cited else []

    # Only return doc_ids that were actually in the retrieved set
    valid_ids = {c["doc_id"] for c in chunks}
    return [c for c in cited if c in valid_ids]


# ── Gemini call ───────────────────────────────────────────────────────────────

def _call_gemini(prompt: str, model_id: str) -> str:
    model    = genai.GenerativeModel(model_id)
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(temperature=0.2),
    )
    return response.text.strip()


# ── Source card builder ───────────────────────────────────────────────────────

def _build_source_cards(chunks: list[dict], cited_ids: list[str]) -> list[dict]:
    """Build source metadata cards for the cited documents."""
    seen = set()
    cards = []
    # Cited first, then uncited
    ordered = sorted(chunks, key=lambda c: (c["doc_id"] not in cited_ids, c["doc_id"]))
    for chunk in ordered:
        doc_id = chunk["doc_id"]
        if doc_id in seen:
            continue
        seen.add(doc_id)
        cards.append({
            "doc_id":      doc_id,
            "file_type":   chunk.get("file_type", ""),
            "author":      chunk.get("author", ""),
            "event_date":  chunk.get("event_date", ""),
            "project_phase": chunk.get("project_phase", ""),
            "cited":       doc_id in cited_ids,
            "excerpt":     chunk["text"][:250].strip() + ("…" if len(chunk["text"]) > 250 else ""),
        })
    return cards


# ── Main generate function ────────────────────────────────────────────────────

def generate(query: str, retrieval_result: dict) -> dict:
    """
    Takes the output of retriever.retrieve() and produces a final answer.
    """
    query_type = retrieval_result["query_type"]
    chunks     = retrieval_result.get("chunks", [])
    org        = retrieval_result.get("org")
    model_id   = _select_model(query_type)
    is_org     = query_type == "org_lookup"

    # Build prompt
    if is_org and org:
        prompt = _build_org_prompt(query, org)
    elif chunks:
        prompt = _build_chunk_prompt(query, query_type, chunks)
    else:
        return {
            "answer":          "Not found in project records.",
            "query_type":      query_type,
            "model_used":      model_id,
            "cited_sources":   [],
            "all_sources":     [],
            "retrieval_count": 0,
        }

    # Call Gemini
    answer = _call_gemini(prompt, model_id)

    # Extract citations
    cited_ids = _extract_citations(answer, chunks, is_org)

    # Build source cards
    if is_org:
        all_sources = [{"doc_id": "org_chart", "file_type": "org_chart",
                        "cited": True, "excerpt": "Organizational structure data"}]
    else:
        all_sources = _build_source_cards(chunks, cited_ids)

    return {
        "answer":          answer,
        "query_type":      query_type,
        "model_used":      model_id,
        "cited_sources":   cited_ids,
        "all_sources":     all_sources,
        "retrieval_count": len(chunks),
    }


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from router import classify
    from retriever import retrieve

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
        "Why was the geographic weight changed from 5% to 15%?"

    print(f"Query      : {query}")
    cl     = classify(query)
    result = retrieve(query, cl, n=8)
    print(f"Type       : {cl.query_type} ({cl.confidence})")
    print(f"Retrieved  : {result['total_chunks']} chunks | mix={result['source_mix']}")
    print(f"Generating...")

    response = generate(query, result)
    print(f"Model      : {response['model_used']}")
    print(f"Cited      : {response['cited_sources']}")
    print()
    print("─" * 70)
    print(response["answer"])
    print("─" * 70)
    print()
    print("SOURCES:")
    for s in response["all_sources"]:
        cited_mark = "✓" if s["cited"] else " "
        print(f"  [{cited_mark}] {s['doc_id']:45s} {s.get('file_type',''):18s} {s.get('event_date','')}")
