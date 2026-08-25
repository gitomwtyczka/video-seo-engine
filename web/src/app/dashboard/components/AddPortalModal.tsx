'use client'

import { useState, useEffect, useRef } from 'react'
import { usePortals } from '../use-portals'
import { useProfiles, type Profile } from '../use-profiles'

export function AddPortalModal({
  onClose,
  onSuccess
}: {
  onClose: () => void
  onSuccess: (portalId: string) => void
}) {
  const { createPortal } = usePortals()
  const { profiles, loading: profilesLoading, createProfile } = useProfiles()

  const [name, setName] = useState('')
  const [url, setUrl] = useState('https://')
  const [wpUser, setWpUser] = useState('')
  const [wpPassword, setWpPassword] = useState('')
  const [profileId, setProfileId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [showNewProfileForm, setShowNewProfileForm] = useState(false)
  const [newProfileBrand, setNewProfileBrand] = useState('')
  const [newProfileType, setNewProfileType] = useState('analiza')
  const [newProfileLang, setNewProfileLang] = useState('pl')
  const [newProfileExtUrl, setNewProfileExtUrl] = useState('')
  const [newProfileExtAnchor, setNewProfileExtAnchor] = useState('')

  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (profiles.length > 0 && !profileId) {
      setProfileId(profiles[0].id)
    }
  }, [profiles, profileId])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
      onClose()
    }
  }

  const slugify = (text: string): string =>
    text.toLowerCase()
      .replace(/[ąàáâãäå]/g, 'a').replace(/[ćčç]/g, 'c')
      .replace(/[ęèéêë]/g, 'e').replace(/[ìíîï]/g, 'i')
      .replace(/[łľ]/g, 'l').replace(/[ńñň]/g, 'n')
      .replace(/[óòôõöő]/g, 'o').replace(/[śšş]/g, 's')
      .replace(/[ùúûüű]/g, 'u').replace(/[ýÿ]/g, 'y')
      .replace(/[źżž]/g, 'z').replace(/[đð]/g, 'd')
      .replace(/[^\w-]/g, '-').replace(/-+/g, '-')
      .replace(/^-|-$/g, '')

  const handleProfileDropdownChange = (value: string) => {
    if (value === '__new__') {
      setShowNewProfileForm(true)
      setProfileId('__new__')
    } else {
      setShowNewProfileForm(false)
      setProfileId(value)
    }
  }

  const handleSave = async () => {
    if (!name || !url || !wpUser || !wpPassword) {
      setError('Uzupełnij wszystkie pola.')
      return
    }

    if (showNewProfileForm) {
      if (!newProfileBrand.trim()) {
        setError('Podaj nazwę brandu dla nowego profilu.')
        return
      }
    }

    setSaving(true)
    setError('')

    try {
      let finalProfileId: string | null = null

      if (showNewProfileForm) {
        const portalSlug = slugify(name)
        if (!portalSlug || portalSlug.length < 3) {
          setError('Nazwa portalu jest za krótka (min. 3 znaki).')
          setSaving(false)
          return
        }

        const newProfile = await createProfile({
          portal_id: portalSlug,
          display_name: name.trim(),
          site_brand: newProfileBrand.trim(),
          wp_base_url: url.trim(),
          default_type: newProfileType,
          seo_language: newProfileLang,
          seo_external_link_url: newProfileExtUrl.trim() || undefined,
          seo_external_link_anchor: newProfileExtAnchor.trim() || undefined,
        })

        if (!newProfile) {
          setError('Nie udało się utworzyć profilu. Sprawdź dane.')
          setSaving(false)
          return
        }

        finalProfileId = newProfile.id
      } else {
        finalProfileId = profileId === 'none' ? null : profileId
      }

      const created = await createPortal({
        name,
        url,
        wp_username: wpUser,
        wp_app_password: wpPassword,
        profile_id: finalProfileId,
      })

      if (created) {
        onSuccess(created.id)
      } else {
        setError('Nie udało się utworzyć portalu.')
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd podczas zapisu')
    } finally {
      setSaving(false)
    }
  }

  const selectClass = "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-violet-500 focus:outline-none cursor-pointer appearance-none"
  const selectStyle = { backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3E%3Cpath stroke=\'%236b7280\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.5rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }
  const inputClass = "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-violet-500 focus:outline-none"

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={handleBackdropClick}
    >
      <div
        ref={modalRef}
        className="w-full max-w-md bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden animate-in"
        style={{ animation: 'fadeInUp 0.25s ease-out', maxHeight: '90vh', overflowY: 'auto' }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gradient-to-r from-violet-950/50 to-fuchsia-950/30">
          <h3 className="font-semibold text-white">Dodaj nowy portal</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-1">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Nazwa portalu</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="np. BiznesCiti.com"
              className={inputClass}
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1.5">URL WordPress</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://biznesciti.com"
              className={inputClass}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Użytkownik WP</label>
              <input
                type="text"
                value={wpUser}
                onChange={(e) => setWpUser(e.target.value)}
                placeholder="admin"
                className={inputClass}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">App Password</label>
              <input
                type="password"
                value={wpPassword}
                onChange={(e) => setWpPassword(e.target.value)}
                placeholder="xxxx xxxx xxxx xxxx"
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Profil treści</label>
            {profilesLoading ? (
              <div className="text-gray-500 text-xs py-2">Ładowanie profili...</div>
            ) : (
              <select
                value={profileId}
                onChange={(e) => handleProfileDropdownChange(e.target.value)}
                className={selectClass}
                style={selectStyle}
              >
                {profiles.map((p: Profile) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name}{p.site_brand ? ` (${p.site_brand})` : ''}
                  </option>
                ))}
                <option value="none">(brak profilu)</option>
                <option value="__new__">+ Utwórz nowy profil</option>
              </select>
            )}
          </div>

          {showNewProfileForm && (
            <div className="space-y-3 pl-3 border-l-2 border-violet-500/30">
              <p className="text-xs text-violet-400 font-medium">Nowy profil treści</p>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Site brand</label>
                <input
                  type="text"
                  value={newProfileBrand}
                  onChange={(e) => setNewProfileBrand(e.target.value)}
                  placeholder="np. BiznesCiti"
                  className={inputClass}
                />
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1">Domyślny typ publikacji</label>
                <select
                  value={newProfileType}
                  onChange={(e) => setNewProfileType(e.target.value)}
                  className={selectClass}
                  style={selectStyle}
                >
                  <optgroup label="-- Informacyjne --">
                    <option value="news">News (depesza)</option>
                  </optgroup>
                  <optgroup label="-- Publicystyczne --">
                    <option value="analiza">Analiza pogłębiona</option>
                    <option value="felieton">Felieton</option>
                  </optgroup>
                  <optgroup label="-- Narracyjne --">
                    <option value="wywiad">Wywiad Q&A</option>
                    <option value="reportaz">Reportaż</option>
                  </optgroup>
                  <optgroup label="-- Użytkowe --">
                    <option value="explainer">Explainer (wyjaśniamy)</option>
                    <option value="poradnik">Poradnik / How-To</option>
                  </optgroup>
                  <optgroup label="-- Legacy (zachowane) --">
                    <option value="full_analysis">Pełna analiza (stary)</option>
                    <option value="watching_page">Strona oglądania</option>
                    <option value="discover">Google Discover</option>
                  </optgroup>
                </select>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1">Język SEO</label>
                <select
                  value={newProfileLang}
                  onChange={(e) => setNewProfileLang(e.target.value)}
                  className={selectClass}
                  style={selectStyle}
                >
                  <option value="pl">Polski</option>
                  <option value="en">English</option>
                  <option value="de">Deutsch</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Link zewn. SEO</label>
                  <input
                    type="url"
                    value={newProfileExtUrl}
                    onChange={(e) => setNewProfileExtUrl(e.target.value)}
                    placeholder="https://youtube.com"
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Anchor linku</label>
                  <input
                    type="text"
                    value={newProfileExtAnchor}
                    onChange={(e) => setNewProfileExtAnchor(e.target.value)}
                    placeholder="Źródło wideo"
                    className={inputClass}
                  />
                </div>
              </div>
            </div>
          )}

          {error && <p className="text-red-400 text-xs mt-2">{error}</p>}

          <div className="flex gap-3 pt-2">
            <button
              onClick={onClose}
              disabled={saving}
              className="flex-1 py-2 bg-gray-800 text-white rounded-lg font-medium hover:bg-gray-700 transition-colors"
            >
              Anuluj
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex-1 py-2 bg-violet-600 text-white rounded-lg font-medium hover:bg-violet-500 transition-colors"
            >
              {saving ? 'Zapisywanie...' : showNewProfileForm ? '✨ Utwórz profil i portal' : 'Zapisz portal'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AddPortalModal
