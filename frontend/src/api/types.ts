// frontend/src/api/types.ts
import type { components } from '../../src/api/generated'; // adjust path

export type PaperMeta = components['schemas']['PaperMeta'];  // summary metadata about a paper: paper_id, title, n_chunks, preview, created_at, etc. Good for listing.
export type PapersList = components['schemas']['PapersList'];
export type ChunkResponse = components['schemas']['ChunkResponse']; // Notice: it does not include paper_id. The PaperChunksResponse contains the paper_id at top level.
export type CanonicalChunk = components['schemas']['CanonicalChunk']; // canonical database chunk (has paper_id + all internal fields). Good for server-side models and ingestion.
export type PaperChunksResponse = components['schemas']['PaperChunksResponse']; // payload for a paper's chunks: { paper_id, total, chunks: ChunkResponse[] }.
export type SearchRequest = components['schemas']['SearchRequest'];
export type SearchResponse = components['schemas']['SearchResponse'];
export type HTTPValidationError = components['schemas']['HTTPValidationError'];
// add more aliases you use frequently
