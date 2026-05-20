"use client";
import { useQuery } from "@tanstack/react-query";
import { fetchCorpusInfo, fetchCorpusHealth } from "@/api/papers";

export function useCorpus() {
  const info = useQuery({
    queryKey: ["corpus-info"],
    queryFn: ({ signal }) => fetchCorpusInfo(signal as AbortSignal | undefined),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const health = useQuery({
    queryKey: ["corpus-health"],
    queryFn: ({ signal }) => fetchCorpusHealth(signal as AbortSignal | undefined),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  return {
    info: info.data ?? null,
    health: health.data ?? null,
    loading: info.isLoading || health.isLoading,
    error: info.error ?? health.error ?? null,
    reload: () => {
      void info.refetch();
      void health.refetch();
    },
  };
}
