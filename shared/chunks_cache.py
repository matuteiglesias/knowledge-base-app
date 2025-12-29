# shared/chunks_cache.py
from pathlib import Path
import json
from typing import Dict, List, Optional, Any

_chunks_by_id: Dict[str, Dict[str, Any]] = {}
_papers_map: Dict[str, List[Dict[str, Any]]] = {}
_loaded = False
_streaming_mode = False
_last_loaded_path: Optional[str] = None
_MAX_BYTES_IN_MEMORY = 50 * 1024 * 1024  # 50 MB guard

def load_chunks_cache(path: Path, max_bytes_in_memory: int = _MAX_BYTES_IN_MEMORY) -> None:
    """
    Load store/chunks/all_chunks.jsonl into an in-memory cache for fast metadata and text lookups.
    If the file exceeds max_bytes_in_memory, the loader switches to streaming mode and does not load into memory.
    """
    global _chunks_by_id, _papers_map, _loaded, _streaming_mode, _last_loaded_path

    _chunks_by_id = {}
    _papers_map = {}
    _loaded = False
    _streaming_mode = False
    _last_loaded_path = str(path)

    if not path.exists():
        _streaming_mode = True
        return

    try:
        size = path.stat().st_size
        if size > max_bytes_in_memory:
            _streaming_mode = True
            return

        with path.open("r", encoding="utf8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    # skip malformed lines but do not crash
                    continue
                cid = obj.get("chunk_id") or obj.get("id") or obj.get("chunkId")
                if not cid:
                    # skip if no id present
                    continue
                _chunks_by_id[cid] = obj
                pid = obj.get("paper_id") or obj.get("paper") or "unknown"
                _papers_map.setdefault(pid, []).append(obj)

        # stable ordering per paper by chunk_index if present
        for pid, chunks in _papers_map.items():
            chunks.sort(key=lambda o: (o.get("chunk_index") or 0))
        _loaded = True
    except Exception:
        _loaded = False
        _streaming_mode = False

def is_loaded() -> bool:
    return _loaded and not _streaming_mode

def is_streaming_mode() -> bool:
    return _streaming_mode

def get_chunk_from_cache(chunk_id: str) -> Optional[Dict[str, Any]]:
    return _chunks_by_id.get(chunk_id)

def list_chunks_for_paper(paper_id: str, offset: int = 0, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    lst = _papers_map.get(paper_id, []).copy()
    if limit is None:
        return lst[offset:]
    return lst[offset: offset + limit]

def list_papers_summary(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    out = []
    for pid, chunks in _papers_map.items():
        if not chunks:
            continue
        title = chunks[0].get("title") or pid
        authors = chunks[0].get("authors")
        out.append({"paper_id": pid, "title": title, "authors": authors, "n_chunks": len(chunks)})
        if limit and len(out) >= limit:
            break
    return out

def get_loaded_path() -> Optional[str]:
    return _last_loaded_path
