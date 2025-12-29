# shared/config.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# -- load .env if present at repo root --
root = Path(__file__).resolve().parents[1]   # assumes shared/ is one level under repo root
env_path = root / ".env"
if env_path.exists():
    # do not override existing envs
    load_dotenv(dotenv_path=str(env_path), override=False)

def _p(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(key)
    return v if v is not None else default

GROBID_URL = _p("GROBID_URL", "http://localhost:8070/api/processFulltextDocument")


# ---------------------------------------------------------------------------
# Paths (canonical)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(_p("PYTHONPATH", str(root))).expanduser().resolve()

CHROMA_DIR = Path(_p("CHROMA_DIR", str(REPO_ROOT / "store" / "chroma"))).expanduser().resolve()
CHUNKS_DIR = Path(_p("CHUNKS_DIR", str(REPO_ROOT / "store" / "chunks"))).expanduser().resolve()
PAPERS_DIR = Path(_p("PAPERS_DIR", str(REPO_ROOT / "store" / "papers"))).expanduser().resolve()
STORE_SUMMARIES_DIR = Path(_p("STORE_SUMMARIES_DIR", str(REPO_ROOT / "store" / "summaries"))).expanduser().resolve()
EMBED_CACHE_DB = Path(_p("EMBED_CACHE_DB", str(REPO_ROOT / "store" / "emb_cache.sqlite"))).expanduser().resolve()
SUMMARY_DB = Path(_p("SUMMARY_DB", str(CHROMA_DIR / "summary_jobs.sqlite"))).expanduser().resolve()


# configuration



# ensure directories exist (best-effort)
for _dir in (CHROMA_DIR, CHUNKS_DIR, PAPERS_DIR):
    try:
        _dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Collections / embedding config
# ---------------------------------------------------------------------------
CHROMA_CHUNKS_COLL = _p("CHROMA_CHUNKS_COLL", "chunks")
CHROMA_PAPERS_COLL = _p("CHROMA_PAPERS_COLL", "papers")

EMBED_ADAPTER = _p("EMBED_ADAPTER", "placeholder")   # placeholder | jina | llamaindex | openai
EMBED_DIM = int(_p("EMBED_DIM", "128"))
LOG_LEVEL = _p("LOG_LEVEL", "INFO")

# optional provider keys (do not print/log these)
JINA_MODEL = _p("JINA_MODEL", None)
JINA_API_KEY = _p("JINA_API_KEY", None)
OPENAI_API_KEY = _p("OPENAI_API_KEY", None)

_GLOBAL_CHROMA_CLIENT = _p("_GLOBAL_CHROMA_CLIENT", None)


# # ---------------------------------------------------------------------------
# # TEI / Grobid constants used by parsers
# # ---------------------------------------------------------------------------
# NS = {"tei": "http://www.tei-c.org/ns/1.0"}   # used by TEI parser modules
# XML_NS_ID = "{http://www.w3.org/XML/1998/namespace}id"
# GROBID_URL = _p("GROBID_URL", "http://localhost:8070/api/processFulltextDocument")


# convenience: single collection env key older code may refer to
# if CHROMA_COLLECTION env present, prefer it; else use chunks collection
COLLECTION_NAME = _p("CHROMA_COLLECTION", CHROMA_CHUNKS_COLL)

# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def chroma_collection_name(kind: str = "chunks") -> str:
    return CHROMA_PAPERS_COLL if kind == "papers" else CHROMA_CHUNKS_COLL

# expose a curated __all__ so 'from shared.config import *' behaves reasonably
__all__ = [
    # canonical
    "REPO_ROOT", "CHROMA_DIR", "CHUNKS_DIR", "PAPERS_DIR", "EMBED_CACHE_DB", "SUMMARY_DB",
    "CHROMA_CHUNKS_COLL", "CHROMA_PAPERS_COLL", "EMBED_ADAPTER", "EMBED_DIM",
    "JINA_MODEL", "JINA_API_KEY", "OPENAI_API_KEY", "LOG_LEVEL", "NS", "XML_NS_ID", "GROBID_URL", "COLLECTION_NAME",
    # helper
    "chroma_collection_name",
]
