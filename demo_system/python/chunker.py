"""
Step 3a — Document Chunking

Reads cache/enriched_docs.json, splits each document into chunks using
file-type-specific strategies, writes cache/chunks.json.

Chunking strategies:
  email           → one chunk per email (they're short)
  meeting_minutes → split by section marker, then sliding window
  word_doc        → sliding window 512w / 128 overlap
  sas_script      → one chunk per PROC/DATA block
  excel_sheet     → row groups with column headers prepended, 200w target
  csv             → row groups with column headers prepended, 200w target
  policy_doc      → split by numbered section, then sliding window 600w
  log_file        → sliding window 400w / 128 overlap
  powerpoint      → sliding window 400w / 128 overlap
"""

import json
import re
import sys
from pathlib import Path

from config import CACHE_DIR, CHUNK_SIZES, CHUNK_OVERLAP
from enricher import load_enriched_docs

# ── Token → word conversion (rough: 1 token ≈ 0.75 words) ───────────────────
def _tokens_to_words(tokens: int) -> int:
    return max(50, int(tokens * 0.75))

OVERLAP_WORDS = _tokens_to_words(CHUNK_OVERLAP)  # ~96 words

# ── Sliding window ────────────────────────────────────────────────────────────

def sliding_window(text: str, target_words: int, overlap_words: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + target_words, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.split()) >= 15:   # skip tiny trailing fragments
            chunks.append(chunk)
        if end >= len(words):
            break
        start += target_words - overlap_words
    return chunks if chunks else [text]


# ── File-type specific strategies ─────────────────────────────────────────────

def chunk_email(doc: dict) -> list[str]:
    """Emails are short — keep as one chunk. If long, slide with 300-word window."""
    text = doc.get("raw_text", "").strip()
    target = _tokens_to_words(CHUNK_SIZES["email"])
    words = text.split()
    if len(words) <= target * 1.5:
        return [text] if text else []
    return sliding_window(text, target, OVERLAP_WORDS)


def chunk_meeting_minutes(doc: dict) -> list[str]:
    """Split on section markers first, then slide if sections are large."""
    text = doc.get("raw_text", "").strip()
    target = _tokens_to_words(CHUNK_SIZES["meeting_minutes"])

    # Try splitting on common meeting section headers
    section_pattern = re.compile(
        r'\n(?=(?:AGENDA|ACTION ITEMS|ATTENDEES|DISCUSSION|DECISIONS|'
        r'NEXT STEPS|SUMMARY|OUTCOMES|KEY DECISIONS|---|={3,}|\d+\.\s+[A-Z]))',
        re.IGNORECASE
    )
    sections = [s.strip() for s in section_pattern.split(text) if s.strip()]

    if len(sections) <= 1:
        # No section markers — fall back to sliding window
        return sliding_window(text, target, OVERLAP_WORDS)

    # Merge short sections with the next one; slide long ones
    chunks = []
    buffer = ""
    for section in sections:
        combined = (buffer + "\n" + section).strip() if buffer else section
        if len(combined.split()) <= target * 1.4:
            buffer = combined
        else:
            if buffer:
                chunks.extend(sliding_window(buffer, target, OVERLAP_WORDS))
            buffer = section
    if buffer:
        chunks.extend(sliding_window(buffer, target, OVERLAP_WORDS))

    return chunks if chunks else [text]


def chunk_sas_script(doc: dict) -> list[str]:
    """One chunk per PROC/DATA block. Preserve comments above each block."""
    text = doc.get("raw_text", "").strip()
    if not text:
        return []

    # Split on PROC or DATA statements at line start
    block_pattern = re.compile(r'\n(?=(?:PROC |DATA )\w)', re.IGNORECASE)
    blocks = [b.strip() for b in block_pattern.split(text) if b.strip()]

    if len(blocks) <= 1:
        return [text]

    # Merge tiny blocks (< 15 words) with the next
    merged = []
    buffer = ""
    for block in blocks:
        combined = (buffer + "\n" + block).strip() if buffer else block
        if len(combined.split()) < 15:
            buffer = combined
        else:
            if buffer and len(buffer.split()) >= 15:
                merged.append(buffer)
            buffer = block
    if buffer:
        merged.append(buffer)

    return merged if merged else [text]


def chunk_excel(doc: dict) -> list[str]:
    """
    Excel raw_text has sheets separated by '=== Sheet: SheetName ==='.
    Split by sheet, then slide rows within each sheet. Always keep header row.
    """
    text = doc.get("raw_text", "").strip()
    target = _tokens_to_words(CHUNK_SIZES["excel_sheet"])

    sheet_pattern = re.compile(r'(=== Sheet: .+? ===)', re.IGNORECASE)
    parts = sheet_pattern.split(text)

    chunks = []
    current_sheet_header = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if sheet_pattern.match(part):
            current_sheet_header = part
        else:
            # Part is rows content — prepend sheet header to every sub-chunk
            lines = part.splitlines()
            col_header = lines[0] if lines else ""
            prefix = f"{current_sheet_header}\nColumns: {col_header}\n"

            sub_chunks = sliding_window(part, target, OVERLAP_WORDS)
            for sc in sub_chunks:
                # Only prepend prefix if not already there
                if not sc.startswith(current_sheet_header):
                    chunks.append(prefix + sc)
                else:
                    chunks.append(sc)

    return chunks if chunks else sliding_window(text, target, OVERLAP_WORDS)


def chunk_csv(doc: dict) -> list[str]:
    """Row groups with column headers prepended to each chunk."""
    text = doc.get("raw_text", "").strip()
    target = _tokens_to_words(CHUNK_SIZES["csv"])

    lines = text.splitlines()
    if not lines:
        return []

    header = lines[0]
    body_lines = lines[1:]

    if not body_lines:
        return [text]

    # Group rows into chunks; prepend header to each
    target_lines = max(5, target // 10)   # rough rows per chunk
    chunks = []
    for i in range(0, len(body_lines), target_lines):
        group = body_lines[i: i + target_lines]
        chunk = f"Columns: {header}\n" + "\n".join(group)
        if chunk.strip():
            chunks.append(chunk)

    return chunks if chunks else [text]


def chunk_policy_doc(doc: dict) -> list[str]:
    """Split on numbered section headers, then slide large sections."""
    text = doc.get("raw_text", "").strip()
    target = _tokens_to_words(CHUNK_SIZES["policy_doc"])

    section_pattern = re.compile(
        r'\n(?=(?:Section \d+|\d+\.\d*\s+[A-Z]|ARTICLE \d+|APPENDIX|ANNEX|PART \d+))',
        re.IGNORECASE
    )
    sections = [s.strip() for s in section_pattern.split(text) if s.strip()]

    if len(sections) <= 1:
        return sliding_window(text, target, OVERLAP_WORDS)

    chunks = []
    for section in sections:
        chunks.extend(sliding_window(section, target, OVERLAP_WORDS))

    return chunks if chunks else [text]


def chunk_generic(doc: dict, file_type: str) -> list[str]:
    """Sliding window for word_doc, log_file, powerpoint."""
    text = doc.get("raw_text", "").strip()
    size = CHUNK_SIZES.get(file_type) or 400
    target = _tokens_to_words(size)
    return sliding_window(text, target, OVERLAP_WORDS)


# ── Dispatcher ────────────────────────────────────────────────────────────────

CHUNKERS = {
    "email":           chunk_email,
    "meeting_minutes": chunk_meeting_minutes,
    "sas_script":      chunk_sas_script,
    "excel_sheet":     chunk_excel,
    "csv":             chunk_csv,
    "policy_doc":      chunk_policy_doc,
}

def chunk_document(doc: dict) -> list[str]:
    ft = doc.get("file_type", "word_doc")
    fn = CHUNKERS.get(ft)
    if fn:
        return fn(doc)
    return chunk_generic(doc, ft)


# ── Flatten metadata for ChromaDB (no lists, no None) ────────────────────────

def flatten_metadata(doc: dict, chunk_index: int, chunk_total: int, project_id: str = "") -> dict:
    """
    ChromaDB requires flat metadata: str | int | float | bool only.
    Convert lists to JSON strings, None to "".
    """
    def s(v) -> str:
        if v is None:
            return ""
        if isinstance(v, list):
            return json.dumps(v, ensure_ascii=False)
        return str(v)

    return {
        # Project scoping
        "project_id":        project_id,
        # Identity
        "doc_id":            s(doc.get("doc_id")),
        "source_path":       s(doc.get("source_path")),
        "file_type":         s(doc.get("file_type")),
        "source_folder":     s(doc.get("source_folder")),
        # Temporal
        "event_date":        s(doc.get("event_date")),
        # Authorship
        "author":            s(doc.get("author")),
        "contributors":      s(doc.get("contributors", [])),
        # Topical
        "topics":            s(doc.get("topics", [])),
        "project_phase":     s(doc.get("project_phase")),
        # Cross-document
        "thread_id":         s(doc.get("thread_id")),
        "references_docs":   s(doc.get("references_docs", [])),
        # Version / status
        "document_version":  s(doc.get("document_version")),
        "approval_status":   s(doc.get("approval_status")),
        # Privacy hook
        "sensitivity_level": s(doc.get("sensitivity_level", "internal")),
        "permitted_roles":   s(doc.get("permitted_roles", ["*"])),
        "owner_team":        s(doc.get("owner_team", "Strategic Oversight")),
        # Chunk position
        "chunk_index":       chunk_index,
        "chunk_total":       chunk_total,
        "parent_doc_id":     s(doc.get("doc_id")),
    }


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_chunking(verbose: bool = True) -> list[dict]:
    docs = load_enriched_docs()
    if not docs:
        raise FileNotFoundError("enriched_docs.json not found — run Step 2 first")

    docs = [d for d in docs if d.get("enrichment_status") == "done"]

    all_chunks = []
    skipped = 0

    for doc in docs:
        texts = chunk_document(doc)
        texts = [t.strip() for t in texts if t.strip()]

        if not texts:
            skipped += 1
            continue

        total = len(texts)
        for i, text in enumerate(texts):
            chunk_id = f"{doc['doc_id']}_c{i:03d}"
            meta = flatten_metadata(doc, chunk_index=i, chunk_total=total)
            all_chunks.append({
                "chunk_id":  chunk_id,
                "text":      text,
                "metadata":  meta,
            })

    out_path = CACHE_DIR / "chunks.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    if verbose:
        from collections import Counter
        ft_counts = Counter(c["metadata"]["file_type"] for c in all_chunks)
        print(f"Total chunks : {len(all_chunks)}")
        print(f"Skipped docs : {skipped}")
        print(f"Avg per doc  : {len(all_chunks)/max(len(docs),1):.1f}")
        print(f"\nBy file type:")
        for ft, cnt in sorted(ft_counts.items()):
            print(f"  {ft:20s}: {cnt}")
        print(f"\nOutput: {out_path}")

    return all_chunks


def load_chunks() -> list[dict]:
    path = CACHE_DIR / "chunks.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_chunking_status() -> dict:
    chunks = load_chunks()
    if not chunks:
        return {"status": "not_run", "total": 0}
    from collections import Counter
    ft_counts = Counter(c["metadata"]["file_type"] for c in chunks)
    doc_ids   = {c["metadata"]["doc_id"] for c in chunks}
    return {
        "status":        "ok",
        "total_chunks":  len(chunks),
        "total_docs":    len(doc_ids),
        "by_file_type":  dict(ft_counts),
    }


if __name__ == "__main__":
    verbose = "--quiet" not in sys.argv
    run_chunking(verbose=verbose)
