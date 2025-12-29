# paste into backend/app/storage_adapter.py (replace JsonlAdapter implementation)
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import re
import json

logger = logging.getLogger(__name__)

# reuse FS helpers if present (but don't rely on their exact shapes)
try:
    from backend.app.chunks_fs import iter_chunks_jsonl, chunk_file_for, read_chunks_as_models, get_chunk_by_id
except Exception:
    # fallback minimal in-module functions (will be used if chunks_fs not importable)
    iter_chunks_jsonl = None
    chunk_file_for = None
    read_chunks_as_models = None
    get_chunk_by_id = None

# path defaults (hard-coded to fixture for emergency mode)
DEFAULT_CHUNKS_DIR = Path("fixture/chunks")
DEFAULT_PAPERS_DIR = Path("fixture/papers")
_WORD_RE = re.compile(r"[a-z0-9]{2,}", re.I)


def _normalize_pages(pages_raw) -> Optional[Tuple[Optional[int], Optional[int]]]:
    # Accept pages as "10-10", "10", [10,10], [10], {"start":10,"end":12}
    if pages_raw is None:
        return None
    if isinstance(pages_raw, (list, tuple)):
        a = int(pages_raw[0]) if len(pages_raw) >= 1 and pages_raw[0] is not None else None
        b = int(pages_raw[1]) if len(pages_raw) >= 2 and pages_raw[1] is not None else a
        return (a, b)
    if isinstance(pages_raw, str):
        s = pages_raw.strip()
        if "-" in s:
            parts = s.split("-", 1)
            try:
                return (int(parts[0]) if parts[0] else None, int(parts[1]) if parts[1] else None)
            except ValueError:
                return None
        try:
            return (int(s), int(s))
        except ValueError:
            return None
    if isinstance(pages_raw, dict):
        try:
            return (int(pages_raw.get("start")) if pages_raw.get("start") else None,
                    int(pages_raw.get("end")) if pages_raw.get("end") else None)
        except Exception:
            return None
    return None


def _ensure_chunk_shape(rec: Dict[str, Any]) -> Dict[str, Any]:
    # produce a stable chunk dict that services expect
    out = {}
    # id keys
    out["chunk_id"] = rec.get("chunk_id") or rec.get("id") or (rec.get("meta") or {}).get("chunk_id") or ""
    out["paper_id"] = rec.get("paper_id") or (rec.get("meta") or {}).get("paper_id") or ""
    # text / preview
    text = rec.get("text")
    if text is None:
        text = rec.get("preview") or (rec.get("meta") or {}).get("preview") or ""
    out["text"] = text or ""
    # chunk index
    try:
        out["chunk_index"] = int(rec.get("chunk_index") or (rec.get("meta") or {}).get("chunk_index") or 0)
    except Exception:
        out["chunk_index"] = 0
    # char_len
    try:
        out["char_len"] = int(rec.get("char_len") or (rec.get("meta") or {}).get("char_len") or len(out["text"] or ""))
    except Exception:
        out["char_len"] = len(out["text"] or "")
    # header_path / pages / meta
    out["header_path"] = rec.get("header_path") or (rec.get("meta") or {}).get("header_path")
    out["pages"] = _normalize_pages(rec.get("pages") or (rec.get("meta") or {}).get("pages"))
    out["meta"] = rec.get("meta") or {}
    # keep original raw for debugging if needed
    out["_raw"] = rec
    return out


class JsonlAdapter:
    backend_name = "jsonl-fixture"
    persisted = False

    def __init__(self, chunks_dir: Optional[str] = None, papers_dir: Optional[str] = None, embeddings_dir: Optional[str] = None):
        self.chunks_dir = Path(chunks_dir or DEFAULT_CHUNKS_DIR)
        self.papers_dir = Path(papers_dir or DEFAULT_PAPERS_DIR)
        self.embeddings_dir = Path(embeddings_dir) if embeddings_dir else None
        self._papers_index: Optional[List[Dict[str, Any]]] = None

    def load_caches(self) -> None:
        # load simple papers index by scanning fixture/papers
        try:
            out = []
            if self.papers_dir.exists():
                for f in self.papers_dir.glob("*.json"):
                    try:
                        raw = json.loads(f.read_text(encoding="utf8"))
                        out.append({
                            "paper_id": raw.get("paper_id", f.stem),
                            "title": raw.get("title", f.stem),
                            "n_chunks": raw.get("n_chunks", 0),
                            "metadata": raw
                        })
                    except Exception:
                        logger.debug("skipping malformed paper file %s", f)
            self._papers_index = out
        except Exception:
            logger.exception("JsonlAdapter.load_caches failed")

    def list_papers(self) -> List[Dict[str, Any]]:
        if self._papers_index is not None:
            return self._papers_index
        self.load_caches()
        return self._papers_index or []

    def get_paper(self, paper_id: str) -> Dict[str, Any]:
        # try paper file
        pfile = self.papers_dir / f"{paper_id}.json"
        if pfile.exists():
            try:
                return json.loads(pfile.read_text(encoding="utf8"))
            except Exception:
                logger.debug("malformed paper file %s", pfile)
        # fallback to listing
        for p in self.list_papers():
            if p.get("paper_id") == paper_id:
                return p.get("metadata") or p
        return {}

    def list_chunks(self, paper_id: str, limit: int = 200, offset: int = 0, q: Optional[str] = None) -> Dict[str, Any]:
        out = []
        total = 0
        # find the file: <paper_id>_chunks.jsonl in fixture/chunks
        file_path = self.chunks_dir / f"{paper_id}_chunks.jsonl"
        if not file_path.exists():
            # try alternative pattern
            matches = list(self.chunks_dir.glob(f"{paper_id}*_chunks.jsonl"))
            if matches:
                file_path = matches[0]
            else:
                return {"paper_id": paper_id, "n": 0, "chunks": []}

        try:
            # stream lines; use provided iter_chunks_jsonl if available
            if callable(iter_chunks_jsonl):
                iterator = iter_chunks_jsonl(file_path)
            else:
                # fallback: simple JSONL parser
                def iterator_gen():
                    with open(file_path, "r", encoding="utf8") as fh:
                        for line in fh:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                yield json.loads(line)
                            except Exception:
                                continue
                iterator = iterator_gen()

            idx = 0
            start = offset
            end = offset + limit
            qlow = (q or "").lower() if q else None
            for rec in iterator:
                # count candidate even if filtered-out, but ensure filter semantics: if q present, only count matches
                text = (rec.get("text") or rec.get("preview") or (rec.get("meta") or {}).get("preview") or "")
                if qlow and qlow not in (text or "").lower():
                    continue
                if idx >= start and idx < end:
                    out.append(_ensure_chunk_shape(rec))
                idx += 1
            total = idx
        except Exception:
            logger.exception("JsonlAdapter.list_chunks streaming failed for %s", paper_id)
            # fallback: attempt to read via read_chunks_as_models if available
            try:
                if callable(read_chunks_as_models):
                    models = read_chunks_as_models(paper_id)
                    maps = [m.model_dump() if hasattr(m, "model_dump") else (m.dict() if hasattr(m, "dict") else m) for m in models]
                    if q:
                        qlow = q.lower()
                        maps = [m for m in maps if qlow in ((m.get("text") or m.get("preview") or "")).lower()]
                    total = len(maps)
                    out = [ _ensure_chunk_shape(m) for m in maps[offset:offset+limit] ]
                else:
                    return {"paper_id": paper_id, "n": 0, "chunks": []}
            except Exception:
                logger.exception("JsonlAdapter.list_chunks fallback also failed")
                return {"paper_id": paper_id, "n": 0, "chunks": []}

        return {"paper_id": paper_id, "n": int(total), "chunks": out}

    def get_chunk(self, paper_id: str, chunk_id: str) -> Optional[Dict[str, Any]]:
        # first try chunks file scan via get_chunk_by_id if available
        try:
            if callable(get_chunk_by_id):
                res = get_chunk_by_id(paper_id, chunk_id)
                if res:
                    # convert to dict shape
                    if hasattr(res, "model_dump"):
                        d = res.model_dump()
                    elif hasattr(res, "dict"):
                        d = res.dict()
                    else:
                        d = dict(getattr(res, "__dict__", {}))
                    return _ensure_chunk_shape(d)
            # fallback: stream file
            file_path = self.chunks_dir / f"{paper_id}_chunks.jsonl"
            if not file_path.exists():
                matches = list(self.chunks_dir.glob(f"{paper_id}*_chunks.jsonl"))
                if matches:
                    file_path = matches[0]
                else:
                    return None
            with open(file_path, "r", encoding="utf8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    cid = rec.get("chunk_id") or rec.get("id") or (rec.get("meta") or {}).get("chunk_id")
                    if cid == chunk_id:
                        return _ensure_chunk_shape(rec)
        except Exception:
            logger.exception("JsonlAdapter.get_chunk failed %s/%s", paper_id, chunk_id)
        return None

    def semantic_search(self, q: str, k: int = 6, paper_id: Optional[str] = None) -> List[Dict[str, Any]]:
        # quick lexical scoring; same as earlier but returning canonical fields
        if not q:
            return []
        q_tokens = _WORD_RE.findall(q.lower())
        hits = []
        def score_text(text: str):
            tokens = _WORD_RE.findall((text or "").lower())
            if not tokens:
                return 0.0
            matches = sum(1 for t in q_tokens if t in tokens)
            return matches / (1 + len(tokens))
        candidates = []
        if paper_id:
            res = self.list_chunks(paper_id, limit=10000, offset=0, q=None)
            candidates = res.get("chunks", [])
        else:
            # stream all chunks (careful: could be large, but this is emergency mode)
            for f in self.chunks_dir.glob("*_chunks.jsonl"):
                tmp = self.list_chunks(f.stem.replace("_chunks",""), limit=1000000, offset=0, q=None)
                candidates.extend(tmp.get("chunks", []))
        for c in candidates:
            s = score_text(c.get("text","") or "")
            if s > 0:
                hits.append({"id": c["chunk_id"], "text": c["text"], "score": s, "meta": c.get("meta", {}), "paper_id": c.get("paper_id")})
        hits_sorted = sorted(hits, key=lambda x: x.get("score",0), reverse=True)[:k]
        return hits_sorted

    def close(self) -> None:
        logger.debug("JsonlAdapter.close noop")

    def maybe_persist(self) -> None:
        logger.debug("JsonlAdapter.maybe_persist noop")
