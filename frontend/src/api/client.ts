/**
 * The HTTP client.
 *
 * Every reply from the server carries the envelope `{ data, error }`. This
 * module unwraps it, so the rest of the interface never sees the envelope. A
 * failure becomes an `ApiError` with the stable code that the server sent.
 *
 * The client also renews an expired access token once per request. The auth
 * store registers the callbacks below, which keeps this file free of a
 * circular import.
 */

import type { Envelope } from './types'

/** The API origin. Empty means the same origin, which production uses. */
export const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: Record<string, unknown> | null

  constructor(
    message: string,
    code: string,
    status: number,
    details: Record<string, unknown> | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }

  /** True when the account must sign in again. */
  get isAuthFailure(): boolean {
    return this.status === 401
  }
}

interface TokenBridge {
  accessToken: () => string | null
  refreshToken: () => string | null
  onRefreshed: (access: string, refresh: string) => void
  onSignedOut: () => void
}

let bridge: TokenBridge = {
  accessToken: () => null,
  refreshToken: () => null,
  onRefreshed: () => {},
  onSignedOut: () => {},
}

/** The auth store calls this once, when the application starts. */
export function connectTokens(next: TokenBridge): void {
  bridge = next
}

interface RequestOptions {
  method?: string
  body?: unknown
  query?: Record<string, unknown> | undefined
  /** Set for FormData. The browser then writes the boundary itself. */
  formData?: FormData
  signal?: AbortSignal
  /** Set false for the sign in routes, which need no token. */
  auth?: boolean
}

export function buildUrl(path: string, query?: Record<string, unknown>): string {
  const url = `${API_BASE}${path}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) {
      for (const entry of value) params.append(key, String(entry))
    } else {
      params.append(key, String(value))
    }
  }
  const text = params.toString()
  return text ? `${url}?${text}` : url
}

/** Return the address of an uploaded file. */
export function mediaUrl(path: string | null | undefined): string | undefined {
  if (!path) return undefined
  if (path.startsWith('http')) return path
  return `${API_BASE}/media/${path.replace(/^\/+/, '')}`
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {}
  if (options.auth !== false) {
    const token = bridge.accessToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }
  let body: BodyInit | undefined
  if (options.formData) {
    body = options.formData
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  return fetch(buildUrl(path, options.query), {
    method: options.method ?? 'GET',
    headers,
    body,
    signal: options.signal,
  })
}

/** Trade the refresh token for a new pair. Returns false if that fails. */
async function renew(): Promise<boolean> {
  const token = bridge.refreshToken()
  if (!token) return false
  try {
    const response = await fetch(buildUrl('/api/auth/refresh'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: token }),
    })
    if (!response.ok) return false
    const envelope = (await response.json()) as Envelope<{
      access_token: string
      refresh_token: string
    }>
    if (!envelope.data) return false
    bridge.onRefreshed(envelope.data.access_token, envelope.data.refresh_token)
    return true
  } catch {
    return false
  }
}

async function unwrap<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T

  let envelope: Envelope<T> | null = null
  try {
    envelope = (await response.json()) as Envelope<T>
  } catch {
    envelope = null
  }

  if (!response.ok) {
    const error = envelope?.error
    throw new ApiError(
      error?.message ?? `The server answered with status ${response.status}.`,
      error?.code ?? `http_${response.status}`,
      response.status,
      error?.details ?? null,
    )
  }
  if (!envelope) {
    throw new ApiError('The server sent no body.', 'empty_response', response.status)
  }
  return envelope.data as T
}

/** Send one request and return the unwrapped data. */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options)

  if (response.status === 401 && options.auth !== false && bridge.refreshToken()) {
    if (await renew()) {
      response = await send(path, options)
    } else {
      bridge.onSignedOut()
    }
  }
  return unwrap<T>(response)
}

/** Download a file route, such as the CSV export. */
export async function download(
  path: string,
  fallbackName: string,
  query?: Record<string, unknown>,
): Promise<void> {
  const token = bridge.accessToken()
  const response = await fetch(buildUrl(path, query), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) {
    await unwrap(response)
    return
  }

  const disposition = response.headers.get('Content-Disposition') ?? ''
  const match = /filename="?([^"]+)"?/.exec(disposition)
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = match?.[1] ?? fallbackName
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export const api = {
  get: <T>(path: string, query?: Record<string, unknown>) =>
    request<T>(path, { query }),
  post: <T>(path: string, body?: unknown, query?: Record<string, unknown>) =>
    request<T>(path, { method: 'POST', body, query }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData, method = 'POST') =>
    request<T>(path, { method, formData }),
}
