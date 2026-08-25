/**
 * CO: Hook do pobierania i zarządzania portalami WP użytkownika.
 * PO CO: InjectModal potrzebuje listy portali do dropdown.
 *        Osobny hook zamiast inline fetch — reusable, czytelny.
 * JAK: Fetch GET /v1/portals przy mount. Pobiera credentials osobno
 *      przez GET /v1/portals/{id}/credentials gdy user wybierze portal.
 */
import { useState, useEffect, useCallback } from 'react'
import { apiGet, apiPost, apiDelete } from '../lib/api-client'

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
  profile_id?: string | null
}

export function usePortals() {
  const [portals, setPortals] = useState<Portal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchPortals = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiGet<{ portals: Portal[] }>('/v1/portals')
      setPortals(data.portals ?? [])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd pobierania portali')
      setPortals([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchPortals() }, [fetchPortals])

  /** Fetch full credentials (incl. password) for a specific portal. */
  const getCredentials = useCallback(async (portalId: string): Promise<PortalWithPassword | null> => {
    try {
      return await apiGet<PortalWithPassword>(`/v1/portals/${portalId}/full`)
    } catch {
      return null
    }
  }, [])

  /** Create a new portal and refresh the list. */
  const createPortal = useCallback(async (payload: PortalCreatePayload): Promise<Portal | null> => {
    try {
      const created = await apiPost<Portal>('/v1/portals', payload)
      await fetchPortals()
      return created
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd tworzenia portalu')
      return null
    }
  }, [fetchPortals])

  /** Delete a portal and refresh the list. */
  const deletePortal = useCallback(async (portalId: string): Promise<boolean> => {
    try {
      const ok = await apiDelete(`/v1/portals/${portalId}`)
      if (ok) await fetchPortals()
      return ok
    } catch {
      return false
    }
  }, [fetchPortals])

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
