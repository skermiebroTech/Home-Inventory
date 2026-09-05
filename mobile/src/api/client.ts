/**
 * The HTTP client.
 *
 * The server address is not fixed: every household runs its own server, so
 * the sign in screen asks for it and the store keeps it. Every reply carries
 * the `{ data, error }` envelope, which this module unwraps.
 */

import type { Envelope } from './types'

export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(message: string, code: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

/** A request that never reached the server. Offline code checks for it. */
export class OfflineError extends Error {
  constructor(message = 'The server is not reachable.') {
    super(message)
    this.name = 'OfflineError'
  }
}

interface Bridge {
  baseUrl: () => string
  accessToken: () => string | null
  refreshToken: () => string | null
  onRefreshed: (access: string, refresh: string) => void
  onSignedOut: () => void
}

let bridge: Bridge = {
  baseUrl: () => '',
  accessToken: () => null,
  refreshToken: () => null,
  onRefreshed: () => {},
  onSignedOut: () => {},
}

export function connectTokens(next: Bridge): void {
  bridge = next
}

export function serverUrl(): string {
  return bridge.baseUrl().replace(/\/$/, '')
}

/** Build the address of an uploaded file on the server. */
export function mediaUrl(path: string | null | undefined): string | undefined {
  if (!path) return undefined
  if (path.startsWith('http')) return path
  return `${serverUrl()}/media/${path.replace(/^\/+/, '')}`
}

interface Options {
  method?: string
  body?: unknown
  query?: Record<string, unknown>
  formData?: FormData
  auth?: boolean
  baseUrl?: string
  timeoutMs?: number
}

export function buildUrl(path: string, query?: Record<string, unknown>, base?: string): string {
  const url = `${(base ?? serverUrl()).replace(/\/$/, '')}${path}`
  if (!query) return url
  const parts: string[] = []
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) {
      for (const entry of value) parts.push(`${key}=${encodeURIComponent(String(entry))}`)
    } else {
      parts.push(`${key}=${encodeURIComponent(String(value))}`)
    }
  }
  return parts.length > 0 ? `${url}?${parts.join('&')}` : url
}

async function send(path: string, options: Options): Promise<Response> {
  const headers: Record<string, string> = {}
  if (options.auth !== false) {
    const token = bridge.accessToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }
  let body: BodyInit | undefined
  if (options.formData) {
    body = options.formData as unknown as BodyInit
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? 30000)
  try {
    return await fetch(buildUrl(path, options.query, options.baseUrl), {
      method: options.method ?? 'GET',
      headers,
      body,
      signal: controller.signal,
    })
  } catch (error) {
    throw new OfflineError(
      error instanceof Error && error.name === 'AbortError'
        ? 'The server did not answer in time.'
        : 'The server is not reachable.',
    )
  } finally {
    clearTimeout(timer)
  }
}

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
  let envelope: Envelope<T> | null = null
  try {
    envelope = (await response.json()) as Envelope<T>
  } catch {
    envelope = null
  }
  if (!response.ok) {
    throw new ApiError(
      envelope?.error?.message ?? `The server answered with status ${response.status}.`,
      envelope?.error?.code ?? `http_${response.status}`,
      response.status,
    )
  }
  return (envelope?.data as T) ?? (undefined as T)
}

export async function request<T>(path: string, options: Options = {}): Promise<T> {
  let response = await send(path, options)
  if (response.status === 401 && options.auth !== false && bridge.refreshToken()) {
    if (await renew()) response = await send(path, options)
    else bridge.onSignedOut()
  }
  return unwrap<T>(response)
}

export const api = {
  get: <T>(path: string, query?: Record<string, unknown>) => request<T>(path, { query }),
  post: <T>(path: string, body?: unknown, query?: Record<string, unknown>) =>
    request<T>(path, { method: 'POST', body, query }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: 'POST', formData, timeoutMs: 120000 }),
}
