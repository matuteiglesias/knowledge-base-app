"use client";
import React, { KeyboardEvent } from "react";

import type { PaperMeta } from "@/lib/normalizers";

type Props = {
  papers?: PaperMeta[] | null;
  onOpen: (p: PaperMeta) => void;
  onSelect: (p: PaperMeta) => void;
};

export default function PaperList({ papers, onOpen, onSelect }: Props) {
  if (!Array.isArray(papers) || papers.length === 0) {
    return (
      <div data-testid="paper-list" style={{ padding: 12 }}>
        No papers
      </div>
    );
  }

  function onRowKey(e: KeyboardEvent<HTMLTableRowElement>, p: PaperMeta) {
    // Enter selects, Space opens — adjust to taste
    if (e.key === "Enter") {
      e.preventDefault();
      onSelect(p);
    } else if (e.key === " ") {
      e.preventDefault();
      onOpen(p);
    }
  }

  return (
    <table
      data-testid="paper-list"
      style={{ width: "100%", borderCollapse: "collapse" }}
      role="table"
      aria-label="Papers list"
    >
      <thead>
        <tr>
          <th style={{ textAlign: "left", padding: 6 }}>Title</th>
          <th style={{ width: 80, textAlign: "right", padding: 6 }}>Chunks</th>
          <th style={{ width: 140, padding: 6 }} aria-hidden="true" />
        </tr>
      </thead>

      <tbody>
        {papers.map((p) => {
          const key = p.paperId; // paperId is mandatory in normalized PaperMeta
          return (
            <tr
              key={key}
              style={{ borderTop: "1px solid #eee", cursor: "pointer" }}
              tabIndex={0}
              role="row"
              onDoubleClick={() => onOpen(p)}
              onKeyDown={(e) => onRowKey(e, p)}
            >
              <td style={{ padding: 8 }}>
                <div style={{ fontWeight: 600 }}>{p.title ?? p.paperId}</div>
                <div style={{ color: "#666", fontSize: 12, marginTop: 4 }}>
                  {Array.isArray(p.authors) ? p.authors.join(", ") : p.authors ?? ""}
                </div>
              </td>

              <td style={{ padding: 8, textAlign: "right" }}>
                {typeof p.nChunks === "number" ? p.nChunks : "—"}
              </td>

              <td style={{ padding: 8 }}>
                <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                  <button
                    aria-label={`Open ${p.title ?? p.paperId}`}
                    onClick={() => onOpen(p)}
                    title="Open"
                  >
                    Open
                  </button>

                  <button
                    aria-label={`Select ${p.title ?? p.paperId}`}
                    onClick={() => onSelect(p)}
                    title="Select"
                  >
                    Select
                  </button>
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
