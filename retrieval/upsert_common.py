"""Shared helpers for the two upsert scripts (configs / prose collections)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from tqdm import tqdm

from .embeddings import embed_texts

PINECONE_METADATA_TEXT_CAP = 20_000  # Pinecone's per-vector metadata limit is 40KB; leave headroom
UPSERT_BATCH_SIZE = 100


def load_jsonl(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def sanitize_metadata(meta: dict, text: str) -> dict:
    """Pinecone metadata values must be str / number / bool / list[str].
    Drop Nones, stringify anything else, and carry the chunk text itself
    (truncated) so retrieval results are self-contained for generation."""
    clean: dict = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        elif isinstance(v, list):
            clean[k] = [str(x) for x in v]
        else:
            clean[k] = str(v)
    clean["text"] = text[:PINECONE_METADATA_TEXT_CAP]
    return clean


def upsert_collection(index, files: list[Path], collection_name: str) -> int:
    total = 0
    for path in files:
        if not path.exists():
            print(f"  [skip] {path} does not exist (run its ingestion script first)")
            continue
        chunks = list(load_jsonl(path))
        print(f"Embedding + upserting {len(chunks)} chunks from {path.name} into {collection_name} ...")
        for i in tqdm(range(0, len(chunks), UPSERT_BATCH_SIZE), desc=path.name):
            batch = chunks[i : i + UPSERT_BATCH_SIZE]
            vectors = embed_texts([c["text"] for c in batch])
            payload = [
                {"id": c["id"], "values": vec, "metadata": sanitize_metadata(c["metadata"], c["text"])}
                for c, vec in zip(batch, vectors)
            ]
            index.upsert(vectors=payload)
            total += len(payload)
    return total
