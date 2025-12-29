'use client'
import React, { useEffect, useState } from 'react'
import { apiGet } from '@/lib/api'
import type { Topic } from '@/api/papers'

export default function TopicsPage(){
  const [topics, setTopics] = useState<Topic[]>([])
  const [sel, setSel] = useState<Topic | null>(null)

  useEffect(()=> {
    apiGet('topics.json').then(d => { setTopics(d.topics || []); setSel((d.topics || [])[0] || null) })
  },[])

  return (
    <div className="grid md:grid-cols-[260px_1fr] gap-6">
      <aside className="space-y-3">
        <input placeholder="Search topics..." className="border px-2 py-1 rounded w-full" />
        <div className="bg-white p-2 rounded border">
          {topics.map(t => <div key={t.topic_id} className={`p-2 rounded cursor-pointer ${sel?.topic_id===t.topic_id?'bg-slate-50':''}`} onClick={()=>setSel(t)}>{t.label} <span className="text-xs text-slate-400">· {t.count}</span></div>)}
        </div>
      </aside>

      <main>
        {sel ? (
          <div>
            <h2 className="text-xl font-semibold">{sel.label}</h2>
            <div className="text-sm text-slate-500 mb-4">{sel.key_phrases.join(' · ')}</div>

            <div className="mb-4">
              <strong>Top papers</strong>
              <ul className="list-disc ml-5">
                {sel.top_papers.map(p=> <li key={p.paper_id}><a href={`/papers/${p.paper_id}`} className="text-sky-600">{p.title}</a></li>)}
              </ul>
            </div>

            <div>
              <strong>Top snippets</strong>
              <div className="mt-2 space-y-2">
                {sel.top_snippets.map(s=> <div key={s.chunk_id} className="p-3 border rounded bg-white">{s.text}</div>)}
              </div>
            </div>

            <div className="mt-6">
              <button className="btn">Create digest</button>
            </div>
          </div>
        ) : <div>No topics</div>}
      </main>
    </div>
  )
}
