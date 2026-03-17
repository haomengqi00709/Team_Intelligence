"""
Rule-based metadata extraction — no LLM required.

Extracts from structure, filenames, and text patterns:
  - event_date       (ISO date string)
  - author           (canonical name string)
  - contributors     (list of canonical names)
  - document_version (e.g. "v1", "v2.0", "Final")
  - approval_status  (draft | approved | unknown)
  - references_docs  (list of MSG-XXX / MTG-XXX ids found in text)
  - thread_id        (root email doc_id for email threads)

Semantic fields (topics, project_phase, cross-prose references)
are left for Step 2 (Gemini enrichment).

Privacy defaults — populated now, enforced later:
  - sensitivity_level = "internal"
  - permitted_roles   = ["*"]
  - owner_team        = "Strategic Oversight"
"""

import re
from email.utils import parsedate_to_datetime

# ── Name normalisation ────────────────────────────────────────────────────────

# Maps email addresses and name variants → canonical display name
CANONICAL_NAMES: dict[str, str] = {
    # email addresses
    "jason.hao@tc.gc.ca":          "Jason Hao",
    "sean.lead@tc.gc.ca":          "Sean",
    "roger.sr@tc.gc.ca":           "Roger",
    "carolyn.mgr@tc.gc.ca":        "Carolyn",
    "marc.dir@tc.gc.ca":           "Marc",
    "aris.consultant@ext.tc.gc.ca":"Dr. Aris",
    "dave.inspector@tc.gc.ca":     "Dave",
    "stephen.audit@tc.gc.ca":      "Stephen",
    # display name variants (lowercase for matching)
    "jason hao":                   "Jason Hao",
    "jason":                       "Jason Hao",
    "sean":                        "Sean",
    "roger":                       "Roger",
    "carolyn":                     "Carolyn",
    "marc":                        "Marc",
    "dr. aris":                    "Dr. Aris",
    "dr aris":                     "Dr. Aris",
    "aris":                        "Dr. Aris",
    "dave":                        "Dave",
    "stephen":                     "Stephen",
    "vicky":                       "Vicky",
    "luc trudel":                  "Luc Trudel",
    "luc":                         "Luc Trudel",
    "judy":                        "Judy",
    "inspector marie":             "Inspector Marie",
    "marie":                       "Inspector Marie",
    "dr. l. henderson":            "Dr. L. Henderson",
    "dr. henderson":               "Dr. L. Henderson",
}


def normalise_name(raw: str) -> str | None:
    """Return canonical name or None if not recognised."""
    if not raw:
        return None

    # Strip email address: "Jason Hao <jason.hao@tc.gc.ca>"
    email_match = re.search(r'<([^>]+)>', raw)
    if email_match:
        addr = email_match.group(1).strip().lower()
        if addr in CANONICAL_NAMES:
            return CANONICAL_NAMES[addr]

    # Strip role suffix after comma/dash/paren:
    # "Jason Hao, Technical Lead"  → "Jason Hao"
    # "Jason Hao (Technical Lead)" → "Jason Hao"
    # "Dr. Aris - Lead Consultant" → "Dr. Aris"
    name_part = re.split(r'[,\(\[]', raw)[0]
    name_part = re.split(r'\s+-\s+', name_part)[0].strip()

    clean = name_part.lower()
    if clean in CANONICAL_NAMES:
        return CANONICAL_NAMES[clean]

    return None


def normalise_names(raws: list[str]) -> list[str]:
    """Normalise a list, deduplicate, preserve order, drop unknowns."""
    seen, result = set(), []
    for r in raws:
        name = normalise_name(r)
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


# ── Date parsing ──────────────────────────────────────────────────────────────

MONTHS = {
    "january":"01","february":"02","march":"03","april":"04",
    "may":"05","june":"06","july":"07","august":"08",
    "september":"09","october":"10","november":"11","december":"12",
}

_LONG_DATE = re.compile(
    r'\b(january|february|march|april|may|june|july|august|'
    r'september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})\b',
    re.IGNORECASE,
)
_ISO_DATE  = re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b')


def parse_date_from_text(text: str) -> str | None:
    """
    Extract the first recognisable date from arbitrary text.
    Returns "YYYY-MM-DD" or None.
    """
    # ISO format first
    m = _ISO_DATE.search(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # "June 05, 2026" / "June 5 2026"
    m = _LONG_DATE.search(text)
    if m:
        month = MONTHS[m.group(1).lower()]
        day   = m.group(2).zfill(2)
        year  = m.group(3)
        return f"{year}-{month}-{day}"
    return None


def parse_email_date(date_str: str) -> str | None:
    """Convert RFC-2822 email date to ISO date string."""
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.date().isoformat()
    except Exception:
        return parse_date_from_text(date_str)


# ── Field extractors ──────────────────────────────────────────────────────────

def extract_event_date(doc: dict) -> str | None:
    ft = doc["file_type"]
    sf = doc.get("structured_fields", {})

    if ft == "email":
        return parse_email_date(sf.get("date", ""))

    # Meeting filenames: Meeting_Minutes_2026-06-05_...
    if ft == "meeting_minutes":
        m = _ISO_DATE.search(doc["doc_id"])
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # Fallback: look for DATE: pattern in first 500 chars of content
    snippet = doc.get("raw_text", "")[:500]
    date_line = re.search(r'DATE[:\s]+(.+)', snippet, re.IGNORECASE)
    if date_line:
        d = parse_date_from_text(date_line.group(1))
        if d:
            return d

    return None


def extract_author(doc: dict) -> str | None:
    ft = doc["file_type"]
    sf = doc.get("structured_fields", {})

    if ft == "email":
        return normalise_name(sf.get("from", ""))

    # Look for AUTHOR: / PREPARED BY: / RECORDED BY: in first AND last 600 chars
    # (policy docs often have "PREPARED BY" at the bottom)
    text    = doc.get("raw_text", "")
    snippet = text[:600] + "\n" + text[-600:]
    for label in ("AUTHOR", "PREPARED BY", "RECORDED BY", "INTERVIEWER"):
        m = re.search(rf'{label}[:\s]+([^\n]+)', snippet, re.IGNORECASE)
        if m:
            name = normalise_name(m.group(1).strip())
            if name:
                return name

    return None


def extract_contributors(doc: dict) -> list[str]:
    ft = doc["file_type"]
    sf = doc.get("structured_fields", {})
    raw_text = doc.get("raw_text", "")
    names: list[str] = []

    if ft == "email":
        # From + To + Cc
        sources = (
            [sf.get("from", "")]
            + sf.get("to", [])
            + sf.get("cc", [])
        )
        names = [s for s in sources if s]

    elif ft == "meeting_minutes":
        # Extract [ATTENDEES] block
        attendees_block = re.search(
            r'\[ATTENDEES\](.*?)(?=\[|\Z)', raw_text, re.DOTALL | re.IGNORECASE
        )
        if attendees_block:
            lines = attendees_block.group(1).strip().splitlines()
            for line in lines:
                # Lines look like: "- Jason Hao (Technical Lead)"
                m = re.match(r'[-\*]\s*(.+)', line.strip())
                if m:
                    # Take the name before the first "("
                    name_part = re.split(r'[\(\[]', m.group(1))[0].strip()
                    # Handle "Aris's Senior Analyst (Vicky - Remote)" → "Vicky"
                    if "vicky" in name_part.lower():
                        names.append("Vicky")
                    else:
                        names.append(name_part)

    else:
        # Scan for person-labelled lines
        for label in ("AUTHOR", "PREPARED BY", "VERIFIED BY",
                      "RECORDED BY", "CHAIR", "ORGANIZER",
                      "INTERVIEWEE", "INTERVIEWER", "ANALYST"):
            m = re.search(rf'{label}[:\s]+([^\n]+)', raw_text[:800], re.IGNORECASE)
            if m:
                names.append(m.group(1).strip())

    return normalise_names(names)


def extract_document_version(doc: dict) -> str | None:
    # Check filename first
    name = doc["doc_id"]

    # Pattern: _v1_, _v2.0_, _V1_, _V2_ (case insensitive)
    m = re.search(r'[_-][vV](\d+[\.\d]*)[_-]', name + "_")
    if m:
        return f"v{m.group(1)}"

    # Versioned email IDs: MSG-012-V1, MSG-016-V2
    m = re.search(r'-V(\d+)$', name, re.IGNORECASE)
    if m:
        return f"V{m.group(1)}"

    # "Final" or "Draft" in name
    if re.search(r'[_-]final[_-]?', name, re.IGNORECASE):
        return "Final"
    if re.search(r'[_-]draft[_-]?', name, re.IGNORECASE):
        return "Draft"

    # Check content STATUS: / VERSION: lines — use \b to avoid partial word matches
    # e.g. must not match "erap_status" or "final_status" in CSV headers
    snippet = doc.get("raw_text", "")[:400]
    for label in ("VERSION", "STATUS"):
        m = re.search(rf'\b{label}\b[:\s]+([^\n]+)', snippet, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if val:
                return val

    return None


def extract_approval_status(doc: dict) -> str:
    name    = doc["doc_id"].lower()
    snippet = doc.get("raw_text", "")[:400].lower()

    if "final" in name or "approved" in snippet:
        return "approved"
    if "draft" in name or "preliminary" in snippet:
        return "draft"

    status_m = re.search(r'\bstatus\b[:\s]+([^\n]+)', snippet)
    if status_m:
        val = status_m.group(1).strip()
        if "final" in val or "approved" in val or "compliant" in val:
            return "approved"
        if "draft" in val or "preliminary" in val:
            return "draft"

    return "unknown"


_MSG_REF = re.compile(r'\b(MSG-\d+(?:-V\d+)?|MTG-\d+)\b', re.IGNORECASE)


def extract_references_docs(doc: dict) -> list[str]:
    """Find explicit MSG-XXX / MTG-XXX references in the text."""
    text = doc.get("raw_text", "")
    found = _MSG_REF.findall(text)
    # Deduplicate, uppercase, exclude self
    own_id = doc["doc_id"].upper()
    seen, result = set(), []
    for ref in found:
        u = ref.upper()
        if u != own_id and u not in seen:
            seen.add(u)
            result.append(u)
    return result


# ── Thread reconstruction (second pass over all email docs) ───────────────────

def reconstruct_email_threads(docs: list[dict]) -> list[dict]:
    """
    Assigns thread_id to every email doc.
    thread_id = doc_id of the root email in that chain.
    Non-email docs get thread_id = None.
    """
    # Build lookup: cleaned message_id → doc_id
    # e.g.  "<MSG-001@tc.gc.ca>"  →  "MSG-001"
    def clean_mid(mid: str) -> str:
        return mid.strip("<> ").replace("@tc.gc.ca", "").replace("@ext.tc.gc.ca", "")

    email_docs   = {d["doc_id"]: d for d in docs if d["file_type"] == "email"}
    mid_to_docid = {}
    for d in email_docs.values():
        sf  = d.get("structured_fields", {})
        mid = sf.get("message_id", "")
        if mid:
            mid_to_docid[clean_mid(mid)] = d["doc_id"]

    def find_root(doc_id: str, depth: int = 0) -> str:
        if depth > 20:          # guard against loops
            return doc_id
        d  = email_docs.get(doc_id)
        if not d:
            return doc_id
        parent_mid = d.get("structured_fields", {}).get("in_reply_to") or ""
        if not parent_mid:
            return doc_id       # this IS the root
        parent_id  = mid_to_docid.get(clean_mid(parent_mid))
        if not parent_id or parent_id == doc_id:
            return doc_id
        return find_root(parent_id, depth + 1)

    for d in docs:
        if d["file_type"] == "email":
            d["thread_id"] = find_root(d["doc_id"])
        else:
            d["thread_id"] = None

    return docs


# ── Privacy defaults ──────────────────────────────────────────────────────────

def apply_privacy_defaults(doc: dict) -> dict:
    doc.setdefault("sensitivity_level", "internal")
    doc.setdefault("permitted_roles",   ["*"])
    doc.setdefault("owner_team",        "Strategic Oversight")
    return doc


# ── Master enrichment function ────────────────────────────────────────────────

def enrich_rule_based(doc: dict) -> dict:
    """
    Adds all rule-based metadata fields to a parsed doc.
    Call this per-document immediately after parsing.
    Thread reconstruction requires a separate second pass (reconstruct_email_threads).
    """
    doc["event_date"]        = extract_event_date(doc)
    doc["author"]            = extract_author(doc)
    doc["contributors"]      = extract_contributors(doc)
    doc["document_version"]  = extract_document_version(doc)
    doc["approval_status"]   = extract_approval_status(doc)
    doc["references_docs"]   = extract_references_docs(doc)
    doc["thread_id"]         = None   # filled by reconstruct_email_threads()

    # Gemini will fill these in Step 2
    doc["topics"]            = []
    doc["project_phase"]     = None

    apply_privacy_defaults(doc)
    return doc
