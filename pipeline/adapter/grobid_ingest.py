#!/usr/bin/env python3
"""
src/grobid_ingest.py

Patched GROBID ingestion runner for the paper-kb project.

Key behaviour:
 - POST to Grobid using form-data teiCoordinates (head, s)
 - Parse TEI with lxml.etree when available (namespace-aware)
 - Prefer xml:id for stable chunk ids (fallback to synthetic ids)
 - Preserve pages/bboxes when present (best-effort parsing)
 - Emit JSONL of canonical records and optional LangChain Documents
 - Safer resource handling (with open(...))
 - Integrates with your cached_embed (imported from embed_cache)
"""
from __future__ import annotations
import hashlib
import re, json
import requests
import time
from pathlib import Path
from typing import Optional

# from shared.config import GROBID_URL

import os
import logging

logger = logging.getLogger("app.services")

from shared.config import GROBID_URL

from backend.app.chunks_fs import write_chunks_jsonl, _atomic_write_text




def _short_hash(s: str, n: int = 8) -> str:
    return hashlib.sha1(s.encode("utf8")).hexdigest()[:n]


def post_pdf_to_grobid(pdf_path: Path | str, timeout_seconds: int = 180, max_retries: int = 3, backoff: float = 1.0) -> str:
    """
    POST a PDF to a local Grobid instance and return TEI XML as str.

    - pdf_path: Pathlike to PDF (will open safely)
    - timeout_seconds: requests timeout for the POST
    - max_retries: number of attempts on transient failures
    - backoff: initial backoff seconds (exponential)
    """
    pdf_p = Path(pdf_path).expanduser().resolve()
    if not pdf_p.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_p}")

    data = {
        "generateIDs": "1",
        "consolidateHeader": "1",
        "segmentSentences": "1",
        # request coordinates for head and sentences if GROBID supports
        "teiCoordinates": ["head", "s"],
    }

    attempt = 0
    last_exc: Optional[Exception] = None
    while attempt < max_retries:
        attempt += 1
        try:
            with pdf_p.open("rb") as fh:
                files = {"input": (pdf_p.name, fh, "application/pdf")}
                resp = requests.post(GROBID_URL, files=files, data=data, timeout=timeout_seconds)
                resp.raise_for_status()
                tei_text = resp.text
                if not tei_text or not tei_text.strip():
                    raise RuntimeError("Empty TEI returned by Grobid")
                return tei_text
        except requests.HTTPError as e:
            # 4xx likely permanent, 5xx maybe retryable
            last_exc = e
            status = getattr(e.response, "status_code", None)
            if status and 400 <= status < 500:
                # probably client problem — no retry
                raise RuntimeError(f"Grobid returned {status}: {e}") from e
            # else retry
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
        except Exception as e:
            last_exc = e

        # backoff
        sleep = backoff * (2 ** (attempt - 1))
        time.sleep(sleep)

    raise RuntimeError(f"Failed to get TEI from Grobid after {max_retries} attempts") from last_exc




# ---------------------------
# Main runner
# ---------------------------

from pipeline.parsers.tei_parser import parse_tei_text
# Replace or patch the existing runner with this code (keep post_pdf_to_grobid and parse_tei_text definitions above)

from pathlib import Path
from typing import Optional, List, Dict, Any
import glob
import traceback

def _collect_pdf_paths(input_path: str, recursive: bool = False) -> List[Path]:
    p = Path(input_path).expanduser().resolve()
    if p.exists() and p.is_file():
        return [p]
    if p.exists() and p.is_dir():
        if recursive:
            # rglob for all PDFs under directory
            return sorted([pp for pp in p.rglob("*.pdf") if pp.is_file()])
        else:
            return sorted([pp for pp in p.glob("*.pdf") if pp.is_file()])
    # treat input as glob pattern (e.g. "storage/downloads/*.pdf")
    matches = [Path(m).expanduser().resolve() for m in glob.glob(input_path, recursive=recursive)]
    return sorted([m for m in matches if Path(m).is_file()])


def _sanitize_filename(s: str) -> str:
    """Simple filename sanitizer: keep letters, numbers, dash, underscore and dot; collapse others to _"""
    if not s:
        return ""
    s = re.sub(r"[^\w\-. ]+", "_", s)
    s = s.strip()
    # keep it reasonable length
    return s[:180]





# ---------- 1) Generate TEIs from PDFs ----------
def generate_teis_from_pdfs(pdf_dir: Path,
                            out_tei_dir: Path,
                            recursive: bool = False,
                            timeout: int = 180,
                            max_retries: int = 3,
                            max_files: Optional[int] = None,
                            force: bool = False) -> Dict[str, Any]:
    """
    POST PDFs to GROBID and write TEI files to out_tei_dir.
    Returns summary with successes and failures.
    """
    pdf_dir = Path(pdf_dir).expanduser().resolve()
    out_tei_dir = Path(out_tei_dir).expanduser().resolve()
    out_tei_dir.mkdir(parents=True, exist_ok=True)
    failures_dir = out_tei_dir / "failures"
    failures_dir.mkdir(exist_ok=True)

    files = _collect_pdf_paths(str(pdf_dir), recursive=recursive)
    if max_files:
        files = files[:max_files]

    summary = {"n_input": len(files), "n_success": 0, "n_failures": 0, "successes": [], "failures": []}

    for pdf_path in files:
        try:
            pdf_path = Path(pdf_path)
            logger.info("grobid: processing %s", pdf_path)
            tei_text = post_pdf_to_grobid(pdf_path, timeout_seconds=timeout, max_retries=max_retries)
            # try to get title/paper_id from parsed TEI (pure parse)
            parsed = {}
            try:
                parsed = parse_tei_text(tei_text) or {}
            except Exception:
                # not fatal - we'll still write the TEI using pdf stem
                logger.debug("parse_tei_text failed for preview metadata: %s", traceback.format_exc())

            title = parsed.get("title") or pdf_path.stem
            pid = parsed.get("paper_id") or parsed.get("pid") or None

            preferred_base = _sanitize_filename(title) or _sanitize_filename(pdf_path.stem) or "paper"
            candidate = out_tei_dir / f"{preferred_base}.tei.xml"

            # disambiguate collisions (only if file exists or provided pid doesn't match)
            if candidate.exists():
                # use stable short suffix from pid if available, else hash of pdf filename
                if pid and pid != preferred_base:
                    suffix = "-" + _sanitize_filename(str(pid))[:12]
                else:
                    suffix = "-" + _short_hash(pdf_path.name, 8)
                candidate = out_tei_dir / f"{preferred_base}{suffix}.tei.xml"

            # atomic write
            _atomic_write_text(candidate, tei_text)
            logger.info("grobid: wrote TEI %s", candidate)
            summary["n_success"] += 1
            summary["successes"].append({"pdf": str(pdf_path), "tei": str(candidate), "paper_id": pid, "title": title})
        except Exception as e:
            tb = traceback.format_exc()
            logger.exception("grobid: failed %s", pdf_path)
            err = {"pdf": str(pdf_path), "error": str(e), "traceback": tb}
            summary["n_failures"] += 1
            summary["failures"].append(err)
            # write failure dump
            fail_path = failures_dir / f"{_sanitize_filename(pdf_path.stem)}.fail.json"
            fail_path.write_text(json.dumps(err, ensure_ascii=False, indent=2), encoding="utf8")
            continue

    return summary


