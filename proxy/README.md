# orangejuicer OTF relay proxy

A **stateless** Cloudflare Worker that lets the browser dashboard call
OrangeTheory's private API. It exists only to work around two browser
restrictions — **CORS** and the **forbidden `User-Agent` header** — that block a
static site from calling OTF directly.

## What it does (and doesn't)

- Forwards `GET /relay?target=<otf-url>` to OrangeTheory, passing through the
  browser's `Authorization` (Cognito ID token) and `koji-*` headers, and adding
  the mobile `User-Agent` OTF expects.
- Adds CORS response headers so the SPA can read the reply.
- **Stores nothing, logs nothing**, holds no credentials, and only forwards to an
  allowlist of three OTF hostnames. It is a dumb relay; if it disappeared, no
  user data would be lost or exposed.

Trust note: tokens transit the proxy in flight, so run an instance you trust
(self-host it — see below). Users wanting zero third party in the path can use
the browser-extension build instead, which talks to OTF directly.

## Deploy

Requires a free Cloudflare account and [`wrangler`](https://developers.cloudflare.com/workers/wrangler/).

```bash
cd proxy
npx wrangler deploy
```

Set `ALLOWED_ORIGIN` in `wrangler.toml` to your SPA's origin (e.g.
`https://<you>.github.io`) to restrict who can use the proxy.

After deploy, wrangler prints a URL like `https://otf-proxy.<you>.workers.dev`.
Point the SPA at it by building with:

```bash
cd ../web
VITE_OTF_PROXY_URL=https://otf-proxy.<you>.workers.dev npm run build
```

## Local test

```bash
cd proxy
npx wrangler dev      # serves http://localhost:8787
```

Then run the SPA with `VITE_OTF_PROXY_URL=http://localhost:8787 npm run dev`.

## Other hosts

The same handler runs on Vercel/Netlify edge functions with minor wrapper
changes; the relay logic in `worker.js` is platform-agnostic.
