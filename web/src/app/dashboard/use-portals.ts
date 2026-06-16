/**
 * CO: Hook do pobierania i zarządzania portalami WP użytkownika.
 * PO CO: InjectModal potrzebuje listy portali do dropdown.
 *        Osobny hook zamiast inline fetch — reusable, czytelny.
 * JAK: Fetch GET /v1/portals przy mount. Pobiera credentials osobno
 *      przez GET /v1/portals/{id}/credentials gdy user wybierze portal.
 */
import { useState, useEffect, useCallback } from 'react'
import { useSession } from 'next-auth/react'

export interface Portal {
  id: string
  name: string
  url: string
  wp_username: string
  is_default: boolean
  created_at?: string
}

export interface PortalWithPassword extends Portal {
  wp_app_password: string
}

export interface PortalCreatePayload {
  name: string
  url: string
  wp_username: string
  wp_app_password: string
  is_default?: boolean
}

export function usePortals() {
  const { data: session } = useSession()
  const [portals, setPortals] = useState<Portal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
  const token = session?.accessToken as string | undefined

  const fetchPortals = useCallback(async () => {
    if (!token) { setLoading(false); return }
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${apiUrl}/v1/portals`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setPortals(data.portals ?? [])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd pobierania portali')
      setPortals([])
    } finally {
      setLoading(false)
    }
  }, [apiUrl, token])

  useEffect(() => { fetchPortals() }, [fetchPortals])

  /** Fetch full credentials (incl. password) for a specific portal. */
  const getCredentials = useCallback(async (portalId: string): Promise<PortalWithPassword | null> => {
    if (!token) return null
    try {
      const res = await fetch(`${apiUrl}/v1/portals/${portalId}/credentials`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) return null
      return await res.json()
    } catch {
      return null
    }
  }, [apiUrl, token])

  /** Create a new portal and refresh the list. */
  const createPortal = useCallback(async (payload: PortalCreatePayload): Promise<Portal | null> => {
    if (!token) return null
    try {
      const res = await fetch(`${apiUrl}/v1/portals`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const created = await res.json()
      await fetchPortals() // refresh list
      return created
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd tworzenia portalu')
      return null
    }
  }, [apiUrl, token, fetchPortals])

  /** Delete a portal and refresh the list. */
  const deletePortal = useCallback(async (portalId: string): Promise<boolean> => {
    if (!token) return false
    try {
      const res = await fetch(`${apiUrl}/v1/portals/${portalId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok && res.status !== 204) return false
      await fetchPortals() // refresh list
      return true
    } catch {
      return false
    }
  }, [apiUrl, token, fetchPortals])

  return {
    portals,
    loading,
    error,
    fetchPortals,
    getCredentials,
    createPortal,
    deletePortal,
  }
}
