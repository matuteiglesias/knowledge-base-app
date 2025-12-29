'use client'
import React, { useEffect, useState } from 'react'
import { apiGet } from '@/lib/api'
import type { PaperMeta } from '@/api/types'
import PapersCard from '@/components/containers/PapersCard'

export default function HomePage(){
  const [papers, setPapers] = useState<PaperMeta[]>([])
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    apiGet('papers.json').then((d) => {
      if(!mounted) return
      setPapers(d.papers || [])
    }).finally(()=>setLoading(false))
    return ()=>{ mounted = false }
  },[])

  const filtered = q ? papers.filter(p=> (p.title||'').toLowerCase().includes(q.toLowerCase()) || (p.authors||[]).join(' ').toLowerCase().includes(q.toLowerCase())) : papers

  return (
    <main className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">Papers</h1>
        <div className="flex gap-2 items-center">
          <input className="border rounded px-3 py-2" placeholder="Quick filter title/author" value={q} onChange={e=>setQ(e.target.value)} />
          <button className="btn">Ingest papers</button>
        </div>
      </div>

      {loading ? <div>Loading...</div> : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map(p => <PapersCard key={p.paper_id} paper={p} />)}
        </div>
      )}
    </main>
  )
}
