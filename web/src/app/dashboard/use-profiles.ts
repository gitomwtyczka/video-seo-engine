/**
 * CO: Hook do pobierania i tworzenia profili serwera (profiles/*.yaml).
 * PO CO: Dashboard potrzebuje listy profili do dropdown selektora portalu.
 *        Użytkownik wybiera profil PRZED generowaniem artykułu, co determinuje
 *        konfigurację SEO, site_brand i domyślny typ publikacji.
 *        Inline profile creation pozwala tworzyć profil z poziomu AddPortalModal.
 * JAK: Fetch GET /v1/profiles przy mount. POST /v1/profiles do tworzenia.
 *      Zwraca profiles, loading, error, fetchProfiles, createProfile.
 *
 * D9  (2026-06-20, vse-dev-23): New hook for dashboard portal selector.
 * D35 (2026-06-30, vse-dev-01): createProfile mutation for inline creation.
 */
import { useState, useEffect, useCallback } from 'react'
import { apiGet, apiPost } from '../lib/api-client'

export interface Profile {
  id: string
  display_name: string
  active: boolean
  publication_types: string[]
  default_type: string
  site_brand?: string | null
}

export interface CreateProfilePayload {
  portal_id: string
  display_name: string
  site_brand: string
  wp_base_url: string
  default_type: string
  seo_language?: string
  seo_external_link_url?: string
  seo_external_link_anchor?: string
}

export function useProfiles() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchProfiles = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiGet<{ profiles: Profile[] }>('/v1/profiles')
      setProfiles(data.profiles ?? [])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd pobierania profili')
      setProfiles([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchProfiles() }, [fetchProfiles])

  /** Create a new server-side YAML profile and refresh the list. */
  const createProfile = useCallback(async (payload: CreateProfilePayload): Promise<Profile | null> => {
    try {
      const created = await apiPost<Profile>('/v1/profiles', payload)
      await fetchProfiles() // refresh list
      return created
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd tworzenia profilu')
      return null
    }
  }, [fetchProfiles])

  return {
    profiles,
    loading,
    error,
    fetchProfiles,
    createProfile,
  }
}
