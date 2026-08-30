"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePaperSummary } from "@/hooks/usePaperSummary";

export default function PaperSummaryCard({ paperId }: { paperId?: string | null }) {
  const { summary, loading, error, generate, regenerate, generating } = usePaperSummary(paperId);
  const writesEnabled = process.env.NEXT_PUBLIC_ENABLE_SUMMARY_WRITES === "1";

  if (!paperId) {
    return (
      <Card>
        <CardHeader><CardTitle>Summary derivation</CardTitle></CardHeader>
        <CardContent><p className="text-sm text-slate-600">Select a paper to inspect summary artifacts.</p></CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle>Summary derivation</CardTitle>
          <Badge variant="outline">experimental</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? <p className="text-sm text-slate-600">Loading summary artifact…</p> : null}

        {!loading && error ? (
          <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">Could not read the summary artifact: {String(error)}</div>
        ) : null}

        {!loading && !error && !summary ? (
          <div className="space-y-2">
            <p className="text-sm text-slate-700"><strong>No summary artifact.</strong></p>
            <p className="text-xs leading-5 text-slate-500">Summaries are derived outputs, never corpus truth. The workbench does not create mock summaries. Write actions are disabled by default.</p>
            {writesEnabled ? (
              <Button size="sm" onClick={() => generate("agent-framework")} disabled={generating}>
                {generating ? "Generating…" : "Generate experimental summary"}
              </Button>
            ) : null}
          </div>
        ) : null}

        {summary ? (
          <div className="space-y-3">
            <div className="text-xs text-slate-500">provider {summary.provider} · model {summary.model || "unknown"} · {new Date(summary.generated_at).toLocaleString()}</div>
            <div className="space-y-2 text-sm">
              <p><strong>One line:</strong> {summary.one_line || "—"}</p>
              <p><strong>Research question:</strong> {summary.research_question || "—"}</p>
              <p><strong>Method:</strong> {summary.method || "—"}</p>
              <p><strong>Data:</strong> {summary.data || "—"}</p>
              <p><strong>Main contribution:</strong> {summary.main_contribution || "—"}</p>
              <p><strong>Limitations:</strong> {summary.limitations || "—"}</p>
            </div>
            {summary.warnings?.length ? <div className="text-xs text-amber-700">{summary.warnings.join(" · ")}</div> : null}
            {writesEnabled ? (
              <Button variant="outline" size="sm" onClick={() => regenerate("agent-framework")} disabled={generating}>
                {generating ? "Generating…" : "Regenerate experimental summary"}
              </Button>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
