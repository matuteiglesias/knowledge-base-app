// frontend/src/hooks/usePapers.ts
"use client";
import { useQuery } from "@tanstack/react-query";

import type { PapersList } from "@/api/types";
import { fetchPapers } from "@/api/papers";

import { normalizePapersList } from "@/lib/normalizers";
import type { PaperMeta } from "@/lib/normalizers";

/**
 * usePapers
 * returns: { data, raw, loading, error, reload, isFetching }
 * - data: PaperMeta[] | null  (frontend-friendly, normalized)
 * - raw: PapersList | null    (raw backend payload)
 */
export function usePapers() {
  const q = useQuery<PapersList, unknown>({
    queryKey: ["papers"],
    queryFn: ({ signal }) => fetchPapers(signal as AbortSignal | undefined),
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
  });

  // Normalize once, predictable shape for consumers
  const data: PaperMeta[] | null = q.data ? normalizePapersList(q.data) : null;

  return {
    data,
    raw: q.data ?? null,
    loading: q.isLoading,
    isFetching: q.isFetching,
    error: q.error ?? null,
    reload: () => q.refetch(),
  };
}



// // in usePapers() return:
// return { data, raw: q.data ?? null, loading: q.isLoading, ... }
