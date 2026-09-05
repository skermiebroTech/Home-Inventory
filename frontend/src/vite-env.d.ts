/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** The API origin. Empty means the same origin, which production uses. */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
