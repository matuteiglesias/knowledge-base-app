import type { components } from "@/api/generated";

export type RawPaperMeta = components["schemas"]["PaperMeta"];
export type RawPapersList = components["schemas"]["PapersList"];
export type RawChunkResponse = components["schemas"]["ChunkResponse"];
export type RawPaperChunksResponse = components["schemas"]["PaperChunksResponse"];
export type RawSearchHit = components["schemas"]["SearchHit"];

export type PaperMeta = {
  paperId: string;
  paperUid?: string | null;
  title: string;
  authors: string[];
  nChunks: number;
  preview?: string | null;
  pages?: number | null;
  sourceFile?: string | null;
  abstract?: string | null;
  date?: string | null;
  year?: number | null;
  venue?: string | null;
  doi?: string | null;
  arxivId?: string | null;
  tags: string[];
  createdAt?: string | null;
  pipelineVersion?: string | null;
  embedModel?: string | null;
  status?: string | null;
};

export type Chunk = {
  id: string;
  paperId?: string;
  pos: number;
  text: string;
  charLen: number;
  headerPath?: string[] | null;
  pages?: (number | null)[] | null;
  meta?: Record<string, unknown> | null;
};

export type PaperChunksNormalized = {
  paperId: string;
  total: number;
  chunks: Chunk[];
};

export function normalizePaperMeta(r: RawPaperMeta): PaperMeta {
  return {
    paperId: r.paper_id,
    paperUid: (r as any).paper_uid ?? null,
    title: r.title,
    authors: Array.isArray(r.authors) ? r.authors : [],
    nChunks: r.n_chunks,
    preview: r.preview ?? null,
    pages: r.pages ?? null,
    sourceFile: r.source_file ?? null,
    abstract: (r as any).abstract ?? null,
    date: (r as any).date ?? null,
    year: (r as any).year ?? null,
    venue: (r as any).venue ?? null,
    doi: (r as any).doi ?? null,
    arxivId: (r as any).arxiv_id ?? null,
    tags: Array.isArray((r as any).tags) ? (r as any).tags : [],
    createdAt: (r as any).created_at ?? null,
    pipelineVersion: (r as any).pipeline_version ?? null,
    embedModel: (r as any).embed_model ?? null,
    status: (r as any).status ?? null,
  };
}

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

export function normalizePapersList(raw: RawPapersList): PaperMeta[] {
  if (!raw || !Array.isArray(raw.papers)) return [];
  const mapped = raw.papers.map((p) => normalizePaperMeta(p));
  mapped.sort((a, b) =>
    String(a.title || "").localeCompare(String(b.title || "")) ||
    a.paperId.localeCompare(b.paperId)
  );
  return mapped;
}

export function normalizePaperChunksResp(r: RawPaperChunksResponse): PaperChunksNormalized {
  const topPaperId = (r as any).paper_id ?? "";
  const total = typeof r.total === "number" ? r.total : (Array.isArray(r.chunks) ? r.chunks.length : 0);
  const chunks: Chunk[] = Array.isArray(r.chunks)
    ? r.chunks.map((c) => normalizeChunkResponse(c, topPaperId))
    : [];
  return { paperId: topPaperId, total, chunks };
}
