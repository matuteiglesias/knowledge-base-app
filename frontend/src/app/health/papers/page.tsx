// "use client";

// import React, { useCallback, useEffect, useState, useRef } from "react";

// /* UI primitives you used in the snippet */
// import {
//   Card,
//   CardHeader,
//   CardTitle,
//   CardContent,
// } from "@/components/ui/card"; // adapt path if needed
// import { Button } from "@/components/ui/button";
// import { Label } from "@/components/ui/label";
// import { Separator } from "@/components/ui/separator";
// import {
//   Table,
//   TableBody,
//   TableCell,
//   TableHead,
//   TableHeader,
//   TableRow,
// } from "@/components/ui/table";

// type Paper = {
//   paper_id?: string | null;
//   title?: string | null;
//   authors?: string[] | null;
//   n_chunks?: number | null;
//   preview?: string | null;
//   pages?: number | null;
//   source_file?: string | null;
// };

// type Props = {
//   /** optional callback when a paper is "selected" */
//   onSelectPaper?: (p: Paper) => void;
//   /** optional base path to open paper viewer; defaults to /paper */
//   viewerBasePath?: string;
// };

// // export default function HealthPapersCard({ onSelectPaper, viewerBasePath = "/paper" }: Props) {
// //   const [papers, setPapers] = useState<Paper[]>([]);
// //   const [loading, setLoading] = useState(false);
// //   const [err, setErr] = useState<string | null>(null);


//   // inside HealthPapersCard component



// export default function HealthPapersCard({ onSelectPaper, viewerBasePath = "/paper" }: Props) {
//     const [papers, setPapers] = useState<Paper[]>([]);
//     const prevPapersRef = useRef<Paper[]>([]);         // << new
//     const [loading, setLoading] = useState(false);
//     const [err, setErr] = useState<string | null>(null);
  


//     // whenever we update papers, keep the ref in sync
//     const replacePapers = (next: Paper[]) => {
//       prevPapersRef.current = next;
//       setPapers(next);
//     };
//     const preservePrev = () => {
//       // helper if we want to preserve previous list explicitly
//       setPapers(prevPapersRef.current);
//     };
  
//     const dedupe = useCallback((arr: Paper[]) => {
//       const m = new Map<string, Paper>();
//       for (const p of arr) {
//         const pid = p.paper_id ?? p.title ?? "";
//         const src = p.source_file ?? "";
//         const key = `${pid}||${src}`;
//         if (!m.has(key)) m.set(key, p);
//       }
//       return Array.from(m.values());
//     }, []);
  
//     const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9000";
  
//     // NOTE: removed `papers` from deps — use prevPapersRef instead
//     const loadPapers = useCallback(async () => {
//       setErr(null);
//       setLoading(true);
//       const prev = prevPapersRef.current; // snapshot without creating a dep
//       try {
//         const url = `${API_BASE}/api/papers?t=${Date.now()}`;
//         const res = await fetch(url, { method: "GET", cache: "no-store" });
  
//         // diagnostics (keep as desired)
//         console.debug("loadPapers: status", res.status, "ok", res.ok);
//         for (const [k, v] of res.headers.entries()) console.debug("hdr", k, v);
//         const rawText = await res.clone().text();
//         console.debug("loadPapers raw length", rawText.length, rawText.slice(0, 800));
  
//         if (!res.ok) {
//           const snippet = rawText ? rawText.slice(0, 400) : "<<no body>>";
//           throw new Error(`Backend error ${res.status}: ${snippet}`);
//         }
  
//         let body: any;
//         try {
//           body = rawText ? JSON.parse(rawText) : {};
//         } catch (e) {
//           throw new Error("Failed to parse JSON from backend: " + String(e));
//         }
  
//         const raw = Array.isArray(body?.papers) ? body.papers : [];
  
//         const normalized: Paper[] = raw.map((r: any) => ({
//           paper_id: r.paper_id ?? r.title ?? null,
//           title: r.title ?? r.paper_id ?? null,
//           authors: r.authors ?? null,
//           n_chunks: typeof r.n_chunks === "number" ? r.n_chunks : (r.n_chunks ? Number(r.n_chunks) : null),
//           preview: r.preview ?? null,
//           pages: r.pages ?? null,
//           source_file: r.source_file ?? null,
//         }));
  
//         const deduped = dedupe(normalized);
//         deduped.sort((a, b) => (b.n_chunks || 0) - (a.n_chunks || 0) || String((a.title || "")).localeCompare(String((b.title || ""))));
  
//         console.debug("loadPapers: fetched", raw.length, "-> normalized", normalized.length, "-> deduped", deduped.length);
  
//         if (deduped.length === 0) {
//           console.warn("loadPapers: backend returned 0 papers; preserving previous list.");
//           setErr("Backend returned 0 papers on reload (previous list preserved). Check server logs or network tab.");
//           // preserve prev (nothing to change because prevPapersRef.current is already reflected in state)
//           preservePrev();
//         } else {
//           setErr(null);
//           // use helper which updates both ref and state atomically
//           replacePapers(deduped);
//         }
//       } catch (e: any) {
//         console.error("loadPapers failed", e);
//         setErr(e?.message ?? String(e));
//         // preserve previous papers on error
//         preservePrev();
//       } finally {
//         setLoading(false);
//       }
//     }, [API_BASE, dedupe]); // << papers removed here
  
//     useEffect(() => {
//       // auto-load on mount, stable because loadPapers no longer depends on `papers`
//       loadPapers();
//     }, [loadPapers]);
  
  
//     function clearPapers() {
//       prevPapersRef.current = []; // keep ref consistent
//       setPapers([]);
//       setErr(null);
//     }
  
//     function selectPaper(p: Paper) {
//       if (onSelectPaper) onSelectPaper(p);
//       // visually mark it as selected (put it at top) and keep ref consistent
//       replacePapers([p, ...prevPapersRef.current.filter((x) => x !== p)]);
//     }

//   function openPaper(p: Paper) {
//     // Default behavior: open a new tab to viewerBasePath?paper_id=<encoded>
//     // Adjust to your frontend routing: e.g. `/papers/${encodeURIComponent(id)}`
//     const pid = encodeURIComponent(p.paper_id ?? p.title ?? "");
//     const url = `${viewerBasePath}?paper_id=${pid}`;
//     window.open(url, "_blank", "noopener,noreferrer");
//   }

//   // function selectPaper(p: Paper) {
//   //   if (onSelectPaper) onSelectPaper(p);
//   //   // also visually mark it as selected (simple approach: put it at top)
//   //   setPapers((prev) => [p, ...prev.filter((x) => x !== p)]);
//   // }

//   return (
//     <Card>
//       <CardHeader>
//         <CardTitle>Backend · Health & Smoke</CardTitle>
//       </CardHeader>

//       <CardContent>
//         <div style={{ marginBottom: 8 }}>
//           <Label>Available papers</Label>
//           <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
//             <Button size="sm" onClick={() => loadPapers()} disabled={loading}>
//               {loading ? "Loading…" : "Reload"}
//             </Button>
//             <Button size="sm" onClick={() => clearPapers()} variant="ghost">
//               Clear
//             </Button>

//             <Button size="sm" variant="ghost" onClick={async () => {
//               try {
//                 const r = await fetch(`${API_BASE}/api/papers?t=${Date.now()}`, { cache: "no-store" });
//                 const txt = await r.text();
//                 // opens a new tab with the raw JSON (for dev only)
//                 window.open("data:application/json," + encodeURIComponent(txt));
//               } catch (err) {
//                 console.error(err);
//                 alert("Failed to fetch raw JSON: " + String(err));
//               }
//             }}>Raw JSON</Button>



//           </div>
//         </div>

//         <Separator style={{ margin: "8px 0" }} />

//         <div style={{ maxHeight: 420, overflow: "auto" }}>
//           {err ? (
//             <div style={{ color: "var(--red-600)", padding: 8 }}>Error: {err}</div>
//           ) : papers.length === 0 ? (
//             <div style={{ padding: 8 }}>No papers found (backend or dev-data missing)</div>
//           ) : (
//             <Table>
//               <TableHeader>
//                 <TableRow>
//                   <TableHead>Title</TableHead>
//                   <TableHead style={{ width: 90 }}>Actions</TableHead>
//                 </TableRow>
//               </TableHeader>
//               <TableBody>
//                 {papers.map((p) => (
//                   <TableRow key={`${p.paper_id ?? p.title}::${p.source_file ?? ""}`}>
//                     <TableCell
//                       style={{
//                         whiteSpace: "nowrap",
//                         overflow: "hidden",
//                         textOverflow: "ellipsis",
//                         maxWidth: 220,
//                       }}
//                     >
//                       <div title={(p.title ?? p.paper_id) || undefined}>
//                         {p.title ?? p.paper_id}
//                         {p.n_chunks ? <span style={{ color: "#666", marginLeft: 8 }}>({p.n_chunks})</span> : null}
//                       </div>
//                       <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
//                         {p.authors ? (Array.isArray(p.authors) ? p.authors.join(", ") : String(p.authors)) : ""}
//                       </div>
//                     </TableCell>

//                     <TableCell>
//                       <div style={{ display: "flex", gap: 6 }}>
//                         <Button size="sm" onClick={() => openPaper(p)}>
//                           Open
//                         </Button>
//                         <Button size="sm" variant="outline" onClick={() => selectPaper(p)}>
//                           Select
//                         </Button>




//                       </div>
//                     </TableCell>
//                   </TableRow>
//                 ))}
//               </TableBody>
//             </Table>
//           )}
//         </div>
//       </CardContent>
//     </Card>
//   );
// }

"use client";
import React from "react";
import PapersCard from "@/components/containers/PapersCard";

export default function HealthPapersPage() {
  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: 12 }}>
      <PapersCard />
    </div>
  );
}
