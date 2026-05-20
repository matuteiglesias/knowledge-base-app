// src/api/schema.ts
/* Raw re-exports from generator */
import type { components } from "@/api/generated"; // adjust path if generated elsewhere

export type RawPaperMeta = components["schemas"]["PaperMeta"];
export type RawPapersList = components["schemas"]["PapersList"];
export type RawChunkResponse = components["schemas"]["ChunkResponse"];
export type RawPaperChunksResponse = components["schemas"]["PaperChunksResponse"];
export type RawSearchHit = components["schemas"]["SearchHit"];
/* etc */

/* Frontend-friendly types (single, stable shapes used inside UI) */
export type PaperMeta = {
  paperId: string;
  title: string;
  authors: string[] | null;
  nChunks: number;
  preview?: string | null;
  pages?: number | null;
  sourceFile?: string | null;
  createdAt?: string | null;
  pipelineVersion?: string | null;
  embedModel?: string | null;
  year?: number | null;
  venue?: string | null;
  status?: string | null;
};

export type Chunk = {
  id: string;            // chunk_id
  paperId?: string;      // present on parent response if needed
  pos: number;           // chunk_index
  text: string;
  charLen: number;
  headerPath?: string[] | null;
  pages?: (number | null)[] | null; // normalize tuple -> array
  meta?: Record<string, unknown> | null;
};

/* PaperChunksNormalized - shape returned by normalizePaperChunksResp */
export type PaperChunksNormalized = {
  paperId: string;
  total: number;
  chunks: Chunk[];
};


/* Normalizers */

/** Normalize a single raw PaperMeta -> UI PaperMeta */
export function normalizePaperMeta(r: RawPaperMeta): PaperMeta {
  return {
    paperId: r.paper_id,
    title: r.title,
    authors: r.authors ?? null,
    nChunks: r.n_chunks,
    preview: r.preview ?? null,
    pages: r.pages ?? null,
    sourceFile: r.source_file ?? null,
    createdAt: (r as any).created_at ?? null,
    pipelineVersion: (r as any).pipeline_version ?? null,
    embedModel: (r as any).embed_model ?? null,
    year: (r as any).year ?? null,
    venue: (r as any).venue ?? null,
    status: (r as any).status ?? null,
  };
}

/** Normalize a single raw ChunkResponse -> UI Chunk */
export function normalizeChunkResponse(r: RawChunkResponse, parentPaperId?: string): Chunk {
  return {
    id: r.chunk_id,
    paperId: parentPaperId ?? (r as any).paper_id ?? undefined,
    pos: typeof r.chunk_index === "number" ? r.chunk_index : 0,
    text: r.text ?? "",
    charLen: typeof r.char_len === "number" ? r.char_len : (r.text ? r.text.length : 0),
    headerPath: r.header_path ?? null,
    pages: Array.isArray(r.pages) ? [r.pages[0], r.pages[1]] : null,
    meta: r.meta ?? null,
  };
}

/** Normalize the PapersList payload from the backend into an array of UI PaperMeta */
export function normalizePapersList(raw: RawPapersList): PaperMeta[] {
  if (!raw) {
    console.warn("normalizePapersList called with falsy raw:", raw);
    return [];
  }
  if (!Array.isArray(raw.papers)) {
    console.warn("normalizePapersList: expected raw.papers array, got:", raw);
    return [];
  }
  const mapped = raw.papers.map((p) => normalizePaperMeta(p));
  // optional: stable sort by nChunks desc then title
  mapped.sort((a, b) => (b.nChunks || 0) - (a.nChunks || 0) || String((a.title || "")).localeCompare(String((b.title || ""))));
  return mapped;
}

/** Normalize the PaperChunksResponse payload into PaperChunksNormalized */
export function normalizePaperChunksResp(r: RawPaperChunksResponse): PaperChunksNormalized {
  const topPaperId = (r as any).paper_id ?? "";
  const total = typeof r.total === "number" ? r.total : (Array.isArray(r.chunks) ? r.chunks.length : 0);
  const chunks: Chunk[] = Array.isArray(r.chunks)
    ? r.chunks.map((c) => normalizeChunkResponse(c, topPaperId))
    : [];
  return {
    paperId: topPaperId,
    total,
    chunks,
  };
}