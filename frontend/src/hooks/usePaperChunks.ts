"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchPaperChunks } from "@/api/papers";
import type { PaperChunksResponse, HTTPValidationError } from "@/api/types";
import { normalizePaperChunksResp } from "@/lib/normalizers";
import type { PaperChunksNormalized } from "@/lib/normalizers";

type ValidationCarrier = { validation?: HTTPValidationError };

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
      return fetchPaperChunks(paperId, offset, limit, signal as AbortSignal | undefined);
    },
    enabled: Boolean(paperId),
    staleTime: 1000 * 60 * 5,
  });

  const data: PaperChunksNormalized | null = useMemo(() => {
    if (!q.data) return null;
    return normalizePaperChunksResp(q.data);
  }, [q.data]);

  const validation: HTTPValidationError | null =
    q.error && typeof q.error === "object"
      ? (q.error as ValidationCarrier).validation ?? null
      : null;

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
