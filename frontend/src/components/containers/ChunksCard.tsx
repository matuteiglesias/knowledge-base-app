"use client";
import React from "react";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { usePaperChunks } from "@/hooks/usePaperChunks";
import ChunkList from "@/components/presentational/ChunkList";

export default function ChunksCard({ paperId }: { paperId?: string | null }) {
  const { data, loading, error, reload } = usePaperChunks(paperId);
  const chunks = data?.chunks ?? [];

  if (!paperId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Chunks</CardTitle>
        </CardHeader>
        <CardContent>
          <div style={{ padding: 12 }}>No paper selected</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <CardTitle>Chunks</CardTitle>
        <div>
          <Button size="sm" onClick={() => reload()} disabled={loading}>
            {loading ? "..." : "Reload"}
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        {error && <div style={{ color: "var(--red-600)", paddingBottom: 8 }}>{String(error)}</div>}
        {loading && <div style={{ padding: 8 }}>Loading chunks…</div>}
        <ChunkList chunks={chunks} />
      </CardContent>
    </Card>
  );
}
