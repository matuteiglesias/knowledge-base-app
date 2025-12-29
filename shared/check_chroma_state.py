# # tools/debug_chroma.py
# from pathlib import Path
# import os

# print("ENV CHROMA_DIR:", os.environ.get("CHROMA_DIR"))
# print("ENV CHROMA_COLLECTION:", os.environ.get("CHROMA_COLLECTION"))

# try:
#     import chromadb
#     from chromadb.config import Settings
#     print("chromadb imported, version:", getattr(chromadb, "__version__", "unknown"))
# except Exception as e:
#     print("chromadb import failed:", e)
#     chromadb = None

# import logging

# logger = logging.getLogger(__name__)
# logger.addHandler(logging.NullHandler())

# import traceback, json, os
# from shared.chroma_client import get_client
# , list_collections, get_or_create_collection
# from shared.config import CHROMA_DIR


# # client = None
# # try:
# #     client = get_client(persist_directory=CHROMA_DIR, create_if_missing=False)
# # except Exception as e:
# #     print("get_client failed:", e)



# # print("client:", type(client))
# # try:
# #     cols = list_collections(client)
# #     print("collections:", json.dumps(cols))
# #     coll_name = os.environ.get("CHROMA_COLLECTION") or os.environ.get("COLLECTION_NAME") or "chunks"
# #     if client is not None:
# #         coll = get_or_create_collection(client, coll_name)
# #         try:
# #             res = coll.get(include=['documents','metadatas'])
# #             docs = res.get('documents') or []
# #             if docs and isinstance(docs[0], list):
# #                 docs = docs[0]
# #             print("sample_documents_len:", len(docs))
# #             if docs:
# #                 print("first_preview:", docs[0][:200])
# #         except Exception as e:
# #             print("coll.get failed:", e)
# # except Exception as e:
# #     print("list_collections error:", e)


# # def try_client_with_settings(persist_dir):
# #     try:
# #         s = Settings(chroma_db_impl="duckdb+parquet", persist_directory=str(persist_dir))
# #     except Exception:
# #         try:
# #             s = Settings(persist_directory=str(persist_dir))
# #         except Exception:
# #             s = None
# #     if s:
# #         try:
# #             c = chromadb.Client(settings=s)
# #             print("Client via Settings created:", type(c))
# #             return c
# #         except Exception as e:
# #             print("Client(Settings) failed:", e)
# #     return None

# # def try_client_direct(persist_dir):
# #     try:
# #         c = chromadb.Client()
# #         # some chroma versions accept persist_directory on init; try setting attribute if possible
# #         try:
# #             if hasattr(c, "persist_directory"):
# #                 print("client.persist_directory attribute exists:", getattr(c, "persist_directory"))
# #         except Exception:
# #             pass
# #         print("Client() created:", type(c))
# #         return c
# #     except Exception as e:
# #         print("Client() failed:", e)
# #         return None

# def list_collections_flex(client):
#     try:
#         if hasattr(client, "list_collections"):
#             print("list_collections():", client.list_collections())
#         if hasattr(client, "get_collection"):
#             # attempt to get collection object by name
#             name = os.environ.get("CHROMA_COLLECTION", "chunks")
#             try:
#                 coll = client.get_collection(name)
#                 print("get_collection(name) -> collection object:", coll)
#                 # if collection supports count/get, try a sample
#                 if hasattr(coll, "count"):
#                     print("collection.count():", coll.count())
#                 if hasattr(coll, "get"):
#                     try:
#                         print("collection.get(include=['ids']) ->", coll.get(include=["ids"]))
#                     except Exception as e:
#                         print("collection.get failed:", e)
#             except Exception as e:
#                 print("get_collection failed:", e)
#         # some versions return names via client.list_collections() as objects:
#         try:
#             names = [c.name if hasattr(c, "name") else str(c) for c in client.list_collections()]
#             print("derived collection names:", names)
#         except Exception:
#             pass
#     except Exception:
#         traceback.print_exc()

# def main():
#     CHROMA_DIR = Path(os.environ.get("CHROMA_DIR", "store/chroma"))
#     print("Trying clients with CHROMA_DIR:", CHROMA_DIR.resolve())

#     # 1) try Settings-based client
#     # client = None
#     # if chromadb is not None:
#     #     client = try_client_with_settings(CHROMA_DIR)
#     #     if client is None:
#     #         client = try_client_direct(CHROMA_DIR)
#     # else:
#     #     print("chromadb not importable; aborting")
#     #     return

#     client = get_client(persist_directory=Path(CHROMA_DIR))
#     logger.info("main(embed_runner) client type=%s persist_dir=%s", type(client), CHROMA_DIR)


#     if client is None:
#         print("client is None")
#         return
    
#     print("client type:", type(client))
#     list_collections_flex(client)
#     # show files present after trying to create client
#     print("CHROMA_DIR listing (after client init):")
#     for p in sorted(CHROMA_DIR.rglob("*")):
#         print(p, "-" , p.stat().st_size)
#     # Attempt to create a test collection and persist
#     try:
#         name = "dbg_collection_for_test"
#         print("Attempting to create or get collection:", name)
#         try:
#             coll = client.get_collection(name)
#             print("got existing coll:", coll)
#         except Exception:
#             try:
#                 coll = client.create_collection(name)
#                 print("created coll via create_collection:", coll)
#             except Exception as e:
#                 print("create_collection failed:", e)
#                 coll = None
#         if coll is not None:
#             try:
#                 coll.add(ids=["dbg-1"], documents=["hello dbg"], metadatas=[{"dbg": True}])
#                 print("added doc to collection")
#             except Exception as e:
#                 print("coll.add failed:", e)
#             # attempt to persist (if helper available)
#             try:
#                 if hasattr(client, "persist"):
#                     print("calling client.persist()")
#                     client.persist()
#                 else:
#                     print("client.persist() not available")
#             except Exception as e:
#                 print("client.persist() failed:", e)
#     except Exception:
#         traceback.print_exc()
#     print("Done.")

# if __name__ == "__main__":
#     main()
