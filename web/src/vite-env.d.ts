/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the stateless OTF relay proxy (Cloudflare Worker). */
  readonly VITE_OTF_PROXY_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
