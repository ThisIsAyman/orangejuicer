/**
 * Transport-agnostic OTF request layer.
 *
 * The same endpoint code (endpoints.ts) runs against either:
 *  - ProxyTransport  — default for the hosted SPA; routes through the stateless
 *    relay proxy so the browser's CORS rules and forbidden-header rules don't
 *    block OTF's private API.
 *  - DirectTransport — for environments without CORS limits (a browser extension
 *    with host permissions, or a desktop/Tauri build); calls OTF directly.
 */

import { ALLOWED_HOSTS, OTF_PROXY_URL } from "./config";

export interface OtfRequest {
  /** OTF API hostname (must be in ALLOWED_HOSTS). */
  host: string;
  /** Path beginning with "/". */
  path: string;
  /** Query parameters. */
  query?: Record<string, string | number | boolean | undefined>;
  /** Extra headers (e.g. koji-member-id). Authorization is added by the caller. */
  headers?: Record<string, string>;
}

export interface Transport {
  request<T = unknown>(req: OtfRequest): Promise<T>;
}

function buildQuery(query?: OtfRequest["query"]): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined) params.set(k, String(v));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

function targetUrl(req: OtfRequest): string {
  if (!ALLOWED_HOSTS.includes(req.host)) {
    throw new Error(`Refusing to call non-allowlisted host: ${req.host}`);
  }
  return `https://${req.host}${req.path}${buildQuery(req.query)}`;
}

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`OTF request failed (${res.status}): ${body.slice(0, 300)}`);
  }
  return (await res.json()) as T;
}

/**
 * Routes requests through the stateless relay proxy. The proxy receives the full
 * OTF URL via `?target=`, forwards the Authorization + extra headers, injects the
 * mobile `user-agent`, and adds CORS response headers. It stores nothing.
 */
export class ProxyTransport implements Transport {
  constructor(private readonly proxyBase: string) {}

  async request<T = unknown>(req: OtfRequest): Promise<T> {
    const target = targetUrl(req);
    const url = `${this.proxyBase.replace(/\/$/, "")}/relay?target=${encodeURIComponent(target)}`;
    const res = await fetch(url, { method: "GET", headers: req.headers ?? {} });
    return readJson<T>(res);
  }
}

/** Calls OTF directly. Only works where CORS is not enforced (extension/desktop). */
export class DirectTransport implements Transport {
  async request<T = unknown>(req: OtfRequest): Promise<T> {
    const res = await fetch(targetUrl(req), { method: "GET", headers: req.headers ?? {} });
    return readJson<T>(res);
  }
}

/** Pick the transport based on build config: proxy when configured, else direct. */
export function defaultTransport(): Transport {
  return OTF_PROXY_URL ? new ProxyTransport(OTF_PROXY_URL) : new DirectTransport();
}
