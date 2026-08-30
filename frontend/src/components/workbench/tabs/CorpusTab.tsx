"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkbenchTabProps } from "@/workbench/types";

function valueOrMissing(value: unknown) {
  return value ? String(value) : "missing";
}

export default function CorpusTab({ papers, selectedPaper, corpusHealth, navigate }: WorkbenchTabProps) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return papers;
    return papers.filter((paper) =>
      [paper.title, paper.paperUid, paper.paperId, paper.venue, paper.year, ...paper.authors]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(q)
    );
  }, [papers, query]);

  const coverage = useMemo(() => ({
    abstracts: papers.filter((paper) => Boolean(paper.abstract)).length,
    years: papers.filter((paper) => Boolean(paper.year)).length,
    venues: papers.filter((paper) => Boolean(paper.venue)).length,
    dois: papers.filter((paper) => Boolean(paper.doi)).length,
  }), [papers]);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Papers</CardTitle></CardHeader><CardContent className="text-2xl font-semibold">{papers.length}</CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Chunks</CardTitle></CardHeader><CardContent className="text-2xl font-semibold">{corpusHealth?.n_chunks ?? "—"}</CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Abstracts</CardTitle></CardHeader><CardContent>{coverage.abstracts}/{papers.length}</CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Years</CardTitle></CardHeader><CardContent>{coverage.years}/{papers.length}</CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Venues</CardTitle></CardHeader><CardContent>{coverage.venues}/{papers.length}</CardContent></Card>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold">Corpus browser</h2>
          <p className="text-sm text-slate-500">Canonical identity is preserved; absent scientific metadata stays visibly absent.</p>
        </div>
        <input
          className="min-w-72 rounded border px-3 py-2 text-sm"
          placeholder="Filter title, author, venue, year…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      <div className="overflow-x-auto rounded border bg-white">
        <table className="w-full text-sm">
          <thead className="border-b bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="p-3">Paper</th>
              <th className="p-3">Year</th>
              <th className="p-3">Venue</th>
              <th className="p-3">Abstract</th>
              <th className="p-3">Chunks</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((paper) => (
              <tr key={paper.paperId} className={`border-b align-top ${selectedPaper?.paperId === paper.paperId ? "bg-slate-50" : ""}`}>
                <td className="p-3">
                  <div className="font-medium">{paper.title}</div>
                  <div className="mt-1 text-xs text-slate-500">{paper.authors.join(" · ") || "authors missing"}</div>
                  <div className="mt-1 font-mono text-[11px] text-slate-400">{paper.paperUid || paper.paperId}</div>
                </td>
                <td className="p-3">{valueOrMissing(paper.year)}</td>
                <td className="p-3">{valueOrMissing(paper.venue)}</td>
                <td className="p-3"><Badge variant={paper.abstract ? "secondary" : "outline"}>{paper.abstract ? "available" : "missing"}</Badge></td>
                <td className="p-3">{paper.nChunks}</td>
                <td className="p-3"><Button size="sm" variant="outline" onClick={() => navigate("paper", paper.paperId)}>Open</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 ? <div className="p-6 text-sm text-slate-500">No papers match this filter.</div> : null}
      </div>
    </div>
  );
}
