"""
Quick test runner for all 7 demo queries.
Prints full answer + source breakdown for each.

Usage:
    python3 test_queries.py              # run all 7
    python3 test_queries.py 3            # run question #3 only
    python3 test_queries.py --no-org     # skip org question
"""

import sys
from router import classify
from retriever import retrieve
from generator import generate

QUESTIONS = [
    "Why was the geographic weight changed from 5% to 15%?",
    "What did Jason contribute technically to this project?",
    "Are there any conflicts or contradictions between documents?",
    "What should a new person read first to understand this project?",
    "Show the full compliance audit chain for the risk model.",
    "What is the role of ERAP in the streamlining filter?",
    "Who manages Jason and what is his scope?",
]

DIVIDER = "═" * 72


def run_question(index: int, query: str):
    print(f"\n{DIVIDER}")
    print(f"  Q{index}: {query}")
    print(DIVIDER)

    cl     = classify(query)
    ret    = retrieve(query, cl, n=8)
    resp   = generate(query, ret)

    print(f"  Type     : {resp['query_type']}  |  "
          f"Model : {resp['model_used']}  |  "
          f"Retrieved : {resp['retrieval_count']} chunks")
    print(f"  Cited    : {resp['cited_sources']}")
    print()
    print(resp["answer"])
    print()

    cited     = [s for s in resp["all_sources"] if s.get("cited")]
    uncited   = [s for s in resp["all_sources"] if not s.get("cited")]

    if cited:
        print("  ── Cited sources ──────────────────────────────────────────────")
        for s in cited:
            print(f"  ✓  {s['doc_id']:45s}  {s.get('file_type',''):18s}  {s.get('event_date','')}")
            print(f"     {s['excerpt'][:120].strip()}...")
            print()

    if uncited:
        print("  ── Retrieved but not cited ────────────────────────────────────")
        for s in uncited:
            print(f"     {s['doc_id']:45s}  {s.get('file_type',''):18s}  {s.get('event_date','')}")


def main():
    args = sys.argv[1:]

    # Single question by number
    if args and args[0].isdigit():
        idx = int(args[0])
        if 1 <= idx <= len(QUESTIONS):
            run_question(idx, QUESTIONS[idx - 1])
        else:
            print(f"Question number must be 1–{len(QUESTIONS)}")
        return

    # All questions
    skip_org = "--no-org" in args
    questions = QUESTIONS[:-1] if skip_org else QUESTIONS

    for i, q in enumerate(questions, 1):
        run_question(i, q)

    print(f"\n{DIVIDER}")
    print(f"  Done — {len(questions)} questions tested")
    print(DIVIDER)


if __name__ == "__main__":
    main()
