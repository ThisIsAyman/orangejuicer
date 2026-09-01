/**
 * orangejuicer — stateless OTF relay proxy (Cloudflare Worker).
 *
 * Purpose: let the static SPA call OrangeTheory's private mobile API from a
 * browser, which is otherwise blocked by CORS and by the browser forbidding
 * JS from setting the `User-Agent` header.
 *
 * Guarantees:
 *  - Stateless: stores nothing, logs no tokens or bodies. Each request is
 *    forwarded and forgotten.
 *  - Holds no credentials: the browser sends the `Authorization: Bearer <id_token>`
 *    header per request; the Worker only passes it through.
 *  - Only forwards to an allowlist of OTF hostnames (no open relay).
 *
 * Contract:
 *   GET  /relay?target=<url-encoded https OTF url, e.g. https://api.orangetheory.io/...>
 *        Forwarded headers: Authorization, koji-member-id, koji-member-email.
 *   OPTIONS /relay  -> CORS preflight.
 *
 * Configure ALLOWED_ORIGIN via wrangler env vars to restrict which site may use
 * the proxy ("*" allows any origin).
 */

const ALLOWED_HOSTS = [
  "api.orangetheory.io",
  "api.yuzu.orangetheory.com",
  "api.orangetheory.co",
];

// Headers we relay from the browser to OTF (everything else is dropped).
const FORWARD_HEADERS = ["authorization", "koji-member-id", "koji-member-email"];

const OTF_USER_AGENT = "okhttp/4.12.0";

function corsHeaders(env) {
  const origin = (env && env.ALLOWED_ORIGIN) || "*";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, koji-member-id, koji-member-email",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(env);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    const url = new URL(request.url);
    if (url.pathname !== "/relay") {
      return new Response("Not found", { status: 404, headers: cors });
    }
    if (request.method !== "GET") {
      return new Response("Method not allowed", { status: 405, headers: cors });
    }

    const target = url.searchParams.get("target");
    if (!target) {
      return new Response("Missing target", { status: 400, headers: cors });
    }

    let targetUrl;
    try {
      targetUrl = new URL(target);
    } catch {
      return new Response("Invalid target URL", { status: 400, headers: cors });
    }

    if (targetUrl.protocol !== "https:" || !ALLOWED_HOSTS.includes(targetUrl.hostname)) {
      return new Response("Target host not allowed", { status: 403, headers: cors });
    }

    // Build a clean outbound request: only the allowlisted headers + spoofed UA.
    const outHeaders = new Headers();
    for (const name of FORWARD_HEADERS) {
      const value = request.headers.get(name);
      if (value) outHeaders.set(name, value);
    }
    outHeaders.set("User-Agent", OTF_USER_AGENT);
    outHeaders.set("Accept", "application/json");
    outHeaders.set("Content-Type", "application/json");

    let otfResponse;
    try {
      // redirect: "manual" so a 3xx from OTF never causes the Authorization
      // header to be replayed to a host outside the allowlist.
      otfResponse = await fetch(targetUrl.toString(), {
        method: "GET",
        headers: outHeaders,
        redirect: "manual",
      });
    } catch {
      return new Response("Upstream fetch failed", { status: 502, headers: cors });
    }

    if (otfResponse.status >= 300 && otfResponse.status < 400) {
      return new Response("Upstream redirect not allowed", { status: 502, headers: cors });
    }

    // Relay status + body, stripping upstream CORS/security headers and adding ours.
    const respHeaders = new Headers(cors);
    const contentType = otfResponse.headers.get("Content-Type");
    if (contentType) respHeaders.set("Content-Type", contentType);

    return new Response(otfResponse.body, {
      status: otfResponse.status,
      headers: respHeaders,
    });
  },
};
