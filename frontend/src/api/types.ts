import type { components } from '../../src/api/generated';

export type PaperMeta = components['schemas']['PaperMeta'];
export type PapersList = components['schemas']['PapersList'];
export type ChunkResponse = components['schemas']['ChunkResponse'];
export type CanonicalChunk = components['schemas']['CanonicalChunk'];
export type PaperChunksResponse = components['schemas']['PaperChunksResponse'];
export type SearchRequest = components['schemas']['SearchRequest'];
export type SearchResponse = components['schemas']['SearchResponse'];
export type HTTPValidationError = components['schemas']['HTTPValidationError'];

export type CorpusInfoResponse = {
  corpus_name?: string | null;
  storage_backend: string;
  chunk_sets_dir?: string | null;
  cache_ready: boolean;
  loaded_at?: number | null;
};

export type CorpusHealthResponse = {
  status: string;
  n_papers: number;
  n_chunks: number;
  n_artifacts: number;
  n_invalid_artifacts: number;
  n_skipped_chunks?: number;
  dedupe_collisions?: number;
  warnings: string[];
};
