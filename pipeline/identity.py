from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_title(title: Optional[str]) -> str:
    t = (title or "").strip().lower()
    t = _WS.sub(" ", t)
    return t


def normalize_source_ref(source_ref: Optional[str]) -> str:
    if not source_ref:
        return ""
    name = Path(str(source_ref)).name.strip().lower()
    name = _WS.sub(" ", name)
    return name


def _hex10(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]


def make_paper_uid(*, doi: Optional[str] = None, source_file: Optional[str] = None, title: Optional[str] = None, fallback: Optional[str] = None) -> str:
    if doi and doi.strip():
        seed = f"doi:{doi.strip().lower()}"
    elif source_file and str(source_file).strip():
        seed = f"source:{normalize_source_ref(source_file)}"
    elif title and title.strip():
        norm_title = normalize_title(title)
        seed = f"title:{norm_title}"
    else:
        seed = f"fallback:{normalize_source_ref(fallback) or 'unknown'}"
    return f"paper_{_hex10(seed)}"


def safe_artifact_key(paper_uid: str) -> str:
    base = (paper_uid or "").strip().lower()
    cleaned = _NON_ALNUM.sub("_", base).strip("_")
    return cleaned or "paper_unknown"
