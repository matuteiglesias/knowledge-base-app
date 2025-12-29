"use client";
import React, { useState } from "react";
import PapersCard from "@/components/containers/PapersCard";
import ChunksCard from "@/components/containers/ChunksCard";
import type { PaperMeta } from "@/lib/normalizers";

/**
 * HealthChunksPage
 * - Left: PapersCard (select a paper)
 * - Right: ChunksCard (shows chunks for selected paper)
 *
 * PapersCard's onSelectPaper passes a normalized PaperMeta which we keep.
 */
export default function HealthChunksPage() {
  const [selected, setSelected] = useState<PaperMeta | null>(null);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 12, padding: 12 }}>
      <div>
        <PapersCard onSelectPaper={(p) => setSelected(p)} />
      </div>

      <div>
        <ChunksCard paperId={selected?.paperId ?? null} />
      </div>
    </div>
  );
}
