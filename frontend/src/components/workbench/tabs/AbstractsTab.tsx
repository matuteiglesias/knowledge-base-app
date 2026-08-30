"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkbenchTabProps } from "@/workbench/types";

export default function AbstractsTab({ papers, navigate }: WorkbenchTabProps) {
  const [query, setQuery] = useState("");
  const [showMissing, setShowMissing] = useState(true);

  const available = papers.filter((paper) => Boolean(paper.abstract)).length;
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return papers.filter((paper) => {
      if (!showMissing && !paper.abstract) return false;
      if (!q) return true;
      return [paper.title, paper.abstract, ...paper.authors]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(q);
    });
  }, [papers, query, showMissing]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-xl font-semibold">Abstract review</h2>
          <p className="text-sm text-slate-500">{available}/{papers.length} abstracts available. Missing values are upstream evidence, not silently inferred.</p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={showMissing} onChange={(event) => setShowMissing(event.target.checked)} />
            show missing
          </label>
          <input
            className="min-w-72 rounded border px-3 py-2 text-sm"
            placeholder="Filter title, author, abstract…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>

      <div className="space-y-3">
        {filtered.map((paper) => (
          <Card key={paper.paperId}>
            <CardHeader className="pb-2">
              <CardTitle className="flex flex-col gap-2 text-base sm:flex-row sm:items-start sm:justify-between">
                <span>{paper.title}</span>
                <Badge variant={paper.abstract ? "secondary" : "outline"}>{paper.abstract ? "abstract" : "missing upstream"}</Badge>
              </CardTitle>
              <div className="text-xs text-slate-500">{paper.authors.join(" · ") || "authors missing"}{paper.year ? ` · ${paper.year}` : ""}{paper.venue ? ` · ${paper.venue}` : ""}</div>
            </CardHeader>
            <CardContent>
              {paper.abstract ? (
                <p className="whitespace-pre-line text-sm leading-6 text-slate-700">{paper.abstract}</p>
              ) : (
                <p className="text-sm text-slate-500">No authoritative abstract is present in the current Paper KB read model for this paper.</p>
              )}
              <div className="mt-3"><Button size="sm" variant="outline" onClick={() => navigate("paper", paper.paperId)}>Inspect paper</Button></div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
