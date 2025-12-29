// frontend/src/api/papers.ts
import type { PapersList, PaperChunksResponse, HTTPValidationError } from "@/api/types";


// frontend/src/api/config.ts
export const API_BASE =
  // prefer runtime env variable; fallback to relative path
  (typeof process !== "undefined" && (process.env.NEXT_PUBLIC_API_BASE as string)) ||
  "";



/** Parse JSON safely (returns null on parse error). */
async function parseJsonSafe(res: Response): Promise<any | null> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

// fetchPaperChunks

/** low-level typed fetch that returns structured errors for the caller */
async function typedFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, init);

  if (!res.ok) {
    const parsed = await parseJsonSafe(res);
    if (res.status === 422 && parsed) {
      const ve = parsed as HTTPValidationError;
      const err = new Error("Validation error");
      (err as any).status = 422;
      (err as any).validation = ve;
      throw err;
    }
    const bodyText = parsed ? JSON.stringify(parsed) : await res.text().catch(() => "");
    const err = new Error(`HTTP ${res.status} ${res.statusText}: ${bodyText}`);
    (err as any).status = res.status;
    (err as any).body = parsed;
    throw err;
  }

  const body = await parseJsonSafe(res);
  if (body === null) throw new Error("Expected JSON response but got non-JSON body");
  return body as T;
}

export async function fetchPapers(signal?: AbortSignal): Promise<PapersList> {
  return typedFetch<PapersList>(`${API_BASE}/api/papers`, { signal });
}

export async function fetchPaperChunks(
  paperId: string,
  offset = 0,
  limit = 50,
  signal?: AbortSignal
): Promise<PaperChunksResponse> {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  return typedFetch<PaperChunksResponse>(`/api/papers/${encodeURIComponent(paperId)}?${params}`, {
    signal,
  });
}
