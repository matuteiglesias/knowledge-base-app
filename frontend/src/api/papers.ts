import type {
  PapersList,
  PaperChunksResponse,
  HTTPValidationError,
  PaperMeta,
  CorpusInfoResponse,
  CorpusHealthResponse,
  PaperSummary,
  SummaryGenerateRequest,
} from "@/api/types";
import { apiGet, apiPost } from "@/lib/api";

export type SearchHit = {
  id: string;
  text: string;
  score?: number | null;
  meta?: Record<string, unknown> | null;
  chunk_id?: string | null;
  paper_id?: string | null;
};

export type SearchResults = {
  capability: string;
  query: string;
  k: number;
  hits: SearchHit[];
};

async function typedGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  try {
    return await apiGet<T>(path, { signal });
  } catch (err: any) {
    if (err?.status === 422) {
      const ve = (err?.body || {}) as HTTPValidationError;
      (err as any).validation = ve;
    }
    throw err;
  }
}

export async function fetchCorpusInfo(signal?: AbortSignal): Promise<CorpusInfoResponse> {
  return typedGet<CorpusInfoResponse>("/api/corpus", signal);
}

export async function fetchCorpusHealth(signal?: AbortSignal): Promise<CorpusHealthResponse> {
  return typedGet<CorpusHealthResponse>("/api/corpus/health", signal);
}

export async function fetchPapers(signal?: AbortSignal): Promise<PapersList> {
  return typedGet<PapersList>("/api/papers", signal);
}

export async function fetchPaper(paperId: string, signal?: AbortSignal): Promise<PaperMeta> {
  return typedGet<PaperMeta>(`/api/papers/${encodeURIComponent(paperId)}`, signal);
}

export async function fetchPaperChunks(
  paperId: string,
  offset = 0,
  limit = 50,
  signal?: AbortSignal
): Promise<PaperChunksResponse> {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  return typedGet<PaperChunksResponse>(`/api/papers/${encodeURIComponent(paperId)}/chunks?${params}`, signal);
}

export async function searchPaperChunks(
  q: string,
  opts?: { k?: number; paperId?: string | null },
  signal?: AbortSignal
): Promise<SearchResults> {
  return apiPost<SearchResults>(
    "/api/search",
    { q, k: opts?.k ?? 20, paper_id: opts?.paperId || null },
    { signal }
  );
}

export async function fetchPaperSummary(paperId: string, signal?: AbortSignal): Promise<PaperSummary> {
  return typedGet<PaperSummary>(`/api/papers/${encodeURIComponent(paperId)}/summary`, signal);
}

export async function generatePaperSummary(
  paperId: string,
  body: SummaryGenerateRequest = { provider: "mock", force: false },
  signal?: AbortSignal
): Promise<PaperSummary> {
  return apiPost<PaperSummary>(`/api/papers/${encodeURIComponent(paperId)}/summary:generate`, body, { signal });
}
