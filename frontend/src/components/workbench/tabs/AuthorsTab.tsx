"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkbenchTabProps } from "@/workbench/types";

export default function AuthorsTab({ papers, navigate }: WorkbenchTabProps) {
  const [query, setQuery] = useState("");

  const authors = useMemo(() => {
    const index = new Map<string, typeof papers>();
    for (const paper of papers) {
      for (const author of paper.authors) {
        const key = author.trim();
        if (!key) continue;
        index.set(key, [...(index.get(key) || []), paper]);
      }
    }
    return Array.from(index.entries())
      .map(([name, works]) => ({ name, works }))
      .filter(({ name }) => name.toLowerCase().includes(query.trim().toLowerCase()))
      .sort((a, b) => b.works.length - a.works.length || a.name.localeCompare(b.name));
  }, [papers, query]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold">Authors</h2>
          <p className="text-sm text-slate-500">A projection of producer metadata, not an inferred author authority.</p>
        </div>
        <input
          className="min-w-72 rounded border px-3 py-2 text-sm"
          placeholder="Filter authors…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {authors.map(({ name, works }) => (
          <Card key={name}>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-baseline justify-between gap-3 text-base">
                <span>{name}</span>
                <span className="text-xs font-normal text-slate-500">{works.length} {works.length === 1 ? "paper" : "papers"}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {works.map((paper) => (
                <div key={paper.paperId} className="flex items-start justify-between gap-3 rounded border p-2">
                  <div>
                    <div className="text-sm font-medium">{paper.title}</div>
                    <div className="mt-1 text-xs text-slate-500">{paper.year || "year missing"}{paper.venue ? ` · ${paper.venue}` : ""}</div>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => navigate("paper", paper.paperId)}>Open</Button>
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>

      {authors.length === 0 ? <div className="rounded border p-6 text-sm text-slate-500">No authors match this filter.</div> : null}
    </div>
  );
}
