"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchPaperSummary, generatePaperSummary } from "@/api/papers";
import type { PaperSummary, SummaryGenerateRequest } from "@/api/types";

export function usePaperSummary(paperId?: string | null) {
  const qc = useQueryClient();
  const key = ["paperSummary", paperId];

  const q = useQuery<PaperSummary | null>({
    queryKey: key,
    enabled: Boolean(paperId),
    queryFn: async ({ signal }) => {
      if (!paperId) return null;
      try {
        return await fetchPaperSummary(paperId, signal as AbortSignal | undefined);
      } catch (err: any) {
        if (String(err?.message || "").includes(" failed 404")) return null;
        throw err;
      }
    },
    staleTime: 60_000,
  });

  const m = useMutation({
    mutationFn: async (input?: Partial<SummaryGenerateRequest>) => {
      if (!paperId) throw new Error("Missing paper id");
      return generatePaperSummary(paperId, { provider: "mock", force: false, ...(input || {}) });
    },
    onSuccess: (data) => qc.setQueryData(key, data),
  });

  return {
    summary: q.data ?? null,
    loading: q.isLoading,
    error: q.error,
    generate: (provider: "mock" | "agent-framework" = "mock") => m.mutate({ provider, force: false }),
    regenerate: (provider: "mock" | "agent-framework" = "mock") => m.mutate({ provider, force: true }),
    generating: m.isPending,
    reload: () => q.refetch(),
  };
}
