"""
Step 4a — Query Router

Classifies an incoming query into one of 6 types using keyword/pattern matching.
No LLM call — fast, deterministic, testable.

Query types:
  causal_trace        why/reason/changed/decided
  contributor_profile person name + did/contributed/worked/role
  conflict_detect     conflict/contradiction/disagree/mismatch
  audit_chain         audit/compliance/evidence/provenance/traceability
  onboarding          new/start/read first/understand/overview
  general             fallback
"""

import re
from dataclasses import dataclass

# ── Known people — derived from the single source of truth in metadata_rules ──

from metadata_rules import CANONICAL_NAMES

# Only keep short-name keys (not email addresses) for query matching
KNOWN_PEOPLE = {k for k in CANONICAL_NAMES if "@" not in k}

# ── Signal patterns per query type ────────────────────────────────────────────

PATTERNS = {
    "causal_trace": [
        r'\bwhy\b', r'\breason\b', r'\bbecause\b',
        r'\bwhat caused\b', r'\bhow did .+ change\b',
        r'\bwhat led\b', r'\bwhat triggered\b',
        r'\bdecided\b', r'\bchanged\b', r'\bmodified\b',
        r'\bjustif', r'\bmotivat',
    ],
    "contributor_profile": [
        r'\bwhat did \w+ (do|contribute|work|build|create|write|develop)\b',
        r'\bwhat (has|did|was) \w+.{0,20}(role|contribut|involv|respon)\b',
        r'\b\w+\'s (role|contribut|work|involvement)\b',
        r'\bwho (wrote|built|created|developed|coded|authored|designed)\b',
        r'\btell me about \w+\b',
        r'\bwhat (is|was) \w+\'s\b',
    ],
    "conflict_detect": [
        r'\bconflicts?\b', r'\bcontradictions?\b', r'\bdisagrees?\b',
        r'\bmismatch\b', r'\binconsisten', r'\bdiscrepan',
        r'\boppos', r'\bdisput', r'\bpush.?back\b',
        r'\bdifference between\b', r'\bvs\.?\b', r'\bversus\b',
        r'\bany .{0,20}(conflict|contradict|inconsist)\b',
    ],
    "audit_chain": [
        r'\baudit\b', r'\bcomplian\b', r'\bevidence\b',
        r'\bprovenance\b', r'\btraceability\b', r'\btrail\b',
        r'\bregulat\b', r'\bdirective\b', r'\bpolicy\b',
        r'\bfour pillars\b', r'\biad\b', r'\bstephen\b',
        r'\bfull chain\b', r'\bshow.{0,10}chain\b',
    ],
    "org_lookup": [
        r'\bwho manages\b', r'\bwho (is|was) \w+.{0,10}manager\b',
        r'\breports? to\b', r'\breporting (line|structure|chain)\b',
        r'\borg(anization)? (chart|structure|hierarchy)\b',
        r'\bwho (is|was) in charge\b', r'\bwhat is \w+\'s (title|role|position)\b',
        r'\bwho does \w+ report\b', r'\bdirect reports?\b',
        r'\bteam structure\b', r'\bwho (leads|led) the (team|project)\b',
        r'\bwhat does .{0,30}team (do|handle|own|manage)\b',
        r'\bwho should i (talk|speak|go) to\b',
        r'\bwho (handles|owns|is responsible for|covers)\b',
        r'\bwhat (is|are) .{0,20}(scope|responsibilit)\b',
        r'\bwho (can|could) help\b', r'\bpoint of contact\b',
    ],
    "onboarding": [
        r'\bnew (person|employee|hire|member|joiner)\b',
        r'\bstart\b.*\bunderstand\b', r'\bunderstand\b.*\bstart\b',
        r'\bread first\b', r'\bread.{0,10}start\b',
        r'\boverview\b', r'\bsummary of the project\b',
        r'\bget up to speed\b', r'\bonboard\b',
        r'\bwhere (should|do) i start\b',
        r'\bintroduction\b',
    ],
}


@dataclass
class ClassificationResult:
    query_type:  str
    confidence:  str          # "high" | "medium" | "low"
    signals:     list[str]    # which patterns fired
    person_hint: str | None   # extracted person name if contributor_profile


def _extract_person(query: str) -> str | None:
    """Return canonical author name if a known person is found in query."""
    q = query.lower()
    for name in sorted(KNOWN_PEOPLE, key=len, reverse=True):  # longest first
        if name in q:
            return CANONICAL_NAMES.get(name)
    return None


def classify(query: str) -> ClassificationResult:
    q = query.lower().strip()

    scores: dict[str, list[str]] = {k: [] for k in PATTERNS}

    # Score each type
    for qtype, patterns in PATTERNS.items():
        for pat in patterns:
            if re.search(pat, q):
                scores[qtype].append(pat)

    # Contributor profile: boost if a known person is mentioned
    person = _extract_person(q)
    if person:
        scores["contributor_profile"].append(f"person_detected:{person}")

    # Pick winner
    best_type = max(scores, key=lambda t: len(scores[t]))
    best_signals = scores[best_type]

    if not best_signals:
        return ClassificationResult(
            query_type="general",
            confidence="low",
            signals=[],
            person_hint=None,
        )

    n = len(best_signals)
    confidence = "high" if n >= 3 else "medium" if n >= 1 else "low"

    # Tie-break: org_lookup wins over contributor_profile for org/hierarchy questions
    if person and scores["org_lookup"]:
        best_type = "org_lookup"
        best_signals = scores["org_lookup"]
        confidence = "high"
    # Tie-break: contributor_profile wins if a person is named (and no org signals)
    elif person and scores["contributor_profile"]:
        best_type = "contributor_profile"
        best_signals = scores["contributor_profile"]
        confidence = "high"

    return ClassificationResult(
        query_type=best_type,
        confidence=confidence,
        signals=best_signals,
        person_hint=person if best_type in ("contributor_profile", "org_lookup") else None,
    )


# ── Quick CLI test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    DEMO_QUESTIONS = [
        "Why was the geographic weight changed from 5% to 15%?",
        "What did Jason contribute technically to this project?",
        "Are there any conflicts or contradictions between documents?",
        "What should a new person read first to understand this project?",
        "Show the full compliance audit chain for the risk model.",
        "What is the role of ERAP in the streamlining filter?",
    ]

    print(f"{'Query':<55} {'Type':<22} {'Conf':<8} {'Signals'}")
    print("─" * 110)
    for q in DEMO_QUESTIONS:
        r = classify(q)
        print(f"{q[:54]:<55} {r.query_type:<22} {r.confidence:<8} {r.signals[:2]}")
