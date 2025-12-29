"""
pipeline/prompt_builder.py

Builds a single "summarize" prompt from top-k supporting chunks + a user query.
- Loads a Jinja2 template from `templates/summarize.j2` if available.
- Falls back to a compact built-in template when jinja2 or the template file isn't present.
- Returns a tuple: (prompt_text, provenance_list)

Provenance list: ordered list of dicts with these keys: {
    "index": 1-based rank,
    "chunk_id": ..., "paper_id": ..., "pages": ..., "text_snippet": ...
}

Usage:
    from pipeline.prompt_builder import build_prompt_from_chroma_result
    prompt, prov = build_prompt_from_chroma_result(query, chroma_res, template_path="templates/summarize.j2", k=6)

The function intentionally produces exactly one prompt ("summarize") and keeps the prompt-building concerns isolated so it can be reused
from background workers.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional
import textwrap
import logging

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    HAS_JINJA = True
except Exception:
    HAS_JINJA = False

logger = logging.getLogger(__name__)

# Conservative defaults
DEFAULT_TEMPLATE = textwrap.dedent(
    """
    You are a concise summarizer.
    Use ONLY the numbered context paragraphs below to answer the question.

    Question: {{ query }}

    Context paragraphs:
    {% for item in docs %}
    [{{ loop.index }}] ({{ item.paper_id }}:{{ item.pages or "?" }}) — {{ item.text_snippet }}
    {% endfor %}

    Instructions:
    - Produce a single concise paragraph summary answering the question.
    - After each factual sentence include a bracketed provenance marker like [1] referencing the context paragraph that supports it.
    - If information is not present in the context, say "(no evidence in context)".
    - Keep the answer under 200 words.
    """
)


def _safe_snippet(text: str, max_chars: int = 400) -> str:
    """Return a single-line trimmed snippet safe for embedding into prompts."""
    if not text:
        return ""
    s = " ".join(str(text).split())  # collapse whitespace
    if len(s) <= max_chars:
        return s
    # try to keep full sentences if possible
    cut = s[: max_chars + 200]
    last_period = cut.rfind('. ')
    if last_period != -1 and last_period >= max_chars // 2:
        return cut[: last_period + 1]
    return s[:max_chars].rstrip() + "..."


def _load_template(template_path: Optional[str] = None) -> Tuple[Optional[Environment], Optional[str]]:
    """Return a Jinja2 Environment+template name if available; otherwise (None, None).
    If template_path is None, we try default 'templates/summarize.j2' under project root.
    """
    if not HAS_JINJA:
        logger.debug("Jinja2 not available; falling back to default template")
        return None, None

    tpl_path = Path(template_path or "templates/summarize.j2").expanduser()

    # If a direct file provided, use its parent as loader path
    if tpl_path.exists() and tpl_path.is_file():
        loader = FileSystemLoader(str(tpl_path.parent))
        env = Environment(loader=loader, autoescape=select_autoescape(False), trim_blocks=True, lstrip_blocks=True)
        return env, tpl_path.name

    # Otherwise, try to load from ./templates relative to repository root
    alt = Path.cwd() / "templates" / Path(template_path or "summarize.j2")
    if alt.exists() and alt.is_file():
        loader = FileSystemLoader(str(alt.parent))
        env = Environment(loader=loader, autoescape=select_autoescape(False), trim_blocks=True, lstrip_blocks=True)
        return env, alt.name

    logger.debug("Template file not found at %s or %s; falling back to default template", tpl_path, alt)
    return None, None


def build_prompt(query: str, docs: List[Dict[str, Any]], template_path: Optional[str] = None, max_snippet_chars: int = 500) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Build a single "summarize" prompt from `query` and ordered `docs`.

    Args:
      - query: user query / instruction (string)
      - docs: ordered list of supporting docs, each expected to have keys: {"text", "meta" or "metadata" (dict), "id"}
             meta may contain paper_id and pages. If a doc provides 'text_snippet' that will be used; otherwise 'text' is trimmed.
      - template_path: optional path to Jinja2 template (templates/summarize.j2)

    Returns: (prompt_text, provenance_list)
      - prompt_text: final string to feed to LLM
      - provenance_list: list of dicts: {index, chunk_id, paper_id, pages, text_snippet}
    """
    # Normalize docs into a simple list of dicts with canonical fields
    norm_docs = []
    for i, d in enumerate(docs):
        # allow both 'meta' and 'metadata'
        meta = d.get("meta") or d.get("metadata") or {}
        chunk_id = d.get("id") or d.get("chunk_id") or f"doc_{i}"
        text = d.get("text") or d.get("document") or d.get("page_content") or ""
        snippet = d.get("text_snippet") or _safe_snippet(text, max_chars=max_snippet_chars)
        paper_id = meta.get("paper_id") or meta.get("paper") or meta.get("paperId") or meta.get("pid") or "unknown"
        pages = meta.get("pages") or meta.get("page") or None
        norm_docs.append({
            "chunk_id": chunk_id,
            "paper_id": paper_id,
            "pages": pages,
            "text": text,
            "text_snippet": snippet,
        })

    # Build provenance list
    provenance = []
    for idx, nd in enumerate(norm_docs, start=1):
        provenance.append({
            "index": idx,
            "chunk_id": nd["chunk_id"],
            "paper_id": nd["paper_id"],
            "pages": nd.get("pages"),
            "text_snippet": nd["text_snippet"],
        })

    # Try to load Jinja2 template
    env, tpl_name = _load_template(template_path)
    if env and tpl_name:
        try:
            tpl = env.get_template(tpl_name)
            prompt = tpl.render(query=query, docs=provenance)
            return prompt.strip(), provenance
        except Exception as e:
            logger.exception("Failed to render Jinja2 template %s: %s", tpl_name, e)
            # fall-through to default

    # fallback: use the default template
    prompt = DEFAULT_TEMPLATE
    # Render simple replacements: we do a minimal, safe interpolation
    # build docs text block
    ctx_lines = []
    for p in provenance:
        pid = p.get("paper_id") or "?"
        pages = p.get("pages") or "?"
        txt = p.get("text_snippet") or ""
        ctx_lines.append(f"[{p['index']}] ({pid}:{pages}) — {txt}")

    prompt_filled = prompt.replace("{{ query }}", str(query))
    prompt_filled = prompt_filled.replace("{% for item in docs %}", "")
    # simple substitute for the docs block marker in our default template
    prompt_filled = prompt_filled.replace("{% endfor %}", "")
    prompt_filled = prompt_filled.replace("{{ item.paper_id }}", "")
    prompt_filled = prompt_filled.replace("{{ item.pages or \"?\" }}", "")
    prompt_filled = prompt_filled.replace("{{ item.text_snippet }}", "")
    # insert context paragraphs into the placeholder location (after 'Context paragraphs:')
    prompt_parts = prompt_filled.split("Context paragraphs:")
    if len(prompt_parts) == 2:
        head, tail = prompt_parts
        filled = head + "Context paragraphs:\n" + "\n\n".join(ctx_lines) + "\n\n" + tail
    else:
        filled = prompt_filled + "\n\n" + "\n\n".join(ctx_lines)

    # final sanitization
    final = str(filled).strip()
    return final, provenance


def build_prompt_from_chroma_result(query: str, res: Dict[str, Any], k: int = 6, template_path: Optional[str] = None) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Adapter to build prompt from a Chroma `.query()` result.
    Expects `res` to be the raw response dict returned by Chroma's query, with shapes like:
      {
         "ids": [[...]],
         "documents": [[...]],
         "metadatas": [[...]],
      }
    We take the first (and usually only) row of results and map into docs.
    """
    # Defensive extraction of first result row
    try:
        ids_row = res.get("ids") or []
        docs_row = res.get("documents") or []
        metas_row = res.get("metadatas") or []
        # If nested (list of lists), take the first row
        if ids_row and isinstance(ids_row[0], list):
            ids = ids_row[0]
        else:
            ids = ids_row
        if docs_row and isinstance(docs_row[0], list):
            docs = docs_row[0]
        else:
            docs = docs_row
        if metas_row and isinstance(metas_row[0], list):
            metas = metas_row[0]
        else:
            metas = metas_row
    except Exception:
        # fallback: try to treat res as flat mapping lists
        ids = res.get("ids", [])
        docs = res.get("documents", [])
        metas = res.get("metadatas", [])

    # build normalized docs list
    norm = []
    for i in range(min(k, max(len(ids), len(docs), len(metas)))):
        chunk_id = ids[i] if i < len(ids) else f"r{i}"
        text = docs[i] if i < len(docs) else ""
        meta = metas[i] if i < len(metas) else {}
        norm.append({"id": chunk_id, "text": text, "meta": meta})

    return build_prompt(query, norm, template_path=template_path)


# If invoked as a script, demonstrate on sample JSON files if present
if __name__ == "__main__":
    import json
    sample = Path.cwd() / "frontend" / "public" / "dev-data" / "search-results.json"
    if sample.exists():
        try:
            data = json.loads(sample.read_text(encoding="utf8"))
            # try to use the first 'result' shape
            if isinstance(data, dict) and "hits" in data:
                hits = data["hits"]
                docs = []
                for h in hits[:6]:
                    docs.append({"id": h.get("id"), "text": h.get("text"), "meta": h.get("meta")})
                p, prov = build_prompt_from_chroma_result("Summarize the main finding", {"ids": [[d['id'] for d in docs]], "documents": [[d['text'] for d in docs]], "metadatas": [[d['meta'] for d in docs]]}, k=6)
                print("PROMPT:\n", p)
                print("PROVENANCE:\n", prov)
        except Exception as e:
            logger.exception("Demo run failed: %s", e)
    else:
        print("No sample dev-data found; call build_prompt or build_prompt_from_chroma_result from your code.")
