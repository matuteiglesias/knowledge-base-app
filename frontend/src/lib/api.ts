export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ||
  process.env.NEXT_PUBLIC_API_URL || // compatibility fallback only
  "http://127.0.0.1:9000";

function joinUrl(base: string, path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  const b = base.endsWith("/") ? base.slice(0, -1) : base;
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${b}${p}`;
}

async function parseJsonSafe(res: Response): Promise<any> {
  const txt = await res.text();
  if (!txt) return {};
  try {
    return JSON.parse(txt);
  } catch {
    throw new Error(`Invalid JSON response (${res.status}) from ${res.url}`);
  }
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const url = joinUrl(API_BASE, path);
  const res = await fetch(url, { method: "GET", cache: "no-store", ...init });
  const body = await parseJsonSafe(res);
  if (!res.ok) {
    throw new Error(`GET ${url} failed ${res.status}: ${JSON.stringify(body).slice(0, 400)}`);
  }
  return body as T;
}

export async function apiPost<T>(path: string, payload: unknown, init?: RequestInit): Promise<T> {
  const url = joinUrl(API_BASE, path);
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload ?? {}),
    ...init,
  });
  const body = await parseJsonSafe(res);
  if (!res.ok) {
    throw new Error(`POST ${url} failed ${res.status}: ${JSON.stringify(body).slice(0, 400)}`);
  }
  return body as T;
}

export { joinUrl };
