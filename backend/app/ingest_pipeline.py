# # backend/app/ingest_pipeline.py

# """
# Orchestrates ingestion:
# - Saves chunks to FS
# - Embeds chunk texts
# - Pushes chunks to Chroma (with metadata)
# - Computes & stores paper-level metadata + embedding
# """

# from typing import List, Dict
# from backend.app import papers_fs, papers_fs
# from pipeline.embedding.engine import embed_text_batch
# from shared.chroma_helpers import (
#     get_or_create_collection, get_client,
#     serialize_metadata,
# )


# from shared.config import CHROMA_PAPERS_COLL, CHROMA_CHUNKS_COLL


# def ingest(records: List[Dict], paper_meta: Dict):
#     paper_id = paper_meta["paper_id"]
#     title = paper_meta.get("title", "")
#     authors = paper_meta.get("authors", [])

#     # -----------------------
#     # 1) Save to file system
#     # -----------------------
#     chunks_fs.write_chunks_jsonl(paper_id, [
#         {"id": r["chunk_id"], "text": r["text"], "chunk_index": r["chunk_index"]}
#         for r in records
#     ])
#     papers_fs.save_paper_metadata_to_fs(paper_id, {
#         **paper_meta,
#         "n_chunks": len(records),
#         "full_text_uri": f"store/chunks/{paper_id}.jsonl"
#     })

#     # -----------------------
#     # 2) Embed chunk texts
#     # -----------------------
#     texts = [r["text"] for r in records]
#     embeddings = embed_text_batch(texts)

#     # -----------------------
#     # 3) Push chunk-level info to Chroma
#     # -----------------------
#     # client = make_chroma_client()
#     chunk_coll = get_or_create_collection(client, name = CHROMA_CHUNKS_COLL)
#     # chunk_coll = get_or_create_collection(CHROMA_CHUNKS_COLL)
#     chunk_coll.add(
#         ids=[r["chunk_id"] for r in records],
#         documents=[t[:300] for t in texts],
#         embeddings=embeddings,
#         metadatas=[
#             serialize_metadata({
#                 "paper_id": paper_id,
#                 "level": r.get("level"),
#                 "header_path": r.get("header_path"),
#                 "pages": r.get("pages"),
#                 # "bboxes": r.get("bboxes"),
#                 "chunk_index": r.get("chunk_index"),
#                 "parent_chunk_id": r.get("parent_chunk_id"),
#                 "full_text_uri": f"store/chunks/{paper_id}.jsonl"
#             }) for r in records
#         ]
#     )

#     # -----------------------
#     # 4) Push paper-level info to Chroma
#     # -----------------------
#     # client = make_chroma_client()
#     client = get_client(persist_directory=Path(args.chroma_dir), create_if_missing=True)
#     paper_coll = get_or_create_collection(CHROMA_PAPERS_COLL)
#     paper_coll.add(
#         ids=[paper_id],
#         documents=[title[:300]],
#         embeddings=[_mean_embedding(embeddings)],
#         metadatas=[serialize_metadata({
#             "title": title,
#             "authors": authors,
#             "n_chunks": len(records),
#             "full_text_uri": f"store/chunks/{paper_id}.jsonl"
#         })]
#     )


# def _mean_embedding(embs: List[List[float]]) -> List[float]:
#     if not embs:
#         return []
#     dim = len(embs[0])
#     out = [0.0] * dim
#     for e in embs:
#         for i in range(dim):
#             out[i] += float(e[i])
#     return [x / len(embs) for x in out]



# 🧨 Moderate complexity batch operations:

# persist_records_to_store_and_chroma:
# ❌ Violates separation of concerns. Handles:

# File system write

# Embedding

# Preview extraction

# Fallbacks

# Aggregation

# Vector insertion

# >>>>


# def persist_records_to_store_and_chroma(records: list[dict], title: str = None, authors: list = None, chroma_dir: str | None = None):
#     """
#     Persist chunk records into:
#       - store/chunks/<paper_id>.jsonl (full text)
#       - Chroma chunks collection (preview + metadata + embeddings)
#       - Chroma papers collection (one doc with small metadata + avg embedding)
#     records: list of dicts with keys chunk_id, paper_id, text, pages, bboxes, parent_chunk_id, level, header_path
#     title/authors: optional paper-level metadata (from parsed TEI)
#     chroma_dir: optional, path to persist chroma
#     """
#     from collections import defaultdict
#     grouped = defaultdict(list)
#     for r in records:
#         grouped[r["paper_id"]].append(r)

#     for paper_id, recs in grouped.items():
#         # ensure stable ordering
#         recs = sorted(recs, key=lambda x: x.get("chunk_index", 0))
#         # 1) Write full chunk JSONL (one file per paper)
#         jsonl_chunks = []
#         for idx, r in enumerate(recs):
#             jsonl_chunks.append({
#                 "id": r["chunk_id"],
#                 "text": r.get("text", "") or "",
#                 "chunk_index": r.get("chunk_index", idx)
#             })
#         # use shared helper if available
#         try:
#             if write_chunks_jsonl is not None:
#                 write_chunks_jsonl(paper_id, jsonl_chunks)
#                 jsonl_path = f"store/chunks/{paper_id}.jsonl"

#         #     else:
#         #         jsonl_path = _ensure_write_chunks_jsonl(paper_id, jsonl_chunks)
#         except Exception:
#             jsonl_path = _ensure_write_chunks_jsonl(paper_id, jsonl_chunks)


#         # save_paper_metadata_to_fs(paper_metadata["paper_id"], paper_metadata)  # TODO


#         # 2) Compute embeddings per chunk and prepare Chroma adds
#         chunk_embeddings = []
#         chunk_previews = []
#         for r in recs:
#             cid = r["chunk_id"]
#             text = r.get("text", "") or ""
#             emb = None
#             try:
#                 emb = get_embed(cid, text)  # uses cached_embed or fallback
#             except Exception:
#                 emb = get_embed(cid, text)  # robust fallback

#             # normalize embedding to plain python list
#             try:
#                 emb_list = emb.tolist() if hasattr(emb, "tolist") else list(emb)
#             except Exception:
#                 # if embedding not iterable, create a tiny deterministic vector
#                 import hashlib
#                 h = hashlib.sha1(text.encode("utf8")).hexdigest()
#                 emb_list = [int(h[i:i+4], 16) % 1000 / 1000.0 for i in range(0, 32, 4)]

#             # preview (first 300 chars)
#             preview = (text or "")[:300]
#             meta = {
#                 "paper_id": paper_id,
#                 "chunk_index": r.get("chunk_index", 0),
#                 "level": r.get("level"),
#                 "header_path": r.get("header_path"),
#                 "pages": r.get("pages"),
#                 "bboxes": r.get("bboxes"),
#                 "full_text_uri": jsonl_path,  # where to find full text
#             }

#             # if you have shared chroma helpers use them, otherwise try using in-file upsert
#             if HAS_CHROMA and HAS_SHARED_CHROMA_HELPERS:
#                 add_chunk(r["chunk_id"], paper_id, preview, meta, emb_list)
#             else:
#                 # fallback: call the in-file upsert (coll.add) implementation if present
#                 try:
#                     # `upsert_records_to_chroma` may exist in this file (your current implementation)
#                     upsert_records_to_chroma([r], collection_name="chunks", chroma_dir=chroma_dir)
#                 except Exception:
#                     # best-effort: print so you can debug
#                     print("WARNING: could not add chunk to chroma for", r["chunk_id"])
#             chunk_embeddings.append(emb_list)
#             chunk_previews.append(preview)

#         # 3) Create a small paper-level doc in Chroma (papers collection)
#         # derive paper metadata
#         paper_meta = {
#             "title": title or (recs[0].get("header_path",[None])[0] if recs and recs[0].get("header_path") else None),
#             "authors": authors or [],
#             "full_text_uri": jsonl_path,
#             "n_chunks": len(recs),
#         }
#         # compute mean embedding
#         try:
#             # average element-wise
#             dim = len(chunk_embeddings[0]) if chunk_embeddings else 0
#             avg = [0.0] * dim
#             for emb in chunk_embeddings:
#                 for i in range(dim):
#                     avg[i] += float(emb[i])
#             if chunk_embeddings:
#                 avg = [x / len(chunk_embeddings) for x in avg]
#             else:
#                 avg = None
#         except Exception:
#             avg = None

#         # add paper doc
#         if HAS_CHROMA and HAS_SHARED_CHROMA_HELPERS:
#             # ensure paper id is string-friendly
#             add_paper(paper_id, paper_meta, embedding=avg)
#         else:
#             try:
#                 # fallback: add a single chunk to a `papers` collection using the first preview
#                 if avg is None and chunk_previews:
#                     emb_to_use = chunk_embeddings[0] if chunk_embeddings else None
#                 else:
#                     emb_to_use = avg
#                 upsert_records_to_chroma([{
#                     "chunk_id": f"paper-{paper_id}",
#                     "paper_id": paper_id,
#                     "text": (paper_meta.get("title") or "")[:300],
#                     "pages": None,
#                     "bboxes": None,
#                     "header_path": [paper_meta.get("title")]
#                 }], collection_name="papers", chroma_dir=chroma_dir)
#             except Exception:
#                 print("WARNING: could not add paper doc to chroma for", paper_id)

#     # persist client if available
#     try:
#         if HAS_SHARED_CHROMA_HELPERS:
#             c = get_client()
#             try:
#                 c.persist()
#             except Exception:
#                 pass
#     except Exception:
#         pass


