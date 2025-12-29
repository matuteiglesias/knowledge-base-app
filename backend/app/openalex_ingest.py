# # backend/app/openalex_ingest.py
# import json
# import re
# from typing import Dict, List, Any
# from shared.chroma_helpers import add_paper, add_chunk
# from backend.app.chunks_fs import write_chunks_jsonl

# # normalize id string for chunk id friendly
# def slugify_id(s: str) -> str:
#     return re.sub(r'[^A-Za-z0-9\-_\.]', '-', s)

# def parse_openalex_result(ret: Dict[str, Any]) -> List[Dict[str, Any]]:
#     """
#     Parse an OpenAlex-like result (structure like `ret1`) into minimal paper dicts.
#     Returns list of paper dicts with fields: id, title, has_abstract, source, year, authors, raw_row
#     """
#     header = ret["results"]["header"]
#     rows = ret["results"]["body"]
#     papers = []

#     # Build index: header_idx_by_key
#     key_to_index = { h["key"]: i for i, h in enumerate(header) }

#     for row in rows:
#         # helper to fetch a cell by header key safely
#         def cell_for(key):
#             idx = key_to_index.get(key)
#             return row[idx] if idx is not None and idx < len(row) else None

#         # extract fields
#         # id & title
#         id_cell = cell_for("ids.openalex")
#         paper_id = None
#         title = None
#         if id_cell and id_cell.get("type") == "entity" and id_cell.get("value"):
#             v = id_cell["value"]
#             paper_id = v.get("id") or v.get("display_name")
#             title = v.get("display_name") or title

#         # has_abstract
#         has_abs_cell = cell_for("has_abstract")
#         has_abstract = bool(has_abs_cell.get("value")) if has_abs_cell else False

#         # source
#         source_cell = cell_for("primary_location.source.id")
#         source_name = None
#         if source_cell and source_cell.get("type") == "entity" and source_cell.get("value"):
#             source_name = source_cell["value"].get("display_name") or None

#         # year
#         year_cell = cell_for("publication_year")
#         year = year_cell.get("value") if (year_cell and year_cell.get("type") == "number") else None

#         # authors
#         authors_cell = cell_for("authorships.author.id")
#         authors = []
#         if authors_cell and authors_cell.get("isList"):
#             for author in authors_cell.get("value", []) or []:
#                 authors.append({"id": author.get("id"), "display_name": author.get("display_name")})
#         elif authors_cell and authors_cell.get("type") == "entity":
#             v = authors_cell.get("value")
#             if v:
#                 authors.append({"id": v.get("id"), "display_name": v.get("display_name")})

#         # fallback title if missing
#         if not title:
#             # try find an alternative in row cells with display_name
#             for cell in row:
#                 if isinstance(cell, dict) and cell.get("type") == "entity" and cell.get("value"):
#                     title = title or cell["value"].get("display_name")
#         # final fallback
#         title = title or "unknown title"

#         paper = {
#             "id": paper_id or title,
#             "title": title,
#             "has_abstract": has_abstract,
#             "source": source_name,
#             "year": year,
#             "authors": authors,
#             "raw_row": row
#         }
#         papers.append(paper)
#     return papers

# def ingest_openalex_result_to_chroma(ret: Dict[str, Any], embed_fn):
#     """
#     Convert ret1-like dict to Chroma-compatible papers + chunk JSONL and add into Chroma.
#     embed_fn(text) -> list[float] embeddings
#     """
#     parsed = parse_openalex_result(ret)
#     for p in parsed:
#         paper_id = p["id"]
#         # make safe chunk id
#         chunk_id = f"chunk-{slugify_id(paper_id)}-0000"
#         # choose chunk text: ideally you have abstract text in the raw data;
#         # since ret1 example doesn't include abstract text, we use title as fallback
#         # If you have an abstract field in `raw_row`, adapt this code to extract it.
#         chunk_text = None

#         # attempt to find abstract text in raw_row (some datasets include it in other columns)
#         for cell in p["raw_row"]:
#             if isinstance(cell, dict) and cell.get("type") == "string":
#                 chunk_text = cell.get("value")
#                 break

#         if not chunk_text:
#             # fallback to title
#             chunk_text = p["title"]

#         # write chunk jsonl (one chunk for now)
#         write_chunks_jsonl(paper_id, [{
#             "id": chunk_id,
#             "text": chunk_text,
#             "chunk_index": 0
#         }])

#         # compute embedding for preview and chunk
#         emb = embed_fn(chunk_text)

#         # Add paper (we compute a trivial paper-level embedding by using chunk embedding)
#         paper_meta = {
#             "title": p["title"],
#             "has_abstract": p["has_abstract"],
#             "source": p["source"],
#             "year": p["year"],
#             "authors": p["authors"]
#         }
#         add_paper(paper_id, paper_meta, embedding=emb)

#         # Add chunk to Chroma (preview_text is short; use first 300 chars)
#         preview = chunk_text[:300]
#         chunk_meta = {
#             "paper_id": paper_id,
#             "chunk_index": 0
#         }
#         add_chunk(chunk_id, paper_id, preview, chunk_meta, emb)

#     return [p["id"] for p in parsed]

# # Example usage:
# if __name__ == "__main__":
#     # load ret1 from file or string
#     with open("examples/ret1.json", "r", encoding="utf-8") as f:
#         ret = json.load(f)

#     # define a small embed_fn for dev (replace with your embed function)
#     def embed_fn(text: str):
#         # if you have an embed service, use it; for dev return a fixed-length zero vector
#         return [0.0] * 768

#     ids = ingest_openalex_result_to_chroma(ret, embed_fn)
#     print("ingested papers:", ids)
