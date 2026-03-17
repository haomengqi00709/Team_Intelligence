"""
Step 3b — Embedding + ChromaDB Index

Reads cache/chunks.json, embeds each chunk with Gemini text-embedding-004,
stores vectors + metadata in ChromaDB.

Resume-safe: chunks already in the collection are skipped on re-run.
"""

import json
import sys
import time
from collections import Counter

import chromadb
import google.generativeai as genai

from config import (
    CACHE_DIR, CHROMA_DIR, CHROMA_COLLECTION,
    GEMINI_API_KEY, EMBEDDING_MODEL,
)
from chunker import load_chunks, run_chunking, get_chunking_status

genai.configure(api_key=GEMINI_API_KEY)

# ── ChromaDB client ───────────────────────────────────────────────────────────

def get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


# ── Embedding call ────────────────────────────────────────────────────────────

def embed_text(text: str) -> list[float] | None:
    try:
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
        )
        return result["embedding"]
    except Exception as e:
        print(f"    [EMBED ERROR] {e}")
        return None


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_indexing(verbose: bool = True) -> dict:
    chunks = load_chunks()
    if not chunks:
        raise FileNotFoundError("chunks.json not found — run Step 3a (chunking) first")

    collection = get_collection()

    # Find already-indexed chunk_ids (resume-safe)
    existing = set(collection.get(include=[])["ids"])

    to_index = [c for c in chunks if c["chunk_id"] not in existing]

    if not to_index:
        if verbose:
            print("All chunks already indexed. Nothing to do.")
        return get_index_stats()

    if verbose:
        print(f"Indexing {len(to_index)} chunks ({len(existing)} already done)")
        print(f"Model: {EMBEDDING_MODEL}\n")

    # Batch size for ChromaDB adds (keep small to stay within memory)
    BATCH = 50
    done = 0
    failed = 0

    for i, chunk in enumerate(to_index, 1):
        if verbose and i % 10 == 1:
            print(f"  [{i:4}/{len(to_index)}] embedding...", end="\r", flush=True)

        embedding = embed_text(chunk["text"])
        if embedding is None:
            failed += 1
            time.sleep(1.0)
            continue

        try:
            collection.add(
                ids=[chunk["chunk_id"]],
                embeddings=[embedding],
                documents=[chunk["text"]],
                metadatas=[chunk["metadata"]],
            )
            done += 1
        except Exception as e:
            print(f"\n    [CHROMA ERROR] {chunk['chunk_id']}: {e}")
            failed += 1

        # Polite rate limiting
        time.sleep(0.1)

    if verbose:
        print(f"\n{'─'*60}")
        print(f"Indexed  : {done}")
        print(f"Failed   : {failed}")
        print(f"Total in collection: {collection.count()}")

    return get_index_stats()


# ── Stats & inspection ────────────────────────────────────────────────────────

def get_index_stats() -> dict:
    try:
        collection = get_collection()
        total = collection.count()
        if total == 0:
            return {"status": "empty", "total_chunks": 0}

        # Sample metadata to build breakdown (ChromaDB doesn't aggregate)
        sample = collection.get(limit=min(total, 500), include=["metadatas"])
        ft_counts: dict[str, int] = {}
        doc_ids: set[str] = set()
        for meta in sample["metadatas"]:
            ft = meta.get("file_type", "unknown")
            ft_counts[ft] = ft_counts.get(ft, 0) + 1
            doc_ids.add(meta.get("doc_id", ""))

        return {
            "status":       "ok",
            "total_chunks": total,
            "total_docs":   len(doc_ids),
            "by_file_type": ft_counts,
            "collection":   CHROMA_COLLECTION,
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def raw_search(
    query: str,
    n: int = 10,
    filter_meta: dict | None = None,
) -> list[dict]:
    """
    Pure vector search — no LLM. Used for Step 3 testing and Step 4 retrieval.
    filter_meta: ChromaDB where clause, e.g. {"file_type": "email"}
    """
    collection = get_collection()

    query_embedding = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=query,
        task_type="RETRIEVAL_QUERY",
    )["embedding"]

    kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results":        min(n, collection.count()),
        "include":          ["documents", "metadatas", "distances"],
    }
    if filter_meta:
        kwargs["where"] = filter_meta

    results = collection.query(**kwargs)

    hits = []
    for chunk_id, doc, meta, dist in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "chunk_id":    chunk_id,
            "score":       round(1 - dist, 4),   # cosine → similarity
            "text":        doc,
            "doc_id":      meta.get("doc_id"),
            "file_type":   meta.get("file_type"),
            "author":      meta.get("author"),
            "event_date":  meta.get("event_date"),
            "project_phase": meta.get("project_phase"),
            "topics":      meta.get("topics"),
            "chunk_index": meta.get("chunk_index"),
            "chunk_total": meta.get("chunk_total"),
        })

    return hits


# ── Full Step 3 runner (chunk + index) ────────────────────────────────────────

def run_step3(verbose: bool = True) -> dict:
    """Run chunking then indexing in sequence."""
    if verbose:
        print("=== Step 3a: Chunking ===")
    run_chunking(verbose=verbose)

    if verbose:
        print("\n=== Step 3b: Indexing ===")
    return run_indexing(verbose=verbose)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    verbose = "--quiet" not in sys.argv

    if mode == "chunk":
        run_chunking(verbose=verbose)
    elif mode == "index":
        run_indexing(verbose=verbose)
    elif mode == "search" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        print(f"Query: {query}\n")
        hits = raw_search(query, n=5)
        for h in hits:
            print(f"[{h['score']:.3f}] {h['doc_id']} ({h['file_type']}) — {h['text'][:120]}...")
    else:
        run_step3(verbose=verbose)
