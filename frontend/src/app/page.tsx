'use client'
import React, { useMemo, useState } from 'react'
import { API_BASE } from '@/lib/api'
import { usePapers } from '@/hooks/usePapers'
import { useCorpus } from '@/hooks/useCorpus'
import ChunksCard from '@/components/containers/ChunksCard'
import type { PaperMeta as NormalizedPaperMeta } from '@/lib/normalizers'

export default function HomePage() {
  const { data: papers, loading: papersLoading, error: papersError } = usePapers()
  const { info, health, loading: corpusLoading, error: corpusError } = useCorpus()
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState<NormalizedPaperMeta | null>(null)

  const filtered = useMemo(() => {
    const list = papers ?? []
    if (!q.trim()) return list
    const qq = q.toLowerCase()
    return list.filter((p) =>
      [p.title, p.paperId, p.sourceFile, p.venue, p.status, (p.authors || []).join(' ')].join(' ').toLowerCase().includes(qq)
    )
  }, [papers, q])

  const err = papersError || corpusError
  const loading = papersLoading || corpusLoading

  return (
    <main className="space-y-4">
      <section className="border rounded p-3 bg-slate-50">
        <div className="font-semibold">Active corpus</div>
        <div className="text-sm mt-1">
          <div>corpus: <strong>{info?.corpus_name || 'unknown'}</strong></div>
          <div>backend: <code>{API_BASE}</code></div>
          <div>storage: {info?.storage_backend || 'unknown'} · cache_ready: {String(info?.cache_ready ?? false)}</div>
          <div>papers: {health?.n_papers ?? 0} · chunks: {health?.n_chunks ?? 0}</div>
        </div>
      </section>

      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">Papers</h1>
        <input className="border rounded px-3 py-2" placeholder="Filter title/author/venue/status" value={q} onChange={e => setQ(e.target.value)} />
      </div>

      {loading && <div>Loading live corpus data…</div>}
      {err && <div className="text-red-600">Backend unavailable. Check {API_BASE}. Error: {String(err)}</div>}

      {!loading && !err && filtered.length === 0 && (
        <div className="border rounded p-4">Corpus is empty (no papers found).</div>
      )}

      {!loading && !err && filtered.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="border rounded p-2 overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th>Title</th><th>Year</th><th>Venue</th><th>Chunks</th><th>Source/Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => (
                  <tr key={p.paperId} className="border-b cursor-pointer hover:bg-slate-50" onClick={() => setSelected(p)}>
                    <td>{p.title || p.paperId}</td>
                    <td>{p.year ?? '—'}</td>
                    <td>{p.venue ?? '—'}</td>
                    <td>{p.nChunks}</td>
                    <td>{p.sourceFile || p.status || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ChunksCard paperId={selected?.paperId ?? filtered[0]?.paperId ?? null} />
        </div>
      )}
    </main>
  )
}
