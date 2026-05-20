'use client'
import React, { useEffect, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { API_BASE } from '@/lib/api'
import { usePapers } from '@/hooks/usePapers'
import { useCorpus } from '@/hooks/useCorpus'
import ChunksCard from '@/components/containers/ChunksCard'
import PaperSummaryCard from '@/components/containers/PaperSummaryCard'
import { fetchPaperSummary } from '@/api/papers'

type SummaryRowStatus = 'loading' | 'ready' | 'missing' | 'error'

export default function HomePage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { data: papers, loading: papersLoading, error: papersError } = usePapers()
  const { info, health, loading: corpusLoading, error: corpusError } = useCorpus()
  const [q, setQ] = useState('')
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null)
  const [summaryStatusByPaper, setSummaryStatusByPaper] = useState<Record<string, SummaryRowStatus>>({})

  const filtered = useMemo(() => {
    const list = papers ?? []
    if (!q.trim()) return list
    const qq = q.toLowerCase()
    return list.filter((p) =>
      [p.title, p.paperId, p.sourceFile, (p.authors || []).join(' ')].join(' ').toLowerCase().includes(qq)
    )
  }, [papers, q])

  useEffect(() => {
    const fromUrl = searchParams.get('paper')
    if (fromUrl && fromUrl !== selectedPaperId) {
      setSelectedPaperId(fromUrl)
      return
    }

    if (!fromUrl && !selectedPaperId && filtered.length > 0) {
      const first = filtered[0].paperId
      setSelectedPaperId(first)
      const params = new URLSearchParams(searchParams.toString())
      params.set('paper', first)
      router.replace(`/?${params.toString()}`)
    }
  }, [filtered, router, searchParams, selectedPaperId])

  useEffect(() => {
    const ids = (papers ?? []).map((p) => p.paperId)
    if (!ids.length) {
      setSummaryStatusByPaper({})
      return
    }

    let cancelled = false
    setSummaryStatusByPaper((prev) => {
      const next = { ...prev }
      for (const id of ids) {
        if (!next[id]) next[id] = 'loading'
      }
      return next
    })

    Promise.all(ids.map(async (paperId) => {
      try {
        await fetchPaperSummary(paperId)
        return [paperId, 'ready'] as const
      } catch (err) {
        const msg = String((err as Error)?.message || '')
        if (msg.includes(' failed 404')) return [paperId, 'missing'] as const
        return [paperId, 'error'] as const
      }
    })).then((results) => {
      if (cancelled) return
      setSummaryStatusByPaper((prev) => {
        const next = { ...prev }
        for (const [paperId, status] of results) next[paperId] = status
        return next
      })
    })

    return () => {
      cancelled = true
    }
  }, [papers])

  const selected = filtered.find((p) => p.paperId === selectedPaperId) ?? null

  const err = papersError || corpusError
  const loading = papersLoading || corpusLoading

  const onSelectPaper = (paperId: string) => {
    setSelectedPaperId(paperId)
    const params = new URLSearchParams(searchParams.toString())
    params.set('paper', paperId)
    router.replace(`/?${params.toString()}`)
  }

  const summaryBadge = (paperId: string) => {
    const status = summaryStatusByPaper[paperId] ?? 'loading'
    if (status === 'ready') return <span className="text-xs rounded bg-green-100 text-green-800 px-2 py-0.5">ready</span>
    if (status === 'missing') return <span className="text-xs rounded bg-slate-100 text-slate-700 px-2 py-0.5">missing</span>
    if (status === 'error') return <span className="text-xs rounded bg-red-100 text-red-700 px-2 py-0.5">error</span>
    return <span className="text-xs rounded bg-amber-100 text-amber-700 px-2 py-0.5">loading</span>
  }

  return (
    <main className="space-y-4">
      <section className="border rounded p-3 bg-slate-50">
        <div className="font-semibold">Paper Corpus Workbench</div>
        <div className="text-sm mt-1">
          <div>corpus: <strong>{info?.corpus_name || 'unknown'}</strong> · backend: <code>{API_BASE}</code></div>
          <div>papers: {health?.n_papers ?? 0} · chunks: {health?.n_chunks ?? 0} · health: {health?.status || 'unknown'}</div>
          <div className="text-slate-500">Diagnostics: <code>/health/*</code> · Dev sandbox: <code>/test</code> · API reference: <code>/api-docs</code></div>
        </div>
      </section>

      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">Paper Browser</h1>
        <input className="border rounded px-3 py-2" placeholder="Filter title, author, source" value={q} onChange={e => setQ(e.target.value)} />
      </div>

      {loading && <div>Loading corpus…</div>}
      {err && <div className="text-red-600">Could not reach backend at {API_BASE}. Check that the API is running.</div>}

      {!loading && !err && filtered.length === 0 && (
        <div className="border rounded p-4">No papers found in this corpus.</div>
      )}

      {!loading && !err && filtered.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="border rounded p-2 overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th>Title</th><th>Chunks</th><th>Summary</th><th>Source</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => {
                  const isSelected = p.paperId === selected?.paperId
                  return (
                    <tr key={p.paperId} className={`border-b cursor-pointer hover:bg-slate-50 ${isSelected ? 'bg-slate-100' : ''}`} onClick={() => onSelectPaper(p.paperId)}>
                      <td>{p.title || p.paperId}</td>
                      <td>{p.nChunks}</td>
                      <td>{summaryBadge(p.paperId)}</td>
                      <td>{p.sourceFile || '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <section className="space-y-4">
            <div className="border rounded p-3">
              <h2 className="font-semibold">Selected paper</h2>
              {selected ? (
                <div className="text-sm mt-1">
                  <div className="font-medium">{selected.title || selected.paperId}</div>
                  <div className="text-slate-600">{selected.nChunks} chunks · source: {selected.sourceFile || 'unknown'}</div>
                  <div className="text-slate-500">paper_id: {selected.paperId}</div>
                </div>
              ) : (
                <p className="text-sm text-slate-600 mt-1">Select a paper to inspect chunks and summaries.</p>
              )}
            </div>

            <PaperSummaryCard paperId={selected?.paperId ?? null} />
            <ChunksCard paperId={selected?.paperId ?? null} />
          </section>
        </div>
      )}
    </main>
  )
}
