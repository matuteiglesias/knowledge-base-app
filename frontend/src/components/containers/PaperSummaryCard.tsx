"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { usePaperSummary } from "@/hooks/usePaperSummary";

export default function PaperSummaryCard({ paperId }: { paperId?: string | null }) {
  const { summary, loading, error, generate, regenerate, generating } = usePaperSummary(paperId);

  if (!paperId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-600">Select a paper to inspect chunks and summaries.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? <p className="text-sm text-slate-600">Loading summary…</p> : null}

        {!loading && error ? (
          <div className="space-y-2">
            <p className="text-sm text-red-600">Could not load summary.</p>
            <Button size="sm" onClick={() => generate("mock")} disabled={generating}>
              {generating ? "Generating…" : "Try again"}
            </Button>
          </div>
        ) : null}

        {!loading && !error && !summary ? (
          <div className="space-y-2">
            <p className="text-sm text-slate-700">Status: <strong>Summary missing</strong></p>
            <p className="text-xs text-slate-500">Creates and saves a paper summary artifact. Existing summaries are not recomputed by default.</p>
            <Button size="sm" onClick={() => generate("mock")} disabled={generating}>
              {generating ? "Generating…" : "Generate summary"}
            </Button>
          </div>
        ) : null}

        {summary ? (
          <div className="space-y-2">
            <p className="text-sm text-green-700"><strong>Summary ready</strong> · provider: {summary.provider} · generated: {new Date(summary.generated_at).toLocaleString()}</p>
            <div className="text-sm space-y-1">
              <p><strong>One-line:</strong> {summary.one_line || "—"}</p>
              <p><strong>Method:</strong> {summary.method || "—"}</p>
              <p><strong>Data:</strong> {summary.data || "—"}</p>
              <p><strong>Relevance to thesis:</strong> {summary.relevance_to_thesis || "—"}</p>
            </div>
            <Button variant="outline" size="sm" onClick={() => regenerate("mock")} disabled={generating}>
              {generating ? "Generating…" : "Regenerate summary"}
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
