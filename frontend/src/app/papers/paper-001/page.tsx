'use client'

import { useMemo } from 'react'
import { usePaperChunks } from '@/hooks/usePaperChunks'
import { usePaperSummary } from '@/hooks/usePaperSummary'

export default function PaperPage() {
  const paperId = 'p1'
  const { data, loading: chunksLoading, error: chunksError } = usePaperChunks(paperId)
  const { summary, loading: summaryLoading, error: summaryError, generate, regenerate, generating } = usePaperSummary(paperId)

  const chunks = data?.chunks ?? []
  const title = useMemo(() => summary?.title || `Paper ${paperId}`, [summary, paperId])

  return (
    <div className="grid md:grid-cols-[300px_1fr] gap-6">
      <aside className="space-y-4">
        <div className="p-4 border rounded">
          <h2 className="font-semibold">Summary</h2>

          {summaryLoading ? <p className="text-sm text-slate-500 mt-2">Loading summary...</p> : null}

          {!summaryLoading && summaryError ? (
            <p className="text-sm text-red-600 mt-2">Failed to load summary.</p>
          ) : null}

          {!summaryLoading && !summary && !summaryError ? (
            <div className="mt-2 space-y-2">
              <p className="text-sm text-slate-600">No summary yet.</p>
              <button className="border rounded px-3 py-1" onClick={() => generate('mock')} disabled={generating}>
                {generating ? 'Generating...' : 'Generate summary'}
              </button>
            </div>
          ) : null}

          {summary ? (
            <div className="mt-3 space-y-2 text-sm">
              <p>{summary.one_line || '(empty summary)'}</p>
              <p className="text-slate-500">Provider: {summary.provider} · Generated: {new Date(summary.generated_at).toLocaleString()}</p>
              <button className="border rounded px-3 py-1" onClick={() => regenerate('mock')} disabled={generating}>
                {generating ? 'Regenerating...' : 'Regenerate'}
              </button>
            </div>
          ) : null}
        </div>
      </aside>

      <main>
        <h1 className="text-xl font-bold mb-4">{title}</h1>
        {chunksLoading ? <p>Loading chunks...</p> : null}
        {chunksError ? <p className="text-red-600">Failed to load chunks.</p> : null}
        <div className="space-y-3">
          {chunks.map((c) => (
            <article key={c.chunk_id} className="border rounded p-3">
              <div className="text-xs text-slate-500">{c.chunk_id}</div>
              <p className="text-sm mt-1">{c.text}</p>
            </article>
          ))}
        </div>
      </main>
    </div>
  )
}
