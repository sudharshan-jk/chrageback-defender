"""Retrieval over the reason-code corpus.

Uses ChromaDB (local, persistent) with sentence-transformers embeddings.
Cache the collection on disk so we only embed once.
"""
import json
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

CORPUS_PATH = Path("corpus/reason_codes.json")
CHROMA_DIR = Path("data/chroma")
COLLECTION_NAME = "reason_codes"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # small, fast, local, ~90MB


def _get_collection() -> chromadb.Collection:
    """Get or create the persistent Chroma collection with our embedding function."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
    )


def build_index(force: bool = False) -> int:
    """Embed and store all reason codes. Idempotent unless force=True."""
    collection = _get_collection()

    if collection.count() > 0 and not force:
        return collection.count()

    if force and collection.count() > 0:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        client.delete_collection(COLLECTION_NAME)
        collection = _get_collection()

    entries = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    ids = [f"{e['network']}_{e['code']}" for e in entries]
    documents = [
        f"{e['title']}. {e['short_description']} "
        f"Required evidence: {', '.join(e['required_evidence'])}."
        for e in entries
    ]
    metadatas = [
        {
            "code": e["code"],
            "network": e["network"],
            "category": e["category"],
            "title": e["title"],
            "deadline_days": e["deadline_days"],
        }
        for e in entries
    ]

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return collection.count()


def retrieve(query: str, k: int = 3) -> list[dict[str, Any]]:
    """Return the top-k reason codes matching the query, with full entry data."""
    collection = _get_collection()
    if collection.count() == 0:
        raise RuntimeError("Index is empty. Run build_index() first.")

    results = collection.query(query_texts=[query], n_results=k)

    entries = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    by_id = {f"{e['network']}_{e['code']}": e for e in entries}

    hits = []
    for hit_id, distance in zip(results["ids"][0], results["distances"][0]):
        hit = by_id[hit_id].copy()
        hit["_distance"] = distance
        hits.append(hit)
    return hits


if __name__ == "__main__":
    print("building index...")
    n = build_index(force=True)
    print(f"indexed {n} entries")

    print("\ntest query: 'customer says they never got the item'")
    for i, hit in enumerate(retrieve("customer says they never got the item", k=3), 1):
        print(f"  {i}. {hit['network']} {hit['code']} — {hit['title']}  (dist={hit['_distance']:.3f})")

    print("\ntest query: 'cardholder claims the charge was not authorized'")
    for i, hit in enumerate(retrieve("cardholder claims the charge was not authorized", k=3), 1):
        print(f"  {i}. {hit['network']} {hit['code']} — {hit['title']}  (dist={hit['_distance']:.3f})")

    print("\ntest query: 'subscription was cancelled but still charged'")
    for i, hit in enumerate(retrieve("subscription was cancelled but still charged", k=3), 1):
        print(f"  {i}. {hit['network']} {hit['code']} — {hit['title']}  (dist={hit['_distance']:.3f})")