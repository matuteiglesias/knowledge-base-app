"use client";
import React from "react";

import type { Chunk } from "@/lib/normalizers";

type Props = {
  chunks?: Chunk[] | null;
};

function safeMetaPreview(meta: Record<string, unknown> | null | undefined, max = 200) {
  if (!meta) return "";
  try {
    const s = JSON.stringify(meta);
    return s.length > max ? s.slice(0, max) + "…" : s;
  } catch {
    return "[unserializable meta]";
  }
}

export default function ChunkList({ chunks }: Props) {
  if (!Array.isArray(chunks) || chunks.length === 0) {
    return (
      <div data-testid="chunk-list" style={{ padding: 12 }}>
        No chunks yet
      </div>
    );
  }

  return (
    <div data-testid="chunk-list" style={{ display: "grid", gap: 8 }}>
      {chunks.map((c) => (
        <article
          key={c.id}
          style={{
            border: "1px solid #eee",
            padding: 10,
            borderRadius: 6,
            background: "#fff",
          }}
          aria-labelledby={`chunk-${c.id}-title`}
          role="article"
          tabIndex={0}
        >
          <div id={`chunk-${c.id}-title`} style={{ fontSize: 13, color: "#222" }}>
            {c.text ? (c.text.length > 600 ? c.text.slice(0, 600) + "…" : c.text) : "<no text>"}
          </div>

          <div style={{ fontSize: 11, color: "#666", marginTop: 6 }}>
            {safeMetaPreview(c.meta)}
          </div>

          <div style={{ marginTop: 8, display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button
              onClick={() => {
                // small convenience: copy text to clipboard if available
                if (typeof navigator !== "undefined" && navigator.clipboard) {
                  navigator.clipboard.writeText(c.text ?? "").catch(() => {});
                }
              }}
              aria-label="Copy chunk text"
              title="Copy"
            >
              Copy
            </button>
          </div>
        </article>
      ))}
    </div>
  );
}
