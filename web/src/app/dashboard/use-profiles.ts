/**
 * CO: Hook do pobierania listy profili serwera (profiles/*.yaml).
 * PO CO: Dashboard potrzebuje listy profili do dropdown selektora portalu.
 *        Użytkownik wybiera profil PRZED generowaniem artykułu, co determinuje
 *        konfigurację SEO, site_brand i domyślny typ publikacji.
 * JAK: Fetch GET /v1/profiles przy mount. Zwraca profiles, loading, error.
 *
 * D9 (2026-06-20, vse-dev-23): New hook for dashboard portal selector.
 */
import { useState, useEffect, useCallback } from 'react'

export interface Profile {
  id: string
  display_name: string
  active: boolean
  publication_types: string[]
  default_type: string
  site_brand?: string | null
}

export function useProfiles() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''

  const fetchProfiles = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${apiUrl}/v1/profiles`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setProfiles(data.profiles ?? [])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'B\u0142\u0105d pobierania profili')
      setProfiles([])
    } finally {
      setLoading(false)
    }
  }, [apiUrl])

  useEffect(() => { fetchProfiles() }, [fetchProfiles])

  return {
    profiles,
    loading,
    error,
    fetchProfiles,
  }
}
