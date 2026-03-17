"""
Step 2 — Metadata Enrichment via Gemini
Reads cache/parsed_docs.json, sends each document's text to gemini-2.0-flash,
extracts semantic fields that rule-based logic cannot, writes cache/enriched_docs.json.

Fields added:
  - topics             (controlled vocabulary tags)
  - project_phase      (initiation → closeout)
  - additional_refs    (prose-based cross-document links, merged into references_docs)
  - event_date         (filled for docs where rule-based extraction missed it)

Resume-safe: already-enriched docs are skipped on re-run.
"""

import json
import time
import sys
from pathlib import Path

import google.generativeai as genai

from config import CACHE_DIR, GEMINI_API_KEY, GENERATION_MODEL_FLASH

# ── Gemini setup ──────────────────────────────────────────────────────────────

genai.configure(api_key=GEMINI_API_KEY)

# ── Controlled vocabularies ───────────────────────────────────────────────────

TOPIC_VOCABULARY = [
    "geographic_weight",       # the 5%→15% geo sensitivity debate
    "data_hygiene",            # 1900-01-01 legacy decay issue
    "legacy_decay",            # specifically the 2018 migration artifact
    "streamlining",            # STRL-2026 low-risk deferral filter
    "budget_neutrality",       # Marc's zero-budget-growth mandate
    "compliance_history",      # historical violation records
    "risk_scoring",            # the model's scoring algorithm
    "model_validation",        # testing, UAT, parallel run
    "sensitivity_analysis",    # Scenario A vs Scenario B comparison
    "regional_safety",         # Dave's Pacific/urban safety concerns
    "vancouver_corridor",      # specific Vancouver transload hub issue
    "erap_safety",             # ERAP boolean override for high-hazard materials
    "class3_flammable",        # Class 3 flammable liquid incidents
    "sas_implementation",      # SAS code, macros, PROC SQL
    "audit_compliance",        # IAD audit, Four Pillars, traceability
    "decision_making",         # director approvals, formal sign-offs
    "stakeholder_alignment",   # cross-team agreement, consultant relations
    "data_dictionary",         # TDG_CORE schema, field definitions
    "performance_metrics",     # detection rates, KPIs, fiscal outcomes
    "expert_profiling",        # Jason's role, contributor recognition
    "incident_response",       # North York case, real-world validation
    "viya_migration",          # SAS Viya cloud migration
    "project_governance",      # SOW, procurement, contracts
    "policy_compliance",       # TBS directive, regulatory requirements
]

PHASE_VOCABULARY = [
    "initiation",       # problem identified, escalation to management
    "planning",         # scoping, procurement, SOW, consultant onboarding
    "development",      # data analysis, model building, SAS coding
    "review",           # technical review, methodology debate
    "approval",         # director sign-off, formal decisions
    "implementation",   # production deployment, UAT, parallel run
    "audit",            # IAD audit, compliance verification
    "operations",       # post-deployment monitoring, recalibration
    "closeout",         # project closure, handover, archive
]

# Key non-email doc_ids Gemini can reference (emails handled by rule-based)
LINKABLE_DOCS = [
    "meetings_Meeting_Minutes_2026_06_05_Project_Kickoff",
    "meetings_Meeting_Minutes_2026_06_12_Technical_Review",
    "meetings_Meeting_Minutes_2026_06_15_Scenario_Alignment",
    "meetings_Meeting_Minutes_2026_06_17_Decision_Final_Signoff",
    "meetings_Meeting_Minutes_2026_07_08_Technical_Implementation",
    "meetings_Meeting_Minutes_2026_10_15_Audit_Interview",
    "meetings_Meeting_Minutes_2027_01_20_Trend_Analysis",
    "meetings_Meeting_Minutes_2027_03_10_Project_Closeout_Viya_Kickoff",
    "work_Algorithm_Methodology_v1_0_Draft",
    "work_Algorithm_Methodology_v2_0_Final",
    "work_Impact_Summary_Table_v1_Aris_Draft",
    "work_Impact_Summary_Table_v2_Jason_Sensitivity_Analysis",
    "work_NOP_Risk_Model_PROD_AUG01",
    "work_TDG_CORE_Data_Dictionary_v2_1",
    "work_BC_Okanagan_Streamline_Audit_Data",
    "work_Conflict_Check_Report_v1_0",
    "work_Internal_Audit_Memo_2027_01_Final",
    "work_North_York_Incident_Report_Summary",
    "work_2027_Trend_Watch_Class3",
    "guide_TBS_Directive_on_Automated_Decision_Making_v3",
    "guide_Vancouver_Maritime_Review_May_2026",
    "guide_Env_Canada_Technical_Brief_Winter2026",
    "guide_Internal_Audit_Guideline_ADS_202_B",
]

# ── Prompt builder ────────────────────────────────────────────────────────────

SYSTEM_CONTEXT = """
You are analyzing documents from a Transport Canada internal project:
"NOP Risk Model Modernization 2026-27."

PROJECT SUMMARY:
The team rebuilt a dangerous goods site inspection risk model. The key changes were:
- Geographic weight raised from 5% to 15% (Scenario B)
- A streamlining filter (STRL-2026) added to offset increased inspection load
- Legacy data decay (1900-01-01 artifact from 2018 migration) cleaned from the database
- Final model received a "Fully Compliant" audit rating

KEY PEOPLE:
- Jason Hao: Technical Lead, SAS developer, data expert
- Sean: Project Lead
- Dr. Aris: External statistical consultant
- Dave: Regional Inspector (Pacific), safety advocate
- Marc: Director, approved final decision
- Carolyn: Data Management Manager
- Roger: Senior Analyst, QA
- Stephen: Internal Auditor (IAD)

KEY CONCEPTS:
- Scenario A: 10% geo weight (Aris's initial proposal, rejected)
- Scenario B: 15% geo weight (Jason's sensitivity analysis, approved by Marc)
- STRL-2026: Streamlining filter — sites with 5+ clean years and score < 20 get deferred
- ERAP: Emergency Response Assistance Plan — ERAP sites are NEVER streamlined
- 1900-01-01: Legacy date artifact from 2018 system migration (11,240 records affected)
""".strip()


def build_prompt(doc: dict) -> str:
    existing_date = doc.get("event_date") or "unknown"
    doc_type      = doc["file_type"]
    doc_id        = doc["doc_id"]
    content       = doc.get("raw_text", "")[:6000]  # cap at ~6k chars

    linkable_str  = "\n".join(f"  - {d}" for d in LINKABLE_DOCS)
    topics_str    = ", ".join(TOPIC_VOCABULARY)
    phases_str    = ", ".join(PHASE_VOCABULARY)

    return f"""
{SYSTEM_CONTEXT}

---
DOCUMENT TO ANALYZE:
doc_id    : {doc_id}
file_type : {doc_type}
date      : {existing_date}

CONTENT:
{content}
---

TASK: Extract metadata for this document. Return ONLY valid JSON — no explanation, no markdown.

CONTROLLED VOCABULARY:
- topics (pick 2–5): {topics_str}
- project_phase (pick 1): {phases_str}

LINKABLE DOCUMENTS (only use these exact IDs for additional_references):
{linkable_str}

OUTPUT FORMAT:
{{
  "topics": ["tag1", "tag2"],
  "project_phase": "phase_name",
  "additional_references": ["doc_id_if_referenced"],
  "event_date": "YYYY-MM-DD or null if truly unknown"
}}

Rules:
- additional_references: only include if the document explicitly or clearly implicitly refers to that document. Leave empty if unsure.
- event_date: only fill if you can determine it from the content and it is not already known ({existing_date}). Return null otherwise.
- Do not invent topics or phases outside the vocabularies above.
""".strip()


# ── Gemini call ───────────────────────────────────────────────────────────────

def call_gemini(prompt: str, model) -> dict | None:
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        text = response.text.strip()
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            print(f"    [TYPE ERROR] expected dict, got {type(parsed).__name__}")
            return None
        return parsed
    except json.JSONDecodeError as e:
        print(f"    [JSON ERROR] {e} — raw: {response.text[:200]}")
        return None
    except Exception as e:
        print(f"    [API ERROR] {e}")
        return None


# ── Merge enrichment into doc ─────────────────────────────────────────────────

def merge_enrichment(doc: dict, result: dict) -> dict:
    # Topics — set, no duplicates
    existing = set(doc.get("topics", []))
    new_topics = [t for t in result.get("topics", []) if t in TOPIC_VOCABULARY]
    doc["topics"] = sorted(existing | set(new_topics))

    # Project phase
    phase = result.get("project_phase", "")
    if phase in PHASE_VOCABULARY:
        doc["project_phase"] = phase

    # Merge additional references into references_docs
    existing_refs = set(doc.get("references_docs", []))
    new_refs = [
        r for r in result.get("additional_references", [])
        if r in LINKABLE_DOCS and r != doc["doc_id"]
    ]
    doc["references_docs"] = sorted(existing_refs | set(new_refs))

    # Fill missing event_date
    if not doc.get("event_date"):
        new_date = result.get("event_date")
        if new_date and new_date != "null" and new_date is not None:
            doc["event_date"] = new_date

    doc["enrichment_status"] = "done"
    return doc


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_enrichment(verbose: bool = True) -> list[dict]:
    parsed_path   = CACHE_DIR / "parsed_docs.json"
    enriched_path = CACHE_DIR / "enriched_docs.json"

    if not parsed_path.exists():
        raise FileNotFoundError("parsed_docs.json not found — run Step 1 first")

    with open(parsed_path, encoding="utf-8") as f:
        docs = json.load(f)

    # Load any prior enrichment progress
    if enriched_path.exists():
        with open(enriched_path, encoding="utf-8") as f:
            enriched = json.load(f)
        enriched_ids = {d["doc_id"] for d in enriched if d.get("enrichment_status") == "done"}
        # Merge: start from enriched, add any new docs from parsed
        enriched_map = {d["doc_id"]: d for d in enriched}
        for d in docs:
            if d["doc_id"] not in enriched_map:
                enriched_map[d["doc_id"]] = d
        docs = list(enriched_map.values())
    else:
        enriched_ids = set()

    to_process = [d for d in docs if d.get("enrichment_status") != "done"]

    if not to_process:
        if verbose:
            print("All documents already enriched. Nothing to do.")
        return docs

    if verbose:
        print(f"Enriching {len(to_process)} docs ({len(enriched_ids)} already done)")
        print(f"Model: {GENERATION_MODEL_FLASH}\n")

    model = genai.GenerativeModel(GENERATION_MODEL_FLASH)
    doc_map = {d["doc_id"]: d for d in docs}

    for i, doc in enumerate(to_process, 1):
        if verbose:
            print(f"[{i:3}/{len(to_process)}] {doc['doc_id'][:55]:55s}", end=" ", flush=True)

        prompt = build_prompt(doc)
        result = call_gemini(prompt, model)

        if result:
            doc_map[doc["doc_id"]] = merge_enrichment(doc, result)
            if verbose:
                topics = doc_map[doc["doc_id"]].get("topics", [])
                phase  = doc_map[doc["doc_id"]].get("project_phase", "?")
                refs   = doc_map[doc["doc_id"]].get("references_docs", [])
                print(f"✓  phase={phase:15s}  topics={topics}  refs={len(refs)}")
        else:
            doc["enrichment_status"] = "failed"
            doc_map[doc["doc_id"]] = doc
            if verbose:
                print("✗  failed")

        # Save progress after every doc (resume-safe)
        with open(enriched_path, "w", encoding="utf-8") as f:
            json.dump(list(doc_map.values()), f, indent=2, ensure_ascii=False)

        # Polite rate-limiting
        time.sleep(0.5)

    final = list(doc_map.values())
    done   = sum(1 for d in final if d.get("enrichment_status") == "done")
    failed = sum(1 for d in final if d.get("enrichment_status") == "failed")

    if verbose:
        print(f"\n{'─'*60}")
        print(f"Enriched : {done}/{len(final)}")
        print(f"Failed   : {failed}")
        print(f"Output   : {enriched_path}")

    return final


def load_enriched_docs() -> list[dict]:
    path = CACHE_DIR / "enriched_docs.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_enrichment_status() -> dict:
    docs = load_enriched_docs()
    if not docs:
        return {"status": "not_run", "total": 0}

    done   = [d for d in docs if d.get("enrichment_status") == "done"]
    failed = [d for d in docs if d.get("enrichment_status") == "failed"]

    # Topic coverage
    all_topics: dict[str, int] = {}
    for d in done:
        for t in d.get("topics", []):
            all_topics[t] = all_topics.get(t, 0) + 1

    # Phase coverage
    all_phases: dict[str, int] = {}
    for d in done:
        p = d.get("project_phase")
        if p:
            all_phases[p] = all_phases.get(p, 0) + 1

    # Reference coverage
    total_refs = sum(len(d.get("references_docs", [])) for d in done)

    return {
        "status":           "complete" if not failed else "partial",
        "total":            len(docs),
        "done":             len(done),
        "failed":           len(failed),
        "failed_docs":      [d["doc_id"] for d in failed],
        "topic_frequency":  dict(sorted(all_topics.items(), key=lambda x: -x[1])),
        "phase_breakdown":  all_phases,
        "total_references": total_refs,
    }


if __name__ == "__main__":
    verbose = "--quiet" not in sys.argv
    run_enrichment(verbose=verbose)
