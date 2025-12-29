"use client";
import React, { useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";

/**
 * Lightweight normalized SearchHit UI type
 * We map raw backend fields (chunk_id, paper_id, paper_title, score, text)
 * into this camelCase shape for consistent consumption in the UI.
 */
type SearchHit = {
  id: string; // fallback id (chunkId || id || generated)
  chunkId?: string | null;
  paperId?: string | null;
  paperTitle?: string | null;
  text?: string | null;
  score?: number | null;
  meta?: Record<string, unknown> | null;
};

export default function SearchPage() {
  const [rawResultsLoaded, setRawResultsLoaded] = useState(false);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [q, setQ] = useState("effects of climate change");
  const [loading, setLoading] = useState(false);

  // initial load of canned search-results.json (local fixture)
  useEffect(() => {
    setLoading(true);
    apiGet("search-results.json")
      .then((d: any) => {
        // Expecting a shape like { query: "...", results: [ {...raw hit...} ] }
        const raw: any[] = Array.isArray(d?.results) ? d.results : d ? [d] : [];
        const normalized: SearchHit[] = raw.map((r: any, i: number) => {
          const chunkId = r.chunk_id ?? r.id ?? null;
          const paperId = r.paper_id ?? (r.meta && (r.meta.paper_id as string)) ?? null;
          const paperTitle = r.paper_title ?? r.meta?.title ?? null;
          const text = typeof r.text === "string" ? r.text : String(r?.snippet ?? r?.summary ?? "");
          const score = typeof r.score === "number" ? r.score : Number(r?.score ?? NaN);
          return {
            id: chunkId ?? `hit-${i}`,
            chunkId,
            paperId,
            paperTitle,
            text,
            score: Number.isFinite(score) ? score : null,
            meta: r.meta ?? null,
          };
        });
        setHits(normalized);
        setRawResultsLoaded(true);
      })
      .catch((err) => {
        console.error("Failed to load canned search results:", err);
        setHits([]);
      })
      .finally(() => setLoading(false));
  }, []);

  // simple client-side filtering: check q against text or paperTitle
  const filtered = useMemo(() => {
    const qq = (q ?? "").trim().toLowerCase();
    if (!qq) return hits;
    return hits.filter((h) => {
      const text = (h.text ?? "").toLowerCase();
      const title = (h.paperTitle ?? "").toLowerCase();
      return text.includes(qq) || title.includes(qq);
    });
  }, [hits, q]);

  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: 12 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 12 }}>Semantic search (health)</h1>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          aria-label="search-input"
          className="border rounded px-3 py-2"
          style={{ flex: 1 }}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button
          className="btn"
          onClick={() => {
            /* we operate on the canned dataset; this button triggers the same local filter */
          }}
        >
          Search
        </button>
      </div>

      {loading && <div>Loading results…</div>}

      {!loading && !rawResultsLoaded && <div>No results (fixture not loaded)</div>}

      {!loading && rawResultsLoaded && (
        <div style={{ display: "grid", gap: 12 }}>
          {filtered.length === 0 ? (
            <div style={{ padding: 12 }}>No search hits match your query</div>
          ) : (
            filtered.map((r) => (
              <article
                key={r.id}
                style={{ border: "1px solid #e6e6e6", padding: 12, borderRadius: 6, background: "#fff" }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline" }}>
                  <div>
                    <a
                      className="font-medium"
                      href={`/papers/${encodeURIComponent(r.paperId ?? "")}`}
                      style={{ color: "#0ea5e9", textDecoration: "none" }}
                    >
                      {r.paperTitle ?? r.paperId ?? "Unknown paper"}
                    </a>
                  </div>

                  <div style={{ fontSize: 12, color: "#6b7280" }}>
                    {r.score != null ? Number(r.score).toFixed(3) : "—"}
                  </div>
                </div>

                <p style={{ marginTop: 8, color: "#374151" }}>{r.text}</p>

                <div style={{ marginTop: 8, fontSize: 12, color: "#6b7280" }}>
                  <button
                    style={{ marginRight: 8 }}
                    onClick={() => {
                      if (r.paperId) window.open(`/paper?paper_id=${encodeURIComponent(r.paperId)}`, "_blank");
                    }}
                  >
                    Open
                  </button>

                  <button
                    onClick={() => {
                      // minimal follow-up: copy the query + chunk text into the clipboard as a quick "ask"
                      const payload = `Q: ${q}\n\nContext: ${r.text ?? ""}`;
                      if (typeof navigator !== "undefined" && navigator.clipboard) {
                        navigator.clipboard.writeText(payload).catch(() => {});
                      }
                    }}
                  >
                    Ask follow-up
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      )}
    </main>
  );
}
