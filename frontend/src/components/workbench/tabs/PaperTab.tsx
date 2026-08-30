"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import ChunksCard from "@/components/containers/ChunksCard";
import PaperSummaryCard from "@/components/containers/PaperSummaryCard";
import type { WorkbenchTabProps } from "@/workbench/types";

function Field({ label, value, href }: { label: string; value?: string | number | null; href?: string | null }) {
  const missing = value === null || value === undefined || value === "";
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 border-b py-2 text-sm last:border-b-0">
      <div className="text-slate-500">{label}</div>
      <div className="min-w-0">
        {missing ? (
          <Badge variant="outline">missing upstream</Badge>
        ) : href ? (
          <a className="break-all text-sky-700 underline decoration-sky-200 underline-offset-2" href={href} target="_blank" rel="noreferrer">{String(value)}</a>
        ) : (
          <span className="break-words">{String(value)}</span>
        )}
      </div>
    </div>
  );
}

export default function PaperTab({ selectedPaper }: WorkbenchTabProps) {
  if (!selectedPaper) {
    return (
      <div className="rounded border bg-white p-8">
        <h2 className="text-xl font-semibold">Select a paper</h2>
        <p className="mt-2 text-sm text-slate-500">Open a paper from Corpus, Authors, Abstracts or Search. The selected paper remains addressable through the URL.</p>
      </div>
    );
  }

  const doiUrl = selectedPaper.doi ? `https://doi.org/${selectedPaper.doi.replace(/^https?:\/\/doi\.org\//, "")}` : null;
  const arxivUrl = selectedPaper.arxivId ? `https://arxiv.org/abs/${selectedPaper.arxivId}` : null;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle className="text-xl leading-7">{selectedPaper.title}</CardTitle>
              <div className="mt-2 text-sm text-slate-600">{selectedPaper.authors.join(" · ") || "authors missing"}</div>
            </div>
            <Badge variant="secondary">{selectedPaper.nChunks} chunks</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-x-8 lg:grid-cols-2">
            <div>
              <Field label="paper_uid" value={selectedPaper.paperUid} />
              <Field label="paper_id" value={selectedPaper.paperId} />
              <Field label="Year" value={selectedPaper.year} />
              <Field label="Date" value={selectedPaper.date} />
              <Field label="Venue" value={selectedPaper.venue} />
            </div>
            <div>
              <Field label="DOI" value={selectedPaper.doi} href={doiUrl} />
              <Field label="arXiv" value={selectedPaper.arxivId} href={arxivUrl} />
              <Field label="Source file" value={selectedPaper.sourceFile} />
              <Field label="Pipeline" value={selectedPaper.pipelineVersion} />
              <Field label="Tags" value={selectedPaper.tags.length ? selectedPaper.tags.join(" · ") : null} />
            </div>
          </div>

          <div className="mt-5 border-t pt-4">
            <div className="mb-2 text-sm font-medium">Abstract</div>
            {selectedPaper.abstract ? (
              <p className="whitespace-pre-line text-sm leading-6 text-slate-700">{selectedPaper.abstract}</p>
            ) : (
              <p className="text-sm text-slate-500">No authoritative abstract is available in the current corpus metadata.</p>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <PaperSummaryCard paperId={selectedPaper.paperId} />
        <ChunksCard paperId={selectedPaper.paperId} />
      </div>
    </div>
  );
}
