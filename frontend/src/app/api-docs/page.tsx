"use client";

import Link from "next/link";
import { API_BASE } from "@/lib/api";

export default function ApiDocsPage() {
  const swagger = `${API_BASE}/docs`;
  const redoc = `${API_BASE}/redoc`;
  const openapi = `${API_BASE}/openapi.json`;

  return (
    <main className="mx-auto max-w-3xl space-y-5 px-6 py-12">
      <div>
        <div className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500">Paper KB read service</div>
        <h1 className="mt-2 text-2xl font-semibold">API documentation</h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          The FastAPI read service owns its OpenAPI contract and documentation. The workbench links to that live surface rather than bundling a second documentation renderer.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <a className="rounded border bg-white p-4 text-sm font-medium hover:bg-slate-50" href={swagger} target="_blank" rel="noreferrer">Swagger UI</a>
        <a className="rounded border bg-white p-4 text-sm font-medium hover:bg-slate-50" href={redoc} target="_blank" rel="noreferrer">ReDoc</a>
        <a className="rounded border bg-white p-4 text-sm font-medium hover:bg-slate-50" href={openapi} target="_blank" rel="noreferrer">OpenAPI JSON</a>
      </div>

      <Link className="text-sm text-sky-700 underline underline-offset-2" href="/?tab=corpus">Return to workbench</Link>
    </main>
  );
}
