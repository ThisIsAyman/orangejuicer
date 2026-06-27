/**
 * OrangeTheory API configuration.
 *
 * These constants are reverse-engineered from the OTF mobile app and mirror the
 * values used by the Python `otf-api` library (NodeJSmith/otf-api,
 * src/otf_api/auth/auth.py and src/otf_api/api/client.py). They are not secrets:
 * the Cognito App Client has no client secret and these IDs are public to any
 * OTF app user.
 */

// AWS Cognito user pool (us-east-1).
export const COGNITO_REGION = "us-east-1";
export const COGNITO_USER_POOL_ID = "us-east-1_dYDxUeyL1";
export const COGNITO_CLIENT_ID = "1457d19r0pcjgmp5agooi0rb1b";

// OTF data API hostnames.
export const HOST_IO = "api.orangetheory.io"; // perf summaries + bookings
export const HOST_TELEMETRY = "api.yuzu.orangetheory.com"; // heart-rate telemetry
export const HOST_CO = "api.orangetheory.co"; // body comp, benchmarks, lifetime stats

/** Hosts the proxy is allowed to forward to (kept in sync with the Worker allowlist). */
export const ALLOWED_HOSTS = [HOST_IO, HOST_TELEMETRY, HOST_CO];

/**
 * Base URL of the stateless relay proxy (Cloudflare Worker / Vercel Edge).
 * Configured at build time via `VITE_OTF_PROXY_URL`. When unset, the SPA assumes
 * a DirectTransport (browser extension / desktop) is in use.
 */
export const OTF_PROXY_URL: string | undefined = import.meta.env.VITE_OTF_PROXY_URL;

/** Spoofed mobile-app user agent OTF expects. Set by the proxy (browsers forbid JS from setting it). */
export const OTF_USER_AGENT = "okhttp/4.12.0";
