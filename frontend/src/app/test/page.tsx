// /home/matias/Documents/paper-kb/frontend/src/app/health/page.tsx
"use client";

import React, { useEffect, useState, useRef } from "react";

/* shadcn UI components (adjust import paths if your project differs) */
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";



import type { Paper, Chunk, SearchHit, SummaryTask } from '@/api/papers'


/* util: robust fetch with fallback to public/dev-data */
async function robustFetchJSON(url: string, fallback?: string, opts?: RequestInit) {
  try {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (err) {
    if (fallback) {
      try {
        const rf = await fetch(fallback);
        if (!rf.ok) throw new Error(`Fallback HTTP ${rf.status}`);
        return await rf.json();
      } catch (err2) {
        throw new Error(`Both fetch and fallback failed: ${err} / ${err2}`);
      }
    }
    throw err;
  }
}

export default function HealthPage() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [topicsSample, setTopicsSample] = useState<any[]>([]);

  const [searchQ, setSearchQ] = useState("");
  const [searchHits, setSearchHits] = useState<SearchHit[]>([]);

  const [summaryQ, setSummaryQ] = useState("");
  const [summaryTask, setSummaryTask] = useState<SummaryTask | null>(null);
  const pollRef = useRef<number | null>(null);

  // const API_BASE = ""; // relative (frontend -> backend proxy). Change if needed (e.g., http://127.0.0.1:9000)
  // NEXT_PUBLIC_API_URL=http://localhost:9000

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9000"


  useEffect(() => {
    loadPapers();
    loadTopics();
    // cleanup on unmount: stop polling
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
      }
    };
  }, []);

  async function loadPapers() {
    try {
      // const data = await robustFetchJSON(`${API_BASE}/api/papers`, "/dev-data/papers.json");
      const data = await robustFetchJSON(`/api/papers`);
      // backend returns { n, papers: [...] } ; fallback dev file might be different shape
      const arr = data.papers ?? data;
      setPapers(arr);
    } catch (err) {
      console.error("loadPapers error:", err);
      setPapers([]);
    }
  }

  async function openPaper(p: Paper) {
    setSelectedPaper(p);
    setChunks([]);
    try {
      const res = await robustFetchJSON(`${API_BASE}/api/papers/${encodeURIComponent(p.paper_id)}`, `/dev-data/papers.json`);
      // expected shape { paper_id, total, chunks: [...] }
      const chunksList = Array.isArray(res?.chunks) ? res.chunks : Array.isArray(res) ? res : [];
      setChunks(chunksList);
      
    } catch (err) {
      console.error("openPaper error:", err);
      setChunks([]);
    }
  }

  async function runSearch(q?: string) {
    const query = q ?? searchQ;
    setSearchHits([]);
    if (!query || !query.trim()) return;
    try {
      const payload = { q: query, k: 6 };
      const res = await robustFetchJSON(`${API_BASE}/api/search`, "/dev-data/search-results.json", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const hits = Array.isArray(res?.hits) ? res.hits : Array.isArray(res) ? res : [];
      setSearchHits(hits);
      
    } catch (err) {
      console.error("search error:", err);
      setSearchHits([]);
    }
  }

  async function loadTopics() {
    try {
      const res = await robustFetchJSON(`${API_BASE}/api/topics`, "/dev-data/topics.json");
      setTopicsSample(res.sample ?? []);
    } catch (err) {
      console.error("topics load error:", err);
      setTopicsSample([]);
    }
  }

  async function submitSummary() {
    // prefer explicit summaryQ, fallback to single chunk or paper title
    let q = (summaryQ || "").trim();
    if (!q) {
      if (selectedPaper && selectedPaper.title) q = `Summarize paper ${selectedPaper.title}`;
      else if (chunks && chunks.length > 0) q = chunks.slice(0, 3).map((c) => c.text.slice(0, 200)).join("\n\n");
      else q = "Give a short summary";
    }
    const body = { q, paper_id: selectedPaper?.paper_id ?? undefined, k: 6 };
    try {
      const resp = await fetch(`${API_BASE}/api/summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error(`status ${resp.status}`);
      const dj = await resp.json();
      if (!dj.task_id) {
        // If backend returns result inline (legacy), show it
        setSummaryTask({ task_id: "inline", status: "done", result: dj });
        return;
      }
      const taskId = dj.task_id;
      setSummaryTask({ task_id: taskId, status: dj.status ?? "queued", request: body, result: null });
      // start polling
      startPolling(taskId);
    } catch (err) {
      console.error("submitSummary error:", err);
    }
  }

  function startPolling(taskId: string) {
    if (pollRef.current) window.clearInterval(pollRef.current);
    const pollFn = async () => {
      try {
        const r = await fetch(`${API_BASE}/api/summary/${encodeURIComponent(taskId)}`);
        if (!r.ok) {
          console.warn("poll fetch error", r.status);
          return;
        }
        const j = await r.json();
        setSummaryTask(j);
        if (j.status && j.status !== "queued" && j.status !== "running") {
          // done
          if (pollRef.current) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      } catch (err) {
        console.error("poll error", err);
      }
    };
    // poll immediately then every 1.25s
    pollFn();
    const id = window.setInterval(pollFn, 1250);
    pollRef.current = id;
  }

  return (
    <div style={{ padding: 20, display: "grid", gridTemplateColumns: "320px 1fr 360px", gap: 16 }}>
      {/* Left: Papers list */}
      <Card>
        <CardHeader>
          <CardTitle>Backend · Health & Smoke</CardTitle>
        </CardHeader>
        <CardContent>
          <div style={{ marginBottom: 8 }}>
            <Label>Available papers</Label>
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <Button size="sm" onClick={() => loadPapers()}>
                Reload
              </Button>
              <Button size="sm" onClick={() => setPapers([])}>
                Clear
              </Button>
            </div>
          </div>

          <Separator style={{ margin: "8px 0" }} />

          <div style={{ maxHeight: 420, overflow: "auto" }}>
            {papers.length === 0 ? (
              <div>No papers found (backend or dev-data missing)</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Title</TableHead>
                    <TableHead style={{ width: 90 }}>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {papers.map((p) => (
                    <TableRow key={p.paper_id}>
                      <TableCell style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 220 }}>
                        {p.title ?? p.paper_id}
                      </TableCell>
                      <TableCell>
                        <div style={{ display: "flex", gap: 6 }}>
                          <Button size="sm" onClick={() => openPaper(p)}>
                            Open
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => setSelectedPaper(p)}>
                            Select
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Middle: Paper inspector / Search / Chunks */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <Card>
          <CardHeader>
            <CardTitle>Inspector</CardTitle>
          </CardHeader>
          <CardContent>
            <div style={{ marginBottom: 8 }}>
              <Label>Selected paper</Label>
              <div style={{ marginTop: 6 }}>
                {selectedPaper ? (
                  <>
                    <div style={{ fontWeight: 600 }}>{selectedPaper.title ?? selectedPaper.paper_id}</div>
                    <div style={{ color: "#666", fontSize: 12 }}>{selectedPaper.authors ?? ""}</div>
                    <div style={{ marginTop: 8 }}>
                      <Button size="sm" onClick={() => openPaper(selectedPaper)}>
                        Load chunks
                      </Button>
                    </div>
                  </>
                ) : (
                  <div>No paper selected</div>
                )}
              </div>
            </div>

            <Separator style={{ margin: "10px 0" }} />

            <div style={{ marginBottom: 8 }}>
              <Label>Search</Label>
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                <Input placeholder="Query..." value={searchQ} onChange={(e) => setSearchQ(e.target.value)} />
                <Button onClick={() => runSearch()}>Search</Button>
              </div>
            </div>

            <div style={{ marginTop: 10 }}>
              <Label>Search hits</Label>
              <div style={{ maxHeight: 180, overflow: "auto", marginTop: 8 }}>
                {searchHits.length === 0 ? (
                  <div style={{ color: "#666" }}>No hits (run a search)</div>
                ) : (
                  searchHits.map((h) => (
                    <Card key={h.id} style={{ marginBottom: 8 }}>
                      <CardContent>
                        <div style={{ fontWeight: 600 }}>{(h.meta?.paper_id ?? "").slice(0, 60)}</div>
                        <div style={{ marginTop: 6 }}>{h.text?.slice(0, 300)}</div>
                        <div style={{ marginTop: 8 }}>
                          <Button size="sm" onClick={() => { if (h.meta?.paper_id) openPaper({paper_id: h.meta.paper_id, title: h.meta.title}) }}>
                            Open paper
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Chunks</CardTitle>
          </CardHeader>
          <CardContent>
            <div style={{ maxHeight: 360, overflow: "auto" }}>
              {chunks.length === 0 ? (
                <div style={{ color: "#666" }}>No chunks loaded (open a paper)</div>
              ) : (
                chunks.map((c) => (
                  <Card key={c.id} style={{ marginBottom: 8 }}>
                    <CardContent>
                      <div style={{ fontSize: 13 }}>{(c.text ?? "").slice(0, 600)}</div>
                      <div style={{ marginTop: 6, color: "#666", fontSize: 12 }}>{JSON.stringify(c.meta ?? {})}</div>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>



      {/* Right: Summary / Topics */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <Card>
          <CardHeader>
            <CardTitle>Summarize (async)</CardTitle>
          </CardHeader>
          <CardContent>
            <div style={{ marginBottom: 8 }}>
              <Label>Query (optional)</Label>
              <Input placeholder="Text to summarize or empty for paper-based" value={summaryQ} onChange={(e) => setSummaryQ(e.target.value)} />
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <Button onClick={() => submitSummary()}>Run summary</Button>
              <Button variant="outline" onClick={() => { setSummaryQ(""); setSummaryTask(null); if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; } }}>
                Reset
              </Button>
            </div>

            <div style={{ marginTop: 12 }}>
              <Label>Task status</Label>
              <div style={{ marginTop: 8 }}>
                {summaryTask ? (
                  <div>
                    <div><strong>task:</strong> {summaryTask.task_id}</div>
                    <div><strong>status:</strong> {summaryTask.status}</div>
                    <div style={{ marginTop: 8 }}>
                      {summaryTask.result ? (
                        <Card>
                          <CardContent>
                            <div style={{ fontWeight: 600 }}>Answer</div>
                            <pre style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>{summaryTask.result.answer ?? JSON.stringify(summaryTask.result)}</pre>
                            <div style={{ marginTop: 8, color: "#444" }}>
                              <details>
                                <summary>RAG support (provenance)</summary>
                                <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(summaryTask.result.rag ?? summaryTask.result, null, 2)}</pre>
                              </details>
                            </div>
                          </CardContent>
                        </Card>
                      ) : (
                        <div style={{ color: "#666" }}>No result yet. Polling…</div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div style={{ color: "#666" }}>No summary task started</div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Topics sample</CardTitle>
          </CardHeader>
          <CardContent>
            <div style={{ maxHeight: 380, overflow: "auto" }}>
              {topicsSample.length === 0 ? (
                <div style={{ color: "#666" }}>No topics sample</div>
              ) : (
                topicsSample.map((s, i) => (
                  <div key={i} style={{ borderBottom: "1px dashed #eee", padding: 8 }}>
                    <div style={{ fontWeight: 600 }}>{s.meta?.paper_id ?? s.id ?? `item-${i}`}</div>
                    <div style={{ color: "#666", fontSize: 12 }}>{JSON.stringify(s.meta ?? {})}</div>
                  </div>
                ))
              )}
            </div>
            <div style={{ marginTop: 8 }}>
              <Button onClick={() => loadTopics()}>Reload topics</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
