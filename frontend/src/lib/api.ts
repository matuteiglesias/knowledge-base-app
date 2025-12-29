// client-side small API helper used by hooks
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9000";

export async function apiGet(path: string) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const res = await fetch(url, { method: "GET", cache: "no-store" });
  const txt = await res.text();
  if (!res.ok) {
    // keep body snippet for diagnostics
    const snippet = txt?.slice(0, 400) ?? "";
    throw new Error(`GET ${url} failed ${res.status}: ${snippet}`);
  }
  try {
    return txt ? JSON.parse(txt) : {};
  } catch (e) {
    throw new Error(`Invalid JSON from ${url}: ${String(e)}`);
  }
}

export async function apiPost(path: string, body: any) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  const txt = await res.text();
  if (!res.ok) throw new Error(`POST ${url} failed ${res.status}: ${txt?.slice(0,400)}`);
  try { return txt ? JSON.parse(txt) : {}; } catch(e) { return {}; }
}
