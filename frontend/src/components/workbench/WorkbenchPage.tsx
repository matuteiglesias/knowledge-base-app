"use client";

import { useCallback, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api";
import { useCorpus } from "@/hooks/useCorpus";
import { usePapers } from "@/hooks/usePapers";
import { Badge } from "@/components/ui/badge";
import { TAB_CATALOG, resolveWorkbenchProduct, type WorkbenchTabId } from "@/workbench/product";
import { WORKBENCH_TAB_COMPONENTS } from "@/workbench/registry";

type Props = {
  initialTab?: string | null;
  initialPaperId?: string | null;
};

export default function WorkbenchPage({ initialTab, initialPaperId }: Props) {
  const product = useMemo(() => resolveWorkbenchProduct(), []);
  const { data: papers, loading: papersLoading, error: papersError } = usePapers();
  const { info, health, loading: corpusLoading, error: corpusError } = useCorpus();

  const firstTab = product.tabs.includes(initialTab as WorkbenchTabId)
    ? (initialTab as WorkbenchTabId)
    : product.defaultTab;
  const [activeTab, setActiveTab] = useState<WorkbenchTabId>(firstTab);
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(initialPaperId || null);

  const effectiveSelectedPaperId = selectedPaperId || papers?.[0]?.paperId || null;
  const selectedPaper = useMemo(
    () => (papers || []).find((paper) => paper.paperId === effectiveSelectedPaperId) || null,
    [papers, effectiveSelectedPaperId]
  );

  const navigate = useCallback((tab: WorkbenchTabId, paperId?: string | null) => {
    const nextTab = product.tabs.includes(tab) ? tab : product.defaultTab;
    const resolvedPaper = paperId !== undefined ? paperId : effectiveSelectedPaperId;
    setActiveTab(nextTab);
    if (paperId !== undefined) setSelectedPaperId(paperId);

    const params = new URLSearchParams();
    params.set("tab", nextTab);
    if (resolvedPaper) params.set("paper", resolvedPaper);
    window.history.replaceState(null, "", `/?${params.toString()}`);
  }, [effectiveSelectedPaperId, product]);

  const loading = papersLoading || corpusLoading;
  const error = papersError || corpusError;
  const ActiveTab = WORKBENCH_TAB_COMPONENTS[activeTab];

  return (
    <main className="mx-auto min-h-screen max-w-[1500px] space-y-5 px-4 py-5 sm:px-6 lg:px-8">
      <header className="rounded-xl border bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500">{product.id}</div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">{product.label}</h1>
            <p className="mt-1 max-w-3xl text-sm text-slate-600">{product.description}</p>
          </div>
          <div className="grid grid-cols-2 gap-x-5 gap-y-2 text-sm sm:grid-cols-4">
            <div><div className="text-xs text-slate-500">Corpus</div><div className="font-medium">{info?.corpus_name || "unknown"}</div></div>
            <div><div className="text-xs text-slate-500">Papers</div><div className="font-medium">{health?.n_papers ?? papers?.length ?? "—"}</div></div>
            <div><div className="text-xs text-slate-500">Chunks</div><div className="font-medium">{health?.n_chunks ?? "—"}</div></div>
            <div><div className="text-xs text-slate-500">Health</div><Badge variant={health?.status === "ok" ? "secondary" : "outline"}>{health?.status || "unknown"}</Badge></div>
          </div>
        </div>

        <nav className="mt-5 flex gap-1 overflow-x-auto border-t pt-3" aria-label="Workbench tabs">
          {product.tabs.map((tabId) => {
            const tab = TAB_CATALOG[tabId];
            const active = tabId === activeTab;
            return (
              <button
                key={tabId}
                type="button"
                onClick={() => navigate(tabId)}
                className={`whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition ${active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"}`}
                aria-current={active ? "page" : undefined}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>

        <div className="mt-2 flex flex-col gap-1 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span>{TAB_CATALOG[activeTab].description}</span>
          <span className="font-mono">backend {API_BASE}</span>
        </div>
      </header>

      {loading ? <div className="rounded border bg-white p-6 text-sm text-slate-500">Loading governed corpus…</div> : null}
      {error ? <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700">Could not load the Paper KB read service: {String(error)}</div> : null}

      {!loading && !error ? (
        <ActiveTab
          papers={papers || []}
          selectedPaper={selectedPaper}
          corpusInfo={info}
          corpusHealth={health}
          navigate={navigate}
        />
      ) : null}
    </main>
  );
}
