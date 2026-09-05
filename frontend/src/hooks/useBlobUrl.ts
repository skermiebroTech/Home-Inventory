/**
 * Load a protected image.
 *
 * An `<img src>` cannot carry the Authorization header, and the QR routes
 * need a token. This hook fetches the bytes with the token and hands back an
 * object URL that the tag can use.
 */

import { useEffect, useState } from 'react'

import { API_BASE } from '@/api/client'
import { useAuthStore } from '@/store/auth'

export function useBlobUrl(path: string | null): { url: string | null; error: boolean } {
  const token = useAuthStore((state) => state.accessToken)
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!path) {
      setUrl(null)
      return
    }
    let objectUrl: string | null = null
    let cancelled = false

    void (async () => {
      setError(false)
      try {
        const response = await fetch(`${API_BASE}${path}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        })
        if (!response.ok) throw new Error(String(response.status))
        const blob = await response.blob()
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      } catch {
        if (!cancelled) setError(true)
      }
    })()

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [path, token])

  return { url, error }
}
