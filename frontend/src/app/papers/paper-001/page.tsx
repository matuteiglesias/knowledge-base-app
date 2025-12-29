'use client'
import React, { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { apiGet } from '@/lib/api'
import SnippetList from '@/components/presentational/SnippetList'
// import type { PaperDetail } from '@/api/papers'
fetchPapers

export default function PaperPage(){
  const params = useParams()
  const paperId = params?.paperId
  const [paper, setPaper] = useState<PaperDetail| null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if(!paperId) return
    setLoading(true)
    // path uses your public/dev-data layout: papers/papers-001.json
    // map param to file name (paper-001 -> papers-001.json)
    const filename = `papers/${paperId}.json`.replace(/^\/+/,'')
    apiGet(filename).then(d => setPaper(d)).finally(()=>setLoading(false))
  },[paperId])

  if(loading) return <div>Loading paper...</div>
  if(!paper) return <div>Could not load paper</div>

  return (
    <div className="grid md:grid-cols-[260px_1fr_320px] gap-6">
      {/* left meta */}
      <aside className="space-y-4">
        <div className="p-4 border rounded">
          <h2 className="font-semibold">{paper.title}</h2>
          <div className="text-sm text-slate-500">{paper.authors?.join?.(', ')}</div>
          <div className="mt-3 flex flex-col gap-2">
            <button className="btn">Summarize</button>
            <button className="btn-secondary">Ask question</button>
            <button className="btn-ghost">Export</button>
          </div>
        </div>
        <div className="p-3 border rounded text-sm">
          <strong>Summaries</strong>
          <div className="mt-2">{paper.summaries?.map(s => <div key={s.id}><div className="text-xs text-slate-500">{s.type} · cached {new Date(s.cached_at).toLocaleString()}</div>
          <div className="text-sm">{s.summary_text}</div></div>)}</div>
        </div>
      </aside>

      {/* main reader */}
      <article>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold">{paper.title}</h1>
            <div className="text-sm text-slate-500">Reader · {paper.n_chunks} chunks</div>
          </div>
          <div>
            <input placeholder="Search within paper..." className="border px-2 py-1 rounded" />
          </div>
        </div>

        <SnippetList snippets={paper.chunks} />
      </article>

      {/* right rail: RAG / answers */}
      <aside className="space-y-4">
        <div className="p-4 border rounded">
          <strong>Ask question</strong>
          <div className="mt-2">
            <textarea className="w-full border rounded px-2 py-1" placeholder="Ask something about this paper" />
            <button className="btn mt-2">Run RAG (stub)</button>
          </div>
        </div>
        <div className="p-4 border rounded text-sm text-slate-500">
          <strong>Provenance</strong>
          <div className="mt-2">When RAG runs, sources will appear here with chunk links.</div>
        </div>
      </aside>
    </div>
  )
}
