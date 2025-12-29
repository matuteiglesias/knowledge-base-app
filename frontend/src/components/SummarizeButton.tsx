// SummarizeButton.tsx
"use client";
import React, { useEffect, useRef, useState } from "react";

type SummarizeRequest = {
  paperId?: string;
  snippetIds?: string[];   // optional: prefer ids for targeted summaries
  text?: string;           // optional: raw text (small)
  mode?: "short" | "long";
};

type SummaryStatus = {
  task_id: string;
  status: "queued" | "processing" | "done" | "error" | "cancelled";
  summary?: string;
  error?: string;
  model?: string;
  tokens?: number;
};

export default function SummarizeButton({
  paperId,
  snippetIds,
  text,
  mode = "short",
  label = "Summarize",
}: {
  paperId?: string;
  snippetIds?: string[];
  text?: string;
  mode?: "short"|"long";
  label?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<SummaryStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
    };
  }, []);

  async function createSummary(req: SummarizeRequest) {
    setError(null);
    setBusy(true);
    setStatus(null);
    try {
      const resp = await fetch("/api/summary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`Server error: ${resp.status} ${txt}`);
      }
      const body = await resp.json();
      const task_id = body.task_id || body.id || body.paperId;
      if (!task_id) {
        throw new Error("No task id returned");
      }
      const initial: SummaryStatus = { task_id, status: body.status || "queued" };
      setStatus(initial);
      startPolling(task_id);
    } catch (e: any) {
      setError(e?.message || String(e));
      setBusy(false);
    }
  }

  function startPolling(task_id: string) {
    let attempts = 0;
    const maxAttempts = 120; // ~2 minutes depending poll interval
    const baseInterval = 1000; // 1s initial

    async function pollOnce() {
      attempts++;
      try {
        const resp = await fetch(`/api/summary/${encodeURIComponent(task_id)}`);
        if (!resp.ok) {
          // keep polling on transient errors, but record
          if (attempts > 8) {
            throw new Error(`Polling failed: ${resp.status}`);
          }
          return;
        }
        const body = await resp.json();
        setStatus(body as SummaryStatus);
        if (body.status === "done" || body.status === "error" || body.status === "cancelled") {
          // finished
          setBusy(false);
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      } catch (e: any) {
        // on error, if too many attempts, stop
        if (attempts >= maxAttempts) {
          setError("Giving up polling after repeated failures.");
          setBusy(false);
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
        }
      }
    }

    // exponential backoff schedule approximated via interval change
    let interval = baseInterval;
    pollRef.current = window.setInterval(async () => {
      pollOnce();
      // increase interval gradually (not strictly exponential to keep code simple)
      if (interval < 5000) interval += 500;
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
      pollRef.current = window.setInterval(pollOnce, interval);
    }, interval);
  }

  async function onClick() {
    const req: SummarizeRequest = { paperId, snippetIds, text, mode };
    await createSummary(req);
  }

  async function onCancel() {
    if (!status?.task_id) return;
    try {
      setBusy(true);
      const resp = await fetch(`/api/summary/${encodeURIComponent(status.task_id)}`, {
        method: "DELETE",
      });
      if (!resp.ok) {
        throw new Error("Cancel request failed");
      }
      setStatus((s) => s ? {...s, status: "cancelled"} : s);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(false);
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    }
  }

  return (
    <div className="inline-flex items-center gap-2">
      <button
        className={`inline-flex items-center gap-2 px-3 py-1 rounded-md text-sm border ${busy ? "opacity-60 cursor-not-allowed" : "hover:bg-slate-50"}`}
        disabled={busy}
        onClick={onClick}
        aria-pressed={busy}
        aria-label={label}
      >
        {busy ? (
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>
        ) : null}
        <span>{busy ? "Working…" : label}</span>
      </button>

      {status ? (
        <div className="text-xs text-slate-600">
          <div><strong>Status:</strong> {status.status}</div>
          {status.status === "done" && status.summary ? (
            <details className="mt-1">
              <summary className="cursor-pointer text-blue-600">View summary</summary>
              <div className="whitespace-pre-wrap mt-2 text-sm text-slate-800">{status.summary}</div>
            </details>
          ) : null}
        </div>
      ) : null}

      {busy && status?.task_id ? (
        <button onClick={onCancel} className="text-xs px-2 py-1 rounded bg-red-50 text-red-600 border border-red-100">Cancel</button>
      ) : null}

      {error ? <div className="text-xs text-red-600 ml-2">{error}</div> : null}
    </div>
  );
}
