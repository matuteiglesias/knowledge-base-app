"use client";

import { FormEvent, useMemo, useState } from "react";
import { searchPaperChunks, type SearchHit } from "@/api/papers";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkbenchTabProps } from "@/workbench/types";

export default function SearchTab({ papers, selectedPaper, navigate }: WorkbenchTabProps) {
  const [query, setQuery] = useState("");
  const [scopeSelected, setScopeSelected] = useState(false);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [capability, setCapability] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const paperById = useMemo(() => new Map(papers.map((paper) => [paper.paperId, paper])), [papers]);

  async function runSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    try {
      const result = await searchPaperChunks(q, {
        k: 30,
        paperId: scopeSelected ? selectedPaper?.paperId : null,
      });
      setHits(result.hits || []);
      setCapability(result.capability || "unknown");
    } catch (err) {
      setHits([]);
      setCapability(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Chunk search</h2>
        <p className="text-sm text-slate-500">Queries the real Paper KB read service. The backend reports its actual search capability.</p>
      </div>

      <form onSubmit={runSearch} className="rounded border bg-white p-4">
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            className="flex-1 rounded border px-3 py-2"
            placeholder="Search text across canonical chunks…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <Button type="submit" disabled={loading || !query.trim()}>{loading ? "Searching…" : "Search"}</Button>
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={scopeSelected}
            disabled={!selectedPaper}
            onChange={(event) => setScopeSelected(event.target.checked)}
          />
          scope to selected paper {selectedPaper ? `(${selectedPaper.title})` : "(select a paper first)"}
        </label>
      </form>

      {capability ? <div className="text-sm text-slate-500">Backend capability: <Badge variant="outline">{capability}</Badge></div> : null}
      {error ? <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      <div className="space-y-3">
        {hits.map((hit, index) => {
          const paperId = hit.paper_id || (typeof hit.meta?.paper_id === "string" ? hit.meta.paper_id : null);
          const paper = paperId ? paperById.get(paperId) : null;
          return (
            <Card key={`${hit.id}-${index}`}>
              <CardHeader className="pb-2">
                <CardTitle className="flex flex-col gap-1 text-sm sm:flex-row sm:items-baseline sm:justify-between">
                  <span>{paper?.title || paperId || "Unknown paper"}</span>
                  <span className="font-normal text-slate-500">score {typeof hit.score === "number" ? hit.score.toFixed(4) : "—"}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-line text-sm leading-6 text-slate-700">{hit.text}</p>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <span className="font-mono text-[11px] text-slate-400">{hit.chunk_id || hit.id}</span>
                  {paperId ? <Button size="sm" variant="outline" onClick={() => navigate("paper", paperId)}>Open paper</Button> : null}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {!loading && query.trim() && !error && hits.length === 0 ? <div className="rounded border p-6 text-sm text-slate-500">No matching chunks.</div> : null}
    </div>
  );
}
