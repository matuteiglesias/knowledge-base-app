"use client";
import React, { useEffect, useState } from "react";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

/**
 * Minimal PapersCard for health/debug:
 * - Directly fetches /api/papers
 * - Renders the raw papers[] array the backend returns (snake_case)
 * - Shows raw JSON debug blocks so you can inspect returned payloads
 *
 * This is intentionally simple and uses `any` shapes so you can quickly
 * verify the backend response without normalization logic in the way.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9000";

export default function PapersCard({
  onSelectPaper,
  viewerBasePath = "/paper",
}: {
  onSelectPaper?: (p: any) => void;
  viewerBasePath?: string;
}) {
  const [raw, setRaw] = useState<any | null>(null);
  const [papers, setPapers] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadPapers() {
    setLoading(true);
    setError(null);
    try {
      const url = `${API_BASE}/api/papers`;
      const res = await fetch(url, { method: "GET", cache: "no-store" });
      const txt = await res.text();
      // try parse safely
      let body: any = null;
      try {
        body = txt ? JSON.parse(txt) : {};
      } catch (e) {
        throw new Error(`Invalid JSON response (${res.status}): ${String(e)} – body: ${txt.slice(0, 400)}`);
      }

      // preserve raw response for debug
      setRaw({ status: res.status, ok: res.ok, headers: Object.fromEntries(res.headers.entries()), body });

      // expect body.papers to be an array; if not, set to null but show body
      const arr = Array.isArray(body?.papers) ? body.papers : [];
      setPapers(arr.length > 0 ? arr : []); // show empty array if none
      if (!res.ok) {
        setError(`Backend returned status ${res.status}`);
      } else if (!Array.isArray(body?.papers)) {
        setError("Backend returned payload without 'papers' array");
      } else if (arr.length === 0) {
        // No error, but show small note (backend legitimately returned 0 items)
        // leave error null so UI still shows 'No papers' state
      }
    } catch (e: any) {
      console.error("loadPapers error", e);
      setError(String(e?.message ?? e));
      setRaw({ error: String(e) });
      // keep previous papers as-is (do not clear) — optional
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPapers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openPaper(p: any) {
    const pid = encodeURIComponent(p?.paper_id ?? p?.title ?? "");
    window.open(`${viewerBasePath}?paper_id=${pid}`, "_blank", "noopener,noreferrer");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Available papers</CardTitle>
      </CardHeader>

      <CardContent>
        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          <Button size="sm" onClick={() => loadPapers()} disabled={loading}>
            {loading ? "Loading…" : "Reload"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => { setPapers([]); setRaw(null); setError(null); }}>
            Clear
          </Button>
        </div>

        {error && <div style={{ color: "var(--red-600)", paddingBottom: 8 }}>Error: {error}</div>}

        <div style={{ marginBottom: 12 }}>
          <Label>Results</Label>
          {Array.isArray(papers) && papers.length > 0 ? (
            <div style={{ marginTop: 8 }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: 6 }}>Title</th>
                    <th style={{ width: 120, textAlign: "right", padding: 6 }}>Chunks</th>
                    <th style={{ width: 120 }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {papers.map((p, i) => (
                    <tr key={p.paper_id ?? p.title ?? `paper-${i}`} style={{ borderTop: "1px solid #eee" }}>
                      <td style={{ padding: 8 }}>
                        <div style={{ fontWeight: 600 }}>{p.title ?? p.paper_id}</div>
                        <div style={{ color: "#666", fontSize: 12, marginTop: 4 }}>
                          {Array.isArray(p.authors) ? p.authors.join(", ") : p.authors ?? ""}
                        </div>
                      </td>
                      <td style={{ padding: 8, textAlign: "right" }}>{typeof p.n_chunks === "number" ? p.n_chunks : "—"}</td>
                      <td style={{ padding: 8 }}>
                        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                          <Button size="sm" onClick={() => openPaper(p)}>Open</Button>
                          <Button size="sm" onClick={() => onSelectPaper?.(p)} variant="outline">Select</Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: 8 }}>{loading ? "Loading papers…" : "No papers"}</div>
          )}
        </div>

        {/* Raw debug area */}
        <details style={{ marginTop: 8 }}>
          <summary style={{ cursor: "pointer" }}>Raw backend debug</summary>
          <pre style={{ maxHeight: 360, overflow: "auto", padding: 8, background: "#fafafa" }}>
            {JSON.stringify(raw ?? { note: "no raw yet" }, null, 2)}
          </pre>
        </details>
      </CardContent>
    </Card>
  );
}
