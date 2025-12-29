// frontend/src/hooks/usePaperChunks.ts
"use client";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchPaperChunks } from "@/api/papers";
import type { PaperChunksResponse, HTTPValidationError } from "@/api/types";

import { normalizePaperChunksResp } from "@/lib/normalizers";
import type { PaperChunksNormalized } from "@/lib/normalizers";

/**
 * usePaperChunks(paperId?, opts?)
 * returns: { data, raw, loading, error, validation, reload, isFetching }
 * - data: { paperId: string; total: number; chunks: Chunk[] } | null
 *   (the exact normalized shape is PaperChunksNormalized)
 */
export function usePaperChunks(
  paperId?: string | null,
  opts?: { offset?: number; limit?: number }
) {
  const offset = opts?.offset ?? 0;
  const limit = opts?.limit ?? 200;

  const q = useQuery<PaperChunksResponse, unknown>({
    queryKey: ["paperChunks", paperId, offset, limit],
    queryFn: ({ signal }) => {
      if (!paperId) throw new Error("Missing paperId");
      return fetchPaperChunks(
        paperId,
        offset,
        limit,
        signal as AbortSignal | undefined
      );
    },
    enabled: Boolean(paperId),
    staleTime: 1000 * 60 * 5,
  });

  // Normalized result: { paperId, total, chunks: Chunk[] } or null
  const data: PaperChunksNormalized | null = useMemo(() => {
    if (!q.data) return null;
    return normalizePaperChunksResp(q.data);
  }, [q.data]);

  const validation: HTTPValidationError | null = (q.error as any)?.validation ?? null;

  return {
    data,
    raw: q.data ?? null,
    loading: q.isLoading,
    isFetching: q.isFetching,
    error: q.error ?? null,
    validation,
    reload: () => q.refetch(),
  };
}
