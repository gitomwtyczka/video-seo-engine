'use client'

/**
 * CO: Dashboard — główny widok aplikacji po zalogowaniu
 * PO CO: Daje użytkownikowi dwie ścieżki:
 *   A (Free/Starter) — generuje SEO i pokazuje gotowe snippety HTML do skopiowania
 *   B (Pro/Agency)   — dodatkowo umożliwia automatyczną publikację na WordPress
 * JAK: Wywołuje POST /v1/generate → schema_data → renderuje zakładki wynikowe
 *      (Schemat, Artykuł, Rozdziały, Opis YouTube, ShortMachine). Dla planu pro/agency InjectModal → POST /v1/inject.
 */

import { useSession, signOut } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect, useState, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useJobLoader } from './use-job-loader'
import { usePortals, type Portal } from './use-portals'
import { useProfiles, type Profile } from './use-profiles'
import EmailVerificationBanner from './email-verification-banner'
import { ErrorBoundary } from './error-boundary'
import { YouTubePublishModal } from './YouTubePublishModal'

// ─── Types (wydzielone do ./types) ─────────────────────────────────────────
import type {
  GenerateResponse,
  SchemaData,
  ChapterItem,
  FaqItem,
  QuoteItem,
  UserPlan,
  UserProfile,
  InjectResult,
  CopiedKey,
  TabKey,
} from './types'

// ─── Utils (wydzielone do ./utils) ──────────────────────────────────────────
import {
  extractChapters,
  extractFaq,
  secToTimestamp,
  chaptersToText,
  faqToHtml,
  schemaToScriptTag,
  articleToText,
  loadWpCredentials,
  saveWpCredentials,
  extractVideoId,
  buildYtDescription,
} from './utils'

// ─── Subcomponents ──────────────────────────────────────────────────────────

function CopyButton({
  text,
  id,
  copiedKey,
  onCopy,
  label,
}: {
  text: string
  id: string
  copiedKey: CopiedKey
  onCopy: (text: string, id: string) => void
  label?: string
}) {
  const active = copiedKey === id
  return (
    <button
      onClick={() => onCopy(text, id)}
      className={`px-3 py-1 text-xs rounded-lg border transition-all duration-200 ${
        active
          ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
          : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white hover:border-gray-500'
      }`}
    >
      {active ? '✔️ Skopiowano' : (label ?? 'Kopiuj')}
    </button>
  )
}

function ResultSection({
  title,
  copyText,
  copyId,
  copiedKey,
  onCopy,
  badge,
  children,
}: {
  title: string
  copyText: string
  copyId: string
  copiedKey: CopiedKey
  onCopy: (text: string, id: string) => void
  badge?: string
  children: React.ReactNode
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden mb-4">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-gray-900/50">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-200">{title}</span>
          {badge && (
            <span className="px-2 py-0.5 text-xs bg-violet-500/15 text-violet-400 rounded-full border border-violet-500/20">
              {badge}
            </span>
          )}
        </div>
        <CopyButton text={copyText} id={copyId} copiedKey={copiedKey} onCopy={onCopy} />
      </div>
      <div className="p-4">{children}</div>
    </div>
  )
}

function TabBar({
  active,
  onChange,
  chaptersCount,
  faqCount,
}: {
  active: TabKey
  onChange: (tab: TabKey) => void
  chaptersCount: number
  faqCount: number
}) {
  const tabs: { key: TabKey; label: string; badge?: number }[] = [
    { key: 'schema', label: 'Schemat' },
    { key: 'article', label: 'Artykuł', badge: faqCount > 0 ? faqCount : undefined },
    { key: 'chapters', label: 'Rozdziały', badge: chaptersCount > 0 ? chaptersCount : undefined },
    { key: 'youtube', label: 'Opis YouTube' },
    { key: 'shorts', label: '✂️ ShortMachine' },
  ]

  return (
    <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-xl p-1 mb-5">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
            active === tab.key
              ? 'bg-violet-600/20 text-violet-400 border border-violet-500/30'
              : 'text-gray-400 hover:text-white hover:bg-gray-800/50 border border-transparent'
          }`}
        >
          {tab.label}
          {tab.badge != null && tab.badge > 0 && (
            <span className={`px-1.5 py-0.5 text-xs rounded-full ${
              active === tab.key
                ? 'bg-violet-500/30 text-violet-300'
                : 'bg-gray-700 text-gray-500'
            }`}>
              {tab.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}

function InjectModal({
  schemaData,
  videoUrl,
  selectedPortalId,
  portalName,
  portalUrl,
  accessToken,
  onClose,
  ytChannels,
}: {
  schemaData: SchemaData
  videoUrl: string
  selectedPortalId: string
  portalName?: string
  portalUrl?: string
  accessToken?: string
  onClose: () => void
  ytChannels?: any[]
}) {
  const initialCreds = loadWpCredentials()
  const [wpUrl, setWpUrl] = useState(initialCreds.wpUrl)
  const [wpUser, setWpUser] = useState(initialCreds.wpUser)
  const [wpPassword, setWpPassword] = useState(initialCreds.wpPassword)
  const [wpPostId, setWpPostId] = useState('')
  const [postStatus, setPostStatus] = useState<'draft' | 'publish'>('draft')
  const [postFormat, setPostFormat] = useState('video')
  const [publishing, setPublishing] = useState(false)
  const [publishResult, setPublishResult] = useState<InjectResult | null>(null)
  const [selectedYtChannelIds, setSelectedYtChannelIds] = useState<string[]>([])
  const [ytDescPreview, setYtDescPreview] = useState<string>('')
  const [showYtPreview, setShowYtPreview] = useState<boolean>(false)

  const modalRef = useRef<HTMLDivElement>(null)

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

  const isManual = selectedPortalId === '__manual__' || !selectedPortalId

  useEffect(() => {
    if (selectedYtChannelIds.length === 0) { setYtDescPreview(''); return }
    const parts: string[] = []
    if (schemaData?.youtube_description_body) parts.push(schemaData.youtube_description_body)
    if (schemaData?.youtube_mid_cta) parts.push(schemaData.youtube_mid_cta)
    if (schemaData?.youtube_credits) parts.push(schemaData.youtube_credits)
    if (schemaData?.youtube_hashtags) {
      if (Array.isArray(schemaData.youtube_hashtags)) {
        parts.push(schemaData.youtube_hashtags.join(' '))
      } else {
        parts.push(schemaData.youtube_hashtags)
      }
    }
    const firstCh = ytChannels?.find(ch => selectedYtChannelIds.includes(ch.channel_id))
    if (firstCh?.footer_text) parts.push(firstCh.footer_text)
    setYtDescPreview(parts.join('\n\n') || '(brak wygenerowanego opisu)')
  }, [selectedYtChannelIds, schemaData, ytChannels])

  const handlePublish = async () => {
    const isPublishingToWp = !isManual || (wpUser && wpPassword && wpUrl)
    if (!isPublishingToWp && selectedYtChannelIds.length === 0) {
      setPublishResult({ error: 'Uzupełnij URL portalu, użytkownika i Application Password lub wybierz kanał YouTube.' })
      return
    }

    if (isPublishingToWp && isManual) {
      saveWpCredentials({ wpUrl, wpUser, wpPassword })
    }

    setPublishing(true)
    setPublishResult(null)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const body: Record<string, unknown> = {
        video_url: videoUrl,
        schema_data: schemaData,
        post_status: postStatus,
        post_format: postFormat,
      }

      if (selectedYtChannelIds.length > 0) {
        body.yt_channel_ids = selectedYtChannelIds
        if (showYtPreview && ytDescPreview) {
          body.yt_override_description = ytDescPreview
        }
      }

      if (isPublishingToWp) {
        if (isManual) {
          body.site_config = {
            wp_base_url: wpUrl,
            wp_user: wpUser,
            wp_app_password: wpPassword,
          }
        } else {
          body.portal_id = selectedPortalId.trim()
        }
        if (wpPostId.trim()) {
          body.wp_post_id = parseInt(wpPostId, 10)
        }
      }

      const res = await fetch(`${apiUrl}/v1/inject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken && { Authorization: `Bearer ${accessToken}` }),
        },
        body: JSON.stringify(body),
      })
      let data: any
      try { data = await res.json() } catch { data = { error: `HTTP ${res.status}` } }

      if (!res.ok) {
        let errStr = data?.detail || data?.error || `Błąd serwera (HTTP ${res.status})`
        if (typeof errStr === 'object') {
          errStr = JSON.stringify(errStr, null, 2)
        }
        throw new Error(errStr)
      }
      setPublishResult(data)
      if (data?.yt_results) {
        const errors: string[] = []
        Object.entries(data.yt_results).forEach(([_, status]) => {
          if (status !== 'ok') errors.push(`Błąd YT: ${status}`)
        })
        if (errors.length > 0) {
          setPublishResult(prev => ({
            ...prev,
            error: (prev?.error ? prev.error + '\n' : '') + errors.join('\n')
          }))
        }
      }
    } catch (e: unknown) {
      setPublishResult({ error: e instanceof Error ? e.message : 'Błąd połączenia' })
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={handleBackdropClick}
    >
      <div
        ref={modalRef}
        className="w-full max-w-lg bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden animate-in"
        style={{ animation: 'fadeInUp 0.25s ease-out' }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gradient-to-r from-violet-950/50 to-fuchsia-950/30">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center text-sm">
              🚀
            </div>
            <div>
              <h3 className="font-semibold text-white">Publikuj na WordPress</h3>
              <p className="text-xs text-gray-400">Wyślij artykuł + SEO schema na portal</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-1">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4">
            <p className="text-xs text-gray-500 mb-1">Artykuł do publikacji:</p>
            <p className="text-sm font-medium text-white truncate">
              {schemaData.post_title ?? '(brak tytułu)'}
            </p>
            {schemaData.meta_description && (
              <p className="text-xs text-gray-400 mt-1 line-clamp-2">
                {schemaData.meta_description}
              </p>
            )}
          </div>

          {!isManual && portalName && (
            <div className="flex items-center gap-2 px-3 py-2 bg-violet-500/5 border border-violet-500/15 rounded-lg mb-4">
              <span className="text-xs text-violet-400">🚀</span>
              <span className="text-sm text-gray-200">Publikujesz na: <span className="font-semibold">{portalName}</span></span>
              <span className="text-xs text-gray-500 ml-auto">{portalUrl}</span>
            </div>
          )}

          {isManual && (
            <>
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">URL portalu WordPress</label>
                <input
                  type="text"
                  value={wpUrl}
                  onChange={(e) => setWpUrl(e.target.value)}
                  placeholder="https://twojportal.pl"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
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
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1.5">Application Password</label>
                  <input
                    type="password"
                    value={wpPassword}
                    onChange={(e) => setWpPassword(e.target.value)}
                    placeholder="xxxx xxxx xxxx xxxx"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
                  />
                </div>
              </div>
            </>
          )}

          <div className="mb-4">
            <label className="block text-xs text-gray-400 mb-1.5">Dodatkowo: Opublikuj opis na YouTube</label>
            {ytChannels && ytChannels.length > 0 ? (
              <div className="space-y-2 max-h-32 overflow-y-auto bg-gray-800/50 p-2 rounded-lg border border-gray-700">
                {ytChannels.map(ch => (
                  <label key={ch.channel_id} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedYtChannelIds.includes(ch.channel_id)}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedYtChannelIds(p => [...p, ch.channel_id])
                        else setSelectedYtChannelIds(p => p.filter(id => id !== ch.channel_id))
                      }}
                      className="accent-violet-500 rounded"
                    />
                    <span className="text-sm text-gray-300">{ch.channel_title}</span>
                  </label>
                ))}
              </div>
            ) : (
              <div className="p-3 bg-gray-800/50 rounded-lg border border-gray-700">
                <p className="text-xs text-amber-500/90 flex items-center gap-1.5">
                  ⚠️ Brak podłączonych kanałów YouTube.
                  <a href="/ustawienia" target="_blank" rel="noreferrer" className="underline hover:text-amber-400 transition-colors ml-1">
                    Przejdź do ustawień
                  </a>
                </p>
              </div>
            )}

            {selectedYtChannelIds.length > 0 && ytChannels && ytChannels.length > 0 && (
              <div className="mt-3">
                {!showYtPreview ? (
                  <button
                    onClick={() => setShowYtPreview(true)}
                    className="text-xs text-violet-400 hover:text-violet-300 underline"
                  >
                    Pokaż edytowalny podgląd opisu YT
                  </button>
                ) : (
                  <div className="mt-2 animate-in slide-in-from-top-2">
                    <label className="block text-xs text-gray-400 mb-1">
                      Podgląd opisu YouTube <span className="text-gray-600">(edytowalny)</span>
                    </label>
                    <textarea
                      value={ytDescPreview}
                      onChange={(e) => setYtDescPreview(e.target.value)}
                      rows={6}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-violet-500 resize-y font-mono"
                    />
                    <button
                      onClick={() => setShowYtPreview(false)}
                      className="mt-1 text-xs text-gray-500 hover:text-gray-400"
                    >
                      Ukryj podgląd
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">
                ID posta WP <span className="text-gray-600">(puste = nowy post)</span>
              </label>
              <input
                type="number"
                value={wpPostId}
                onChange={(e) => setWpPostId(e.target.value)}
                placeholder="Puste = nowy artykuł"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Status publikacji</label>
              <div className="flex gap-4 h-[42px] items-center">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="modal_post_status"
                    value="draft"
                    checked={postStatus === 'draft'}
                    onChange={() => setPostStatus('draft')}
                    className="accent-violet-500"
                  />
                  <span className="text-sm text-gray-300">Szkic</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="modal_post_status"
                    value="publish"
                    checked={postStatus === 'publish'}
                    onChange={() => setPostStatus('publish')}
                    className="accent-violet-500"
                  />
                  <span className="text-sm text-gray-300">Publikuj</span>
                </label>
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Format wpisu WordPress</label>
            <select
              value={postFormat}
              onChange={(e) => setPostFormat(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer"
              style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3E%3Cpath stroke=\'%236b7280\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.5rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }}
            >
              <option value="video">🎬 Film (video)</option>
              <option value="standard">📄 Standard</option>
              <option value="gallery">🖼️ Galeria (gallery)</option>
              <option value="quote">💬 Cytat (quote)</option>
            </select>
            <p className="text-xs text-gray-600 mt-1">Domyślnie: Film — optymalny dla treści video SEO</p>
          </div>

          <button
            onClick={handlePublish}
            disabled={publishing || (!isManual && !selectedPortalId && selectedYtChannelIds.length === 0) || (isManual && !wpUrl && selectedYtChannelIds.length === 0)}
            className="w-full py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-xl font-semibold text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
          >
            {publishing ? (
              <><span className="animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> Publikowanie...</>
            ) : (
              <>🚀 Opublikuj na portalu</>
            )}
          </button>

          {publishResult && (
            <div
              className={`p-4 rounded-xl text-sm ${
                publishResult.error
                  ? 'bg-red-500/10 border border-red-500/20 text-red-400'
                  : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
              }`}
            >
              {publishResult.error ? (
                <><span className="font-medium">⚠️ Błąd:</span> {publishResult.error}</>
              ) : (
                <div className="space-y-1">
                  <p><span className="font-medium">✔️ Sukces!</span>
                    {publishResult.created ? ' Utworzono nowy artykuł' : ' Zaktualizowano artykuł'}
                    {publishResult.wp_post_id && ` (ID: ${publishResult.wp_post_id})`}
                  </p>
                  {publishResult.post_url && (
                    <a
                      href={publishResult.post_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-emerald-300 hover:text-emerald-200 underline underline-offset-2"
                    >
                      Otwórz artykuł na portalu →
                    </a>
                  )}
                </div>
              )}
            </div>
          )}

          <p className="text-xs text-gray-600 text-center">
            {isManual ? 'Dane logowania zapamiętane w przeglądarce (localStorage)' : 'Credentials pobrane z zapisanego portalu'}
          </p>
        </div>
      </div>
    </div>
  )
}

function AddPortalModal({
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

function ManageSubscriptionLink({ accessToken }: { accessToken?: string }) {
  const [loading, setLoading] = useState(false)
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''

  const handleManage = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${apiUrl}/v1/payments/portal-session`, {
        headers: { Authorization: `Bearer ${accessToken || ''}` },
      })
      if (res.ok) {
        const { portal_url } = await res.json()
        window.location.href = portal_url
      }
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleManage}
      disabled={loading}
      className="text-xs text-gray-400 hover:text-violet-300 transition-colors py-0.5 text-left disabled:opacity-50"
    >
      {loading ? '...' : '⚙ Zarządzaj subskrypcją'}
    </button>
  )
}

function NavItem({
  icon,
  label,
  href,
  active,
}: {
  icon?: string
  label?: string
  href: string
  active?: boolean
}) {
  const iconPath: Record<string, string> = {
    grid: 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z',
    clock: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
    settings: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z',
  }

  return (
    <Link
      href={href}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-violet-600/10 text-violet-400'
          : 'text-gray-400 hover:text-white hover:bg-gray-800'
      }`}
    >
      {icon && iconPath[icon] && (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={iconPath[icon]} />
        </svg>
      )}
      {label}
    </Link>
  )
}

function WpQuickPanel() {
  return (
    <ErrorBoundary>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center text-base">🚀</div>
          <div>
            <p className="text-sm font-medium text-white">Integracja WordPress</p>
            <p className="text-xs text-gray-500">Skonfiguruj portal do automatycznej publikacji</p>
          </div>
          <Link
            href="/ustawienia"
            className="ml-auto text-xs text-violet-400 hover:text-violet-300 transition-colors"
          >
            Konfiguruj →
          </Link>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[
            { icon: '📋', label: 'Kopiuj HTML', desc: 'Schemat gotowy do wklejenia' },
            { icon: '🚀', label: 'Auto-publish', desc: 'Plan Pro/Agency' },
            { icon: '📊', label: 'SEO Schema', desc: 'VideoObject + Clip + FAQ' },
          ].map((item) => (
            <div key={item.label} className="bg-gray-800/50 rounded-lg p-3 text-center">
              <div className="text-xl mb-1">{item.icon}</div>
              <p className="text-xs font-medium text-white">{item.label}</p>
              <p className="text-xs text-gray-500 mt-0.5">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </ErrorBoundary>
  )
}

// ─── Main Component ─────────────────────────────────────────────────────────

export default function DashboardInner() {
  const { data: session, status } = useSession()
  const router = useRouter()

  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ raw: SchemaData; videoId: string; time?: number; inputUrl: string } | null>(null)
  const [error, setError] = useState('')
  const [copiedKey, setCopiedKey] = useState<CopiedKey>(null)
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('article')

  // ShortMachine state
  const [smYoutubeId, setSmYoutubeId] = useState('')
  const [smCustomQuery, setSmCustomQuery] = useState('')
  const [smCountEmotional, setSmCountEmotional] = useState(2)
  const [smCountProfessional, setSmCountProfessional] = useState(2)
  const [smCountCustom, setSmCountCustom] = useState(3)
  const [shortLocalPath, setShortLocalPath] = useState<string>('')
  const [smCandidates, setSmCandidates] = useState<any[]>([])
  const [smPreviewIdx, setSmPreviewIdx] = useState<number | null>(null)
  const ytPlayerRef = useRef<any>(null)
  const ytIntervalRef = useRef<any>(null)
  const [smTitles, setSmTitles] = useState<Record<number, string>>({})
  const [smTags, setSmTags] = useState<Record<number, string[]>>({})
  const [smTitleLoading, setSmTitleLoading] = useState<Record<number, boolean>>({})

  // Auto-populate smYoutubeId from current video URL
  useEffect(() => {
    if (!smYoutubeId) {
      const urlParams = new URLSearchParams(window.location.search)
      const jobVideoUrl = url || urlParams.get('video_url') || ''
      if (jobVideoUrl) {
        const match = jobVideoUrl.match(/(?:v=|youtu\.be\/|shorts\/)([a-zA-Z0-9_-]{11})/)
        if (match) setSmYoutubeId(match[1])
        else if (jobVideoUrl.length === 11) setSmYoutubeId(jobVideoUrl)
      }
    }
  }, [url, smYoutubeId])

  const extractYoutubeId = (urlOrId: string): string => {
    if (/^[A-Za-z0-9_-]{11}$/.test(urlOrId)) return urlOrId
    const match = urlOrId.match(/(?:v=|youtu\.be\/|\/shorts\/)([A-Za-z0-9_-]{11})/)
    return match ? match[1] : urlOrId
  }

  useEffect(() => {
    if (!smYoutubeId) return
    const cleanId = extractYoutubeId(smYoutubeId)
    const apiBase = process.env.NEXT_PUBLIC_API_URL || ''
    fetch(`${apiBase}/v1/shorts/history/${cleanId}`)
      .then(r => r.json())
      .then(data => {
        if (data.candidates?.length > 0 && smCandidates.length === 0) {
          setSmCandidates(data.candidates)
        }
        if (data.jobs?.length > 0 && data.candidates?.length > 0) {
          const restoredStatus: Record<number, any> = {}
          data.jobs.forEach((job: any) => {
            const idx = data.candidates.findIndex(
              (c: any) => Math.abs(c.start_sec - job.start_sec) < 1 &&
                          Math.abs(c.end_sec - job.end_sec) < 1
            )
            if (idx >= 0) {
              restoredStatus[idx] = {
                status: job.status,
                result_paths: job.result_paths,
                job_id: job.id,
                error: job.error,
              }
            }
          })
          if (Object.keys(restoredStatus).length > 0) {
            setSmJobStatus(prev => ({ ...restoredStatus, ...prev }))
          }
        }
      })
      .catch(err => console.warn('Failed to restore ShortMachine state:', err))
  }, [smYoutubeId])

  const [smLoading, setSmLoading] = useState(false)
  const [smError, setSmError] = useState<string | null>(null)
  const [smRenderConfig, setSmRenderConfig] = useState<Record<number, {format: string, subtitles: string}>>({})
  const [smJobStatus, setSmJobStatus] = useState<Record<number, any>>({})
  const [smTrimAdj, setSmTrimAdj] = useState<Record<number, {startDelta: number; endDelta: number}>>({})
  const [smExpandedIdx, setSmExpandedIdx] = useState<number | null>(null)
  const [smTrimMode, setSmTrimMode] = useState<'start' | 'end'>('start')
  const [smSelected, setSmSelected] = useState<Set<number>>(new Set())
  const [smFormat, setSmFormat] = useState<'raw' | 'short'>('raw')

  const toggleSmSelected = (idx: number) => setSmSelected(prev => {
    const next = new Set(prev)
    if (next.has(idx)) next.delete(idx); else next.add(idx)
    return next
  })

  const [smTargetYtId, setSmTargetYtId] = useState<Record<number, string>>({})
  const [smGlobalChannelId, setSmGlobalChannelId] = useState<string>('')
  const [smChannelOverride, setSmChannelOverride] = useState<Record<number, string>>({})
  const [smPublishAt, setSmPublishAt] = useState<Record<number, string>>({})
  const [smPrivacyStatus, setSmPrivacyStatus] = useState<Record<number, string>>({})
  const [smSelectedPlaylist, setSmSelectedPlaylist] = useState<Record<number, string>>({})
  const [smPlaylists, setSmPlaylists] = useState<{id: string, title: string}[]>([])
  const [smModalOpenFor, setSmModalOpenFor] = useState<number | null>(null)

  const [showInjectModal, setShowInjectModal] = useState(false)
  const [ytModalOpen, setYtModalOpen] = useState(false)
  const [ytChannels, setYtChannels] = useState<any[]>([])
  const [ytDescription, setYtDescription] = useState<string>('')

  useEffect(() => {
    if (!session?.accessToken) return
    fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/v1/youtube/channels`, {
      headers: { Authorization: `Bearer ${session.accessToken}` }
    })
      .then((r) => r.ok ? r.json() : [])
      .then((data) => setYtChannels(Array.isArray(data) ? data : []))
      .catch(() => setYtChannels([]))
  }, [session?.accessToken])

  useEffect(() => {
    const defaultCh = ytChannels.find((ch: any) => ch.is_default) ?? ytChannels[0]
    if (defaultCh && !smGlobalChannelId) {
      setSmGlobalChannelId(defaultCh.channel_id)
    }
    const channelId = ytChannels[0]?.channel_id
    if (!channelId) {
      setSmPlaylists([])
      return
    }
    const apiBase = process.env.NEXT_PUBLIC_API_URL || ''
    fetch(`${apiBase}/v1/youtube/channels/${channelId}/playlists`)
      .then(r => r.json())
      .then(data => { if (Array.isArray(data)) setSmPlaylists(data) })
      .catch(err => console.warn('Failed to load playlists:', err))
  }, [ytChannels])

  const fmtSec = (sec: number) => `${Math.floor(sec/60)}:${String(Math.floor(sec%60)).padStart(2,'0')}`
  const getAdj = (idx: number, c: any) => ({ start: (c.start_sec??0)+(smTrimAdj[idx]?.startDelta??0), end: (c.end_sec??0)+(smTrimAdj[idx]?.endDelta??0) })

  const handleRegenerateTitle = async (i: number, c: any) => {
    const adj = getAdj(i, c)
    const apiBase = process.env.NEXT_PUBLIC_API_URL || ''
    setSmTitleLoading(p => ({...p, [i]: true}))
    try {
      const res = await fetch(`${apiBase}/v1/shorts/title`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({youtube_id: smYoutubeId, start_sec: adj.start, end_sec: adj.end})
      })
      const data = await res.json()
      if (data.title) setSmTitles(p => ({...p, [i]: data.title}))
      if (data.tags?.length) setSmTags(p => ({...p, [i]: data.tags}))
    } finally {
      setSmTitleLoading(p => ({...p, [i]: false}))
    }
  }

  useEffect(() => {
    if (typeof window === 'undefined') return
    if ((window as any).YT) return
    const tag = document.createElement('script')
    tag.src = 'https://www.youtube.com/iframe_api'
    document.head.appendChild(tag)
  }, [])

  // Portals hook
  const { portals, loading: portalsLoading } = usePortals()
  const [selectedPortalId, setSelectedPortalId] = useState<string>('')
  const [publicationType, setPublicationType] = useState<string>('analiza')
  const [showAddPortalModal, setShowAddPortalModal] = useState(false)

  useEffect(() => {
    if (portals.length > 0 && !selectedPortalId) {
      const defaultPortal = portals.find((p) => p.is_default) ?? portals[0]
      if (defaultPortal) {
        setSelectedPortalId(defaultPortal.id)
      }
    }
  }, [portals, selectedPortalId])

  const accessToken = (session as any)?.accessToken as string | undefined
  const { jobId, jobData, jobLoading, jobError } = useJobLoader(accessToken)

  useEffect(() => {
    if (jobData?.schema_data) {
      const videoId = jobData.video_id || ''
      setResult({
        raw: jobData.schema_data as SchemaData,
        videoId,
        inputUrl: jobData.video_url,
      })
      setUrl(jobData.video_url)
      setActiveTab('article')
    }
  }, [jobData])

  useEffect(() => {
    if (status === 'unauthenticated') router.push('/login')
  }, [status, router])

  useEffect(() => {
    const fetchProfile = async () => {
      if (!session?.accessToken) return
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
        const res = await fetch(`${apiUrl}/v1/users/me`, {
          headers: { Authorization: `Bearer ${session.accessToken as string}` },
        })
        if (res.ok) setUserProfile(await res.json())
      } catch {
        // silent
      }
    }
    fetchProfile()
  }, [session?.accessToken])

  const isPro =
    (userProfile != null && ['pro', 'agency'].includes(userProfile.plan.id)) ||
    (userProfile == null && ['pro', 'agency'].includes((session?.user as any)?.plan ?? ''))

  const handleCopy = useCallback(async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedKey(id)
      setTimeout(() => setCopiedKey(null), 2000)
    } catch {
      // silent
    }
  }, [])

  useEffect(() => {
    if (result?.raw) {
      const wpLink = result.raw?.wp_url as string | undefined
      setYtDescription(buildYtDescription(result.raw as SchemaData, wpLink))
    }
  }, [result])

  const handleGetCandidates = async () => {
    setSmLoading(true)
    setSmError(null)
    setSmCandidates([])
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const res = await fetch(`${apiUrl}/v1/shorts/candidates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(session?.accessToken ? { Authorization: `Bearer ${session.accessToken}` } : {}) },
        body: JSON.stringify({
          youtube_id: smYoutubeId.length === 11 ? smYoutubeId : undefined,
          youtube_url: smYoutubeId.startsWith('http') ? smYoutubeId : undefined,
          custom_query: smCustomQuery,
          count_emotional: smCountEmotional,
          count_professional: smCountProfessional,
          count_custom: smCustomQuery ? smCountCustom : 0,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setSmCandidates(data.candidates || [])
      const newTitles: Record<number, string> = {}
      const newTags: Record<number, string[]> = {}
      ;(data.candidates || []).forEach((c: any, i: number) => {
        newTitles[i] = c.suggested_title || ''
        newTags[i] = c.tags || []
      })
      setSmTitles(newTitles)
      setSmTags(newTags)
    } catch (e: any) {
      setSmError(e.message)
    } finally {
      setSmLoading(false)
    }
  }

  const handleRenderShort = async (candidate: any, index: number) => {
    try {
      const cfg = smRenderConfig[index] || {}
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const res = await fetch(`${apiUrl}/v1/shorts/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(session?.accessToken ? { Authorization: `Bearer ${session.accessToken}` } : {}) },
        body: JSON.stringify({
          youtube_url: smYoutubeId.startsWith('http') ? smYoutubeId : `https://www.youtube.com/watch?v=${smYoutubeId}`,
          youtube_id: smYoutubeId.length === 11 ? smYoutubeId : undefined,
          start_sec: candidate.start_sec,
          end_sec: candidate.end_sec,
          candidate_data: candidate,
          format: smFormat,
          render_format: cfg.format || '9:16',
          subtitles: cfg.subtitles || 'srt',
          output_dir: 'C:\\VSE\\Shorts',
          ...(shortLocalPath ? { local_path: shortLocalPath } : {}),
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const renderJobId = data.job_id
      setSmJobStatus(prev => ({...prev, [index]: {status: 'pending'}}))
      
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        if (attempts > 40) { clearInterval(poll); return }
        try {
          const statusRes = await fetch(`${apiUrl}/v1/shorts/${renderJobId}`, {
            headers: { ...(session?.accessToken ? { Authorization: `Bearer ${session.accessToken}` } : {}) }
          })
          const statusData = await statusRes.json()
          setSmJobStatus(prev => ({...prev, [index]: statusData}))
          if (statusData.status === 'done' || statusData.status === 'error') {
            clearInterval(poll)
          }
        } catch {}
      }, 3000)
    } catch (e: any) {
      setSmError(`Render error: ${e.message}`)
    }
  }

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const res = await fetch(`${apiUrl}/v1/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(session?.accessToken ? { Authorization: `Bearer ${session.accessToken}` } : {}),
        },
        body: JSON.stringify({
          video_url: url.trim(),
          llm_provider: 'claude',
          lang: 'pl',
          publication_type: publicationType,
          portal_id: selectedPortalId === '__manual__' || selectedPortalId === '__add__' || !selectedPortalId ? undefined : selectedPortalId.trim(),
        }),
      })

      let data: GenerateResponse | null = null
      try { data = await res.json() } catch {
        throw new Error(`Serwer zwrócił nieprawidłową odpowiedź (HTTP ${res.status})`)
      }

      if (!res.ok) {
        const detail = (data as unknown as { detail?: string | { msg: string }[] })?.detail
        if (Array.isArray(detail)) throw new Error(detail.map((d) => d.msg).join(', '))
        throw new Error(typeof detail === 'string' ? detail : `Błąd serwera: HTTP ${res.status}`)
      }

      if (!data) throw new Error('Pusta odpowiedź serwera')
      if (data.error) throw new Error(data.error)

      const schema = data.schema_data ?? null
      if (!schema) throw new Error('Serwer nie zwrócił schema_data')

      setResult({ raw: schema, videoId: data.video_id, time: data.processing_time_s, inputUrl: url.trim() })
      setActiveTab('article')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Nieznany błąd')
    } finally {
      setLoading(false)
    }
  }

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-violet-500" />
      </div>
    )
  }

  const schema = result?.raw ?? null
  const chapters = extractChapters(schema)
  const faq = extractFaq(schema)
  const planLabel = userProfile?.plan?.display_name ?? 'Free'
  const usageUsed = userProfile?.usage?.used_this_month ?? 0
  const usageQuota = userProfile?.usage?.quota ?? 5

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gray-950 text-white">
        {/* Sidebar */}
        <aside className="fixed left-0 top-0 h-full w-64 bg-gray-900 border-r border-gray-800 flex flex-col z-20">
          <div className="p-6 border-b border-gray-800">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-violet-600 to-fuchsia-600 flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.069A1 1 0 0121 8.87v6.26a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <span className="font-bold text-white block">VSE</span>
                <span className="text-xs text-gray-500">Video SEO Engine</span>
              </div>
            </div>
          </div>

          <nav className="flex-1 p-4 space-y-1">
            <NavItem icon="grid" label="Dashboard" href="/dashboard" active />
            <NavItem icon="clock" label="Historia" href="/historia" />
            <NavItem icon="settings" label="Ustawienia" href="/ustawienia" />
          </nav>

          {/* User info + plan */}
          <div className="p-4 border-t border-gray-800">
            <div className="mb-3">
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>Użyto</span>
                <span>{usageUsed}/{usageQuota}</span>
              </div>
              <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-full transition-all"
                  style={{ width: `${Math.min(100, (usageUsed / usageQuota) * 100)}%` }}
                />
              </div>
            </div>

            <div className="flex items-center gap-3 mb-3">
              <div className="w-8 h-8 rounded-full bg-violet-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
                {session?.user?.email?.[0]?.toUpperCase() || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white truncate">{session?.user?.email}</p>
                <p className="text-xs text-violet-400">{planLabel}</p>
              </div>
            </div>

            <div className="flex flex-col gap-1 mb-3">
              <a
                href="/cennik"
                className="text-xs text-gray-400 hover:text-violet-300 transition-colors py-0.5"
              >
                ↑ Zmień plan
              </a>
              {userProfile?.plan?.id !== 'free' && (
                <ManageSubscriptionLink accessToken={(session as { accessToken?: string })?.accessToken} />
              )}
            </div>

            <button
              onClick={() => signOut({ callbackUrl: '/login' })}
              className="w-full text-left text-sm text-gray-400 hover:text-white transition-colors py-1"
            >
              → Wyloguj się
            </button>
          </div>
        </aside>

        {/* Main content */}
        <main className="ml-64 p-8">
          <div className="max-w-3xl">
            <EmailVerificationBanner
              isVerified={userProfile?.is_verified}
              accessToken={(session as { accessToken?: string })?.accessToken}
            />

            <h1 className="text-2xl font-bold text-white mb-1">Video SEO Engine</h1>
            <p className="text-gray-400 mb-8">
              Wklej URL YouTube — AI wygeneruje schema VideoObject + Clip + FAQPage.
            </p>

            {jobLoading && (
              <div className="mb-6 flex items-center gap-3 p-4 bg-violet-500/5 border border-violet-500/20 rounded-xl">
                <span className="animate-spin inline-block w-4 h-4 border-2 border-violet-300/30 border-t-violet-400 rounded-full" />
                <span className="text-sm text-violet-300">Ładowanie wyników z historii...</span>
              </div>
            )}

            {jobError && (
              <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
                ⚠️ {jobError}
              </div>
            )}

            {jobId && result && (
              <div className="mb-6 flex items-center gap-2 p-3 bg-blue-500/5 border border-blue-500/20 rounded-xl">
                <span className="text-xs text-blue-400">📋 Wyniki załadowane z historii</span>
                <Link href="/historia" className="text-xs text-gray-500 hover:text-white ml-auto transition-colors">
                  ← Wróć do historii
                </Link>
              </div>
            )}

            {/* Portal & Publication Type Selector */}
            <div className="grid grid-cols-2 gap-3 mb-5">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Portal docelowy</label>
                {portalsLoading ? (
                  <div className="flex items-center gap-2 h-[42px] text-sm text-gray-500">
                    <span className="animate-spin inline-block w-3 h-3 border border-gray-500 border-t-violet-400 rounded-full" />
                    Ładowanie...
                  </div>
                ) : portals.length === 0 ? (
                  <select
                    value=""
                    onChange={(e) => {
                      const val = e.target.value
                      if (val === '__add__') {
                        setShowAddPortalModal(true)
                      } else if (val === '__manual__') {
                        setSelectedPortalId('__manual__')
                      }
                    }}
                    className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer"
                    style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3E%3Cpath stroke=\'%236b7280\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.75rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }}
                  >
                    <option value="" disabled>Brak portali — dodaj pierwszy portal</option>
                    <option value="__add__">+ Dodaj nowy portal...</option>
                    <option value="__manual__">✏️ Wpisz ręcznie...</option>
                  </select>
                ) : (
                  <select
                    id="portal-selector"
                    value={selectedPortalId}
                    onChange={(e) => {
                      const val = e.target.value
                      if (val === '__add__') {
                        setShowAddPortalModal(true)
                      } else if (val === '__manual__') {
                        setSelectedPortalId('__manual__')
                      } else {
                        setSelectedPortalId(val)
                      }
                    }}
                    className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer"
                    style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3E%3Cpath stroke=\'%236b7280\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.75rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }}
                  >
                    {portals.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                    <option value="__add__">+ Dodaj nowy portal...</option>
                    <option value="__manual__">✏️ Wpisz ręcznie...</option>
                  </select>
                )}
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Typ publikacji</label>
                <select
                  id="publication-type-selector"
                  value={publicationType}
                  onChange={(e) => setPublicationType(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer"
                  style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3E%3Cpath stroke=\'%236b7280\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.5rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }}
                >
                  <option value="full_analysis">📝 Pełna analiza</option>
                  <option value="watching_page">🎬 Strona z filmem</option>
                  <option value="discover">🔍 Discover</option>
                </select>
              </div>
            </div>

            {/* URL Form */}
            <form onSubmit={handleGenerate} className="mb-8">
              <div className="flex gap-3">
                <input
                  id="youtube-url-input"
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=..."
                  className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
                />
                <button
                  id="generate-btn"
                  type="submit"
                  disabled={loading || !url.trim()}
                  className="px-6 py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-xl font-semibold text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2 whitespace-nowrap"
                >
                  {loading ? (
                    <><span className="animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> Generuję...</>
                  ) : (
                    <>✦ Generuj SEO</>
                  )}
                </button>
              </div>

              {loading && (
                <div className="mt-3 flex items-center gap-2 text-sm text-gray-400">
                  <span className="animate-spin inline-block w-3 h-3 border border-gray-500 border-t-violet-400 rounded-full" />
                  Pobieranie transkryptu i generowanie schema... (~50s)
                </div>
              )}

              {error && (
                <div className="mt-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm flex items-start gap-2">
                  <span className="flex-shrink-0 mt-0.5">⚠️</span>
                  <div>
                    <p className="font-medium mb-0.5">Wystąpił błąd</p>
                    <p className="text-red-300/80">{error}</p>
                  </div>
                </div>
              )}
            </form>

            {!result && !loading && (
              <>
                <div className="grid grid-cols-3 gap-4 mb-8">
                  {[
                    { label: 'Filmy w tym miesiącu', value: `${usageUsed}/${usageQuota}`, sub: `Plan ${planLabel}` },
                    { label: 'Benchmark score', value: '8/10', sub: 'vs 2—3/10 konkurencja' },
                    { label: 'Schema standard', value: 'v5.3', sub: 'Google 2026' },
                  ].map((stat) => (
                    <div key={stat.label} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                      <p className="text-gray-400 text-sm mb-1">{stat.label}</p>
                      <p className="text-2xl font-bold text-white">{stat.value}</p>
                      <p className="text-xs text-gray-500 mt-1">{stat.sub}</p>
                    </div>
                  ))}
                </div>
                <WpQuickPanel />
              </>
            )}

            {/* Results */}
            {result && (
              <div>
                <div className="flex items-center justify-between mb-5">
                  <div>
                    <h2 className="text-lg font-semibold text-white">Wyniki SEO</h2>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Video: <span className="font-mono">{result.videoId}</span>
                      {result.time && <> • {result.time.toFixed(1)}s</>}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-sm rounded-full border border-emerald-500/20">
                      ✔️ Wygenerowano
                    </span>
                    {isPro && (
                      <button
                        onClick={() => setShowInjectModal(true)}
                        className="px-4 py-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-sm font-medium text-white rounded-full hover:opacity-90 transition-all flex items-center gap-1.5"
                      >
                        🚀 Wyślij do portalu
                      </button>
                    )}
                    {ytChannels.length > 0 && (
                      <button
                        onClick={() => setYtModalOpen(true)}
                        className="px-4 py-1.5 bg-gradient-to-r from-red-600 to-red-500 text-sm font-medium text-white rounded-full hover:opacity-90 transition-all flex items-center gap-1.5 ml-2"
                      >
                        ▶️ Wyślij na YouTube
                      </button>
                    )}
                  </div>
                </div>

                <TabBar
                  active={activeTab}
                  onChange={setActiveTab}
                  chaptersCount={chapters.length}
                  faqCount={faq.length}
                />

                {/* Tab: Schemat */}
                {activeTab === 'schema' && (
                  <div>
                    <ResultSection
                      title="Tytuł artykułu"
                      copyText={schema?.post_title ?? ''}
                      copyId="post_title"
                      copiedKey={copiedKey}
                      onCopy={handleCopy}
                    >
                      <p className="text-white font-medium">{schema?.post_title ?? '(brak tytułu)'}</p>
                      {schema?.focus_keyphrase && (
                        <p className="text-xs text-gray-500 mt-1">
                          Focus: <span className="text-violet-400">{schema.focus_keyphrase}</span>
                        </p>
                      )}
                    </ResultSection>

                    <ResultSection
                      title="Meta description"
                      copyText={schema?.meta_description ?? ''}
                      copyId="meta_description"
                      copiedKey={copiedKey}
                      onCopy={handleCopy}
                    >
                      <p className="text-gray-300 text-sm leading-relaxed">
                        {schema?.meta_description ?? '(brak meta description)'}
                      </p>
                    </ResultSection>

                    <ResultSection
                      title="Schema JSON-LD"
                      copyText={schemaToScriptTag(schema)}
                      copyId="schema_jsonld"
                      copiedKey={copiedKey}
                      onCopy={handleCopy}
                      badge="Wklej do <head>"
                    >
                      <pre className="text-xs text-emerald-400 font-mono overflow-auto max-h-72 leading-relaxed">
{`<script type="application/ld+json">`}
{JSON.stringify(schema ?? {}, null, 2)}
{`</script>`}
                      </pre>
                    </ResultSection>
                  </div>
                )}

                {/* Tab: Artykuł */}
                {activeTab === 'article' && (
                  <div>
                    <div className="flex justify-end mb-4">
                      <CopyButton
                        text={articleToText(schema, faq)}
                        id="article_all"
                        copiedKey={copiedKey}
                        onCopy={handleCopy}
                        label="Kopiuj cały artykuł"
                      />
                    </div>

                    <ResultSection
                      title="Lead artykułu"
                      copyText={schema?.lead ?? ''}
                      copyId="lead"
                      copiedKey={copiedKey}
                      onCopy={handleCopy}
                    >
                      <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
                        {schema?.lead ?? '(brak leadu)'}
                      </p>
                    </ResultSection>

                    <ResultSection
                      title="Treść artykułu"
                      copyText={schema?.article_body ?? ''}
                      copyId="article_body"
                      copiedKey={copiedKey}
                      onCopy={handleCopy}
                    >
                      <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
                        {schema?.article_body ?? '(brak treści)'}
                      </div>
                    </ResultSection>

                    {faq.length > 0 && (
                      <ResultSection
                        title="Sekcja FAQ (HTML)"
                        copyText={faqToHtml(faq)}
                        copyId="faq"
                        copiedKey={copiedKey}
                        onCopy={handleCopy}
                        badge={`${faq.length} pytań`}
                      >
                        <div className="space-y-3 text-sm">
                          {faq.map((item, idx) => (
                            <details key={idx} className="bg-gray-800/50 rounded-lg p-3 border border-gray-700/50">
                              <summary className="font-medium text-violet-300 cursor-pointer">{item.question}</summary>
                              <p className="mt-2 text-gray-400 text-xs leading-relaxed">{item.answer}</p>
                            </details>
                          ))}
                        </div>
                      </ResultSection>
                    )}
                  </div>
                )}

                {/* Tab: Rozdziały */}
                {activeTab === 'chapters' && (
                  <div>
                    <ResultSection
                      title="Rozdziały YouTube"
                      copyText={chaptersToText(chapters)}
                      copyId="chapters"
                      copiedKey={copiedKey}
                      onCopy={handleCopy}
                      badge={`${chapters.length} rozdziałów`}
                    >
                      <pre className="text-xs text-gray-300 font-mono overflow-auto max-h-60 leading-relaxed">
                        {chaptersToText(chapters)}
                      </pre>
                    </ResultSection>
                  </div>
                )}

                {/* Tab: Opis YouTube */}
                {activeTab === 'youtube' && (
                  <div>
                    <ResultSection
                      title="Wygenerowany opis YouTube"
                      copyText={ytDescription}
                      copyId="yt_desc"
                      copiedKey={copiedKey}
                      onCopy={handleCopy}
                    >
                      <pre className="text-xs text-gray-300 font-mono overflow-auto max-h-96 whitespace-pre-wrap leading-relaxed">
                        {ytDescription}
                      </pre>
                    </ResultSection>
                  </div>
                )}

                {/* Tab: ShortMachine */}
                {activeTab === 'shorts' && (
                  <div className="space-y-6">
                    <h2 className="text-xl font-semibold text-white">✂️ ShortMachine</h2>
                    
                    <div className="bg-gray-800 rounded-xl p-6 space-y-4">
                      <h3 className="text-lg font-medium text-white">Propozycje kandydatów</h3>
                      
                      <div>
                        <label className="block text-sm text-gray-400 mb-1">YouTube ID lub URL</label>
                        <input
                          id="sm-youtube-id"
                          type="text"
                          value={smYoutubeId}
                          onChange={e => setSmYoutubeId(e.target.value)}
                          placeholder="np. dQw4w9WgXcQ"
                          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        />
                      </div>

                      <div className="flex items-center gap-2 mt-2 mb-4">
                        <label className="text-sm text-gray-400 whitespace-nowrap">Plik lokalny</label>
                        <input
                          type="text"
                          value={shortLocalPath}
                          onChange={e => setShortLocalPath(e.target.value)}
                          placeholder="C:\\Users\\...\\video.mp4 (opcjonalny)"
                          className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-gray-200 placeholder-gray-500"
                        />
                        <label className="cursor-pointer bg-gray-700 hover:bg-gray-600 border border-gray-500 rounded px-3 py-1 text-sm text-gray-200 flex items-center gap-1">
                          📁 Browse
                          <input
                            type="file"
                            accept="video/*,.mp4,.mov,.mkv,.avi"
                            className="hidden"
                            onChange={e => {
                              const file = e.target.files?.[0]
                              if (file) setShortLocalPath(file.name)
                            }}
                          />
                        </label>
                      </div>
                      
                      <div>
                        <label className="block text-sm text-gray-400 mb-1">Custom query (opcjonalny)</label>
                        <input
                          id="sm-custom-query"
                          type="text"
                          value={smCustomQuery}
                          onChange={e => setSmCustomQuery(e.target.value)}
                          placeholder="np. Niemcy teściową Europy"
                          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                        />
                      </div>
                      
                      <div className="grid grid-cols-3 gap-3">
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Emotional</label>
                          <input id="sm-count-emotional" type="number" min="0" max="5" value={smCountEmotional}
                            onChange={e => setSmCountEmotional(Number(e.target.value))}
                            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Professional</label>
                          <input id="sm-count-professional" type="number" min="0" max="5" value={smCountProfessional}
                            onChange={e => setSmCountProfessional(Number(e.target.value))}
                            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Custom</label>
                          <input id="sm-count-custom" type="number" min="0" max="5" value={smCountCustom}
                            onChange={e => setSmCountCustom(Number(e.target.value))}
                            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
                        </div>
                      </div>
                      
                      <style>{`@keyframes sm-spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
                      <button
                        id="sm-get-candidates-btn"
                        onClick={handleGetCandidates}
                        disabled={smLoading || !smYoutubeId}
                        className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 px-4 rounded-lg transition-colors"
                      >
                        {smLoading ? (
                          <>
                            <svg style={{display:'inline-block',width:'16px',height:'16px',animation:'sm-spin 0.8s linear infinite',marginRight:'8px',verticalAlign:'middle'}} viewBox="0 0 24 24" fill="none">
                              <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.3)" strokeWidth="3"/>
                              <path d="M12 2a10 10 0 0 1 10 10" stroke="white" strokeWidth="3" strokeLinecap="round"/>
                            </svg>
                            Analizuję transkrypt AI...
                          </>
                        ) : '🎯 Analizuj wideo'}
                      </button>
                    </div>
                    
                    <div className="flex items-center gap-3 py-2 px-3 bg-gray-800/50 rounded-lg border border-gray-700/50">
                      <span className="text-xs text-gray-400">Format renderowania:</span>
                      {(['raw', 'short'] as const).map((fmt) => (
                        <button
                          key={fmt}
                          onClick={() => setSmFormat(fmt)}
                          className={`px-3 py-1 text-xs rounded border transition-all ${
                            smFormat === fmt
                              ? 'bg-violet-600/20 border-violet-500/40 text-violet-400'
                              : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white'
                          }`}
                        >
                          {fmt === 'raw' ? '📼 Raw (szybki cut)' : '✂️ Short (9:16)'}
                        </button>
                      ))}
                      <span className="text-xs text-gray-600 ml-auto">
                        {smFormat === 'raw' ? 'ffmpeg -c copy, bez re-encode' : 'Przetwarzanie 9:16 + SRT'}
                      </span>
                    </div>

                    {/* Globalny selektor kanału YT */}
                    {ytChannels.length > 0 && (
                      <div className="flex items-center gap-3 mb-4 px-1">
                        <span className="text-xs text-gray-400 whitespace-nowrap">Kanał YT:</span>
                        <select
                          className="flex-1 bg-gray-800 border border-gray-700 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-violet-500"
                          value={smGlobalChannelId}
                          onChange={e => setSmGlobalChannelId(e.target.value)}
                        >
                          {ytChannels.map((ch: any) => (
                            <option key={ch.channel_id} value={ch.channel_id}>
                              {ch.is_default ? '★ ' : ''}{ch.channel_title}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                    {smCandidates.length > 0 && (
                      <div className="space-y-3">
                        <h3 className="text-lg font-medium text-white">Kandydaci ({smCandidates.length})</h3>
                        <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-700">
                          <input
                            type="checkbox"
                            id="selectAllCandidates"
                            checked={smCandidates.length > 0 && smSelected.size === smCandidates.length}
                            onChange={(e) => {
                              if (e.target.checked) setSmSelected(new Set(smCandidates.map((_: any, idx: number) => idx)))
                              else setSmSelected(new Set())
                            }}
                            style={{cursor:'pointer',accentColor:'#3b82f6'}}
                          />
                          <label htmlFor="selectAllCandidates" className="text-xs text-gray-400 cursor-pointer">
                            Zaznacz wszystkie ({smCandidates.length})
                          </label>
                        </div>
                        {smCandidates.map((c, i) => (
                          <div key={i} className="bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-3">
                            <div className="flex items-start justify-between">
                              <div className="flex items-center gap-2">
                                <input type="checkbox" checked={smSelected.has(i)} onChange={() => toggleSmSelected(i)} style={{cursor:'pointer',accentColor:'#3b82f6'}} />
                                <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                                  c.type === 'emotional' ? 'bg-red-900 text-red-300' :
                                  c.type === 'professional' ? 'bg-blue-900 text-blue-300' :
                                  'bg-purple-900 text-purple-300'
                                }`}>{c.type}</span>
                                <span className="text-sm text-gray-400">
                                  {Math.floor(c.start_sec / 60)}:{String(Math.floor(c.start_sec % 60)).padStart(2,'0')} - 
                                  {Math.floor(c.end_sec / 60)}:{String(Math.floor(c.end_sec % 60)).padStart(2,'0')}
                                  &nbsp;({c.duration_sec}s)
                                </span>
                              </div>
                              <div style={{display:'flex', gap:'8px', alignItems:'center'}}>
                                <span className="text-yellow-400 text-sm">
                                  {'★'.repeat(Math.round(c.score * 5))}{'☆'.repeat(5 - Math.round(c.score * 5))}
                                </span>
                                <button onClick={() => setSmExpandedIdx(smExpandedIdx === i ? null : i)} style={{padding:'2px 8px',fontSize:'11px',background: smExpandedIdx===i ? '#1e40af' : '#1e293b',border:'1px solid '+(smExpandedIdx===i?'#3b82f6':'#334155'),borderRadius:'4px',color: smExpandedIdx===i?'#93c5fd':'#94a3b8',cursor:'pointer'}}>
                                  {smExpandedIdx === i ? '▲ Transkrypt' : '✏ Transkrypt'}
                                </button>
                              </div>
                            </div>
                            
                            <div className="text-sm space-y-1">
                              <p><span className="text-gray-400">Hook:</span> <span className="text-white">{c.hook_text}</span></p>
                              <p><span className="text-gray-400">Puenta:</span> <span className="text-white">{c.punchline_text}</span></p>
                              {c.query_match && (
                                <p><span className="text-gray-400">Match:</span> <span className="text-green-400">{c.query_match}</span></p>
                              )}
                            </div>
                            
                            {smExpandedIdx === i && (
                              <div style={{marginBottom:'12px',border:'1px solid #334155',borderRadius:'8px',overflow:'hidden',background:'#0f172a'}}>
                                {(() => {
                                  const ytMatch = (c.youtube_url||'').match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/)
                                  const ytId = ytMatch ? ytMatch[1] : null
                                  const adjStart = getAdj(i, c).start
                                  return ytId ? (
                                    <div style={{position:'relative',paddingBottom:'56.25%',height:0,overflow:'hidden'}}>
                                      <iframe key={`yt-${i}-${Math.floor(adjStart)}`} src={`https://www.youtube.com/embed/${ytId}?start=${Math.floor(adjStart)}&autoplay=0&rel=0`} style={{position:'absolute',top:0,left:0,width:'100%',height:'100%',border:'none'}} allowFullScreen />
                                    </div>
                                  ) : <div style={{padding:'8px',color:'#64748b',fontSize:'12px'}}>Brak YouTube URL dla podglądu</div>
                                })()}
                                <div style={{maxHeight:'220px',overflowY:'auto',padding:'8px'}}>
                                  <div style={{display:'flex',gap:'6px',marginBottom:'8px',alignItems:'center'}}>
                                    <span style={{fontSize:'11px',color:'#94a3b8'}}>Klik ustawia:</span>
                                    <button onClick={()=>setSmTrimMode('start')} style={{padding:'2px 8px',fontSize:'11px',borderRadius:'4px',border:'none',cursor:'pointer',background:smTrimMode==='start'?'#3b82f6':'#1e293b',color:smTrimMode==='start'?'#fff':'#94a3b8'}}>◀ Start</button>
                                    <button onClick={()=>setSmTrimMode('end')} style={{padding:'2px 8px',fontSize:'11px',borderRadius:'4px',border:'none',cursor:'pointer',background:smTrimMode==='end'?'#f59e0b':'#1e293b',color:smTrimMode==='end'?'#fff':'#94a3b8'}}>Koniec ▶</button>
                                    <span style={{marginLeft:'auto',fontSize:'11px',color:'#64748b'}}>{(c.vtt_segments||[]).length} segmentów</span>
                                  </div>
                                  {(c.vtt_segments||[]).map((seg: any, si: number) => {
                                    const adj = getAdj(i, c)
                                    const isInRange = seg.ts >= adj.start && seg.ts <= adj.end
                                    return (
                                      <div key={si} onClick={() => { if (smTrimMode === 'start') { setSmTrimAdj((p: any) => ({...p, [i]: {startDelta: seg.ts - (c.start_sec??0), endDelta: p[i]?.endDelta??0}})); } else { setSmTrimAdj((p: any) => ({...p, [i]: {startDelta: p[i]?.startDelta??0, endDelta: seg.ts - (c.end_sec??0) + 2}})); } }} style={{padding:'4px 8px',marginBottom:'2px',borderRadius:'4px',cursor:'pointer',fontSize:'12px',lineHeight:'1.4',background: isInRange ? 'rgba(59,130,246,0.15)' : 'transparent',borderLeft: isInRange ? '3px solid #3b82f6' : '3px solid transparent',color: isInRange ? '#e2e8f0' : '#64748b',transition: 'background 0.1s'}}>
                                        <span style={{color:'#475569',marginRight:'8px',fontFamily:'monospace',fontSize:'11px'}}>{seg.time_str}</span>
                                        {seg.text}
                                      </div>
                                    )
                                  })}
                                </div>
                              </div>
                            )}

                            <div className="space-y-1 mb-2">
                              <div className="flex items-center gap-2">
                                <input
                                  type="text"
                                  value={smTitles[i] || ''}
                                  onChange={e => setSmTitles(p => ({...p, [i]: e.target.value}))}
                                  placeholder="Tytuł shorta..."
                                  className="flex-1 bg-gray-900 border border-gray-600 rounded px-2 py-1 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500"
                                />
                                {(smTrimAdj[i]?.startDelta || smTrimAdj[i]?.endDelta) && (
                                  <button
                                    onClick={() => handleRegenerateTitle(i, c)}
                                    disabled={smTitleLoading[i]}
                                    className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 border border-gray-600 rounded text-gray-300 disabled:opacity-50"
                                    title="Odśwież tytuł i tagi na podstawie nowego zakresu"
                                  >
                                    {smTitleLoading[i] ? '...' : '🔄'}
                                  </button>
                                )}
                              </div>
                              <div className="flex flex-wrap gap-1">
                                {(smTags[i] || []).map((tag, ti) => (
                                  <span key={ti} className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-700 border border-gray-600 rounded-full text-xs text-gray-300">
                                    {tag}
                                    <button onClick={() => setSmTags(p => ({...p, [i]: (p[i]||[]).filter((_,j)=>j!==ti)}))} className="text-gray-500 hover:text-red-400 leading-none">×</button>
                                  </span>
                                ))}
                              </div>
                            </div>

                            <div className="mb-2">
                              <button
                                onClick={() => {
                                  if (smPreviewIdx === i) {
                                    setSmPreviewIdx(null)
                                    if (ytIntervalRef.current) clearInterval(ytIntervalRef.current)
                                    return
                                  }
                                  setSmPreviewIdx(i)
                                  const adj2 = getAdj(i, c)
                                  const videoId2 = smYoutubeId.length === 11 ? smYoutubeId : smYoutubeId.match(/[a-zA-Z0-9_-]{11}/)?.[0] || ''
                                  setTimeout(() => {
                                    if (!(window as any).YT?.Player) return
                                    if (ytPlayerRef.current?.destroy) ytPlayerRef.current.destroy()
                                    if (ytIntervalRef.current) clearInterval(ytIntervalRef.current)
                                    ytPlayerRef.current = new (window as any).YT.Player(`yt-preview-${i}`, {
                                      height: '180',
                                      width: '320',
                                      videoId: videoId2,
                                      playerVars: { start: Math.floor(adj2.start), autoplay: 1, rel: 0, modestbranding: 1 },
                                      events: {
                                        onReady: (e: any) => {
                                          e.target.seekTo(adj2.start, true)
                                          e.target.playVideo()
                                          ytIntervalRef.current = setInterval(() => {
                                            const t = e.target.getCurrentTime()
                                            if (t >= adj2.end) {
                                              e.target.pauseVideo()
                                              clearInterval(ytIntervalRef.current)
                                            }
                                          }, 250)
                                        }
                                      }
                                    })
                                  }, 100)
                                }}
                                className="text-xs text-blue-400 hover:text-blue-300 underline cursor-pointer"
                              >
                                {smPreviewIdx === i ? '▼ Zamknij podgląd' : '▶ Podgląd'}
                              </button>

                              {smPreviewIdx === i && (
                                <div className="mt-2 rounded overflow-hidden" style={{width:320}}>
                                  <div id={`yt-preview-${i}`} />
                                  <div className="text-xs text-gray-500 mt-1">
                                    {fmtSec(getAdj(i,c).start)} → {fmtSec(getAdj(i,c).end)} ({Math.round(getAdj(i,c).end-getAdj(i,c).start)}s)
                                  </div>
                                </div>
                              )}
                            </div>
                            <div style={{display:'flex',alignItems:'center',gap:'6px',flexWrap:'wrap',marginBottom:'8px',fontSize:'12px',color:'#888'}}>
                              <span>✂ Start:</span>
                              {([-5,-2,-1] as number[]).map(d=>(
                                <button key={d} onClick={()=>setSmTrimAdj(p=>({...p,[i]:{startDelta:(p[i]?.startDelta??0)+d,endDelta:p[i]?.endDelta??0}}))} style={{padding:'1px 5px',fontSize:'11px',background:'#1e293b',border:'1px solid #334155',borderRadius:'3px',color:'#94a3b8',cursor:'pointer'}}>{d}s</button>
                              ))}
                              <span style={{color:'#e2e8f0',minWidth:'36px',textAlign:'center'}}>{fmtSec(getAdj(i,c).start)}</span>
                              {([1,2,5] as number[]).map(d=>(
                                <button key={d} onClick={()=>setSmTrimAdj(p=>({...p,[i]:{startDelta:(p[i]?.startDelta??0)+d,endDelta:p[i]?.endDelta??0}}))} style={{padding:'1px 5px',fontSize:'11px',background:'#1e293b',border:'1px solid #334155',borderRadius:'3px',color:'#94a3b8',cursor:'pointer'}}>+{d}s</button>
                              ))}
                              <span style={{marginLeft:'8px'}}>Koniec:</span>
                              {([-5,-2,-1] as number[]).map(d=>(
                                <button key={d} onClick={()=>setSmTrimAdj(p=>({...p,[i]:{startDelta:p[i]?.startDelta??0,endDelta:(p[i]?.endDelta??0)+d}}))} style={{padding:'1px 5px',fontSize:'11px',background:'#1e293b',border:'1px solid #334155',borderRadius:'3px',color:'#94a3b8',cursor:'pointer'}}>{d}s</button>
                              ))}
                              <span style={{color:'#e2e8f0',minWidth:'36px',textAlign:'center'}}>{fmtSec(getAdj(i,c).end)}</span>
                              {([1,2,5] as number[]).map(d=>(
                                <button key={d} onClick={()=>setSmTrimAdj(p=>({...p,[i]:{startDelta:p[i]?.startDelta??0,endDelta:(p[i]?.endDelta??0)+d}}))} style={{padding:'1px 5px',fontSize:'11px',background:'#1e293b',border:'1px solid #334155',borderRadius:'3px',color:'#94a3b8',cursor:'pointer'}}>+{d}s</button>
                              ))}
                              <span style={{marginLeft:'6px',color:'#64748b'}}>{Math.round(getAdj(i,c).end-getAdj(i,c).start)}s</span>
                              {(smTrimAdj[i]?.startDelta||smTrimAdj[i]?.endDelta)?<button onClick={()=>setSmTrimAdj(p=>({...p,[i]:{startDelta:0,endDelta:0}}))} style={{padding:'1px 5px',fontSize:'10px',background:'transparent',border:'1px solid #475569',borderRadius:'3px',color:'#64748b',cursor:'pointer',marginLeft:'auto'}}>↺</button>:null}
                            </div>

                            <div className="grid grid-cols-3 gap-2 pt-2 border-t border-gray-700">
                              <select
                                value={smRenderConfig[i]?.format || '9:16'}
                                onChange={e => setSmRenderConfig(prev => ({...prev, [i]: {...(prev[i]||{}), format: e.target.value}}))}
                                className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-xs"
                              >
                                <option value="9:16">9:16 (Shorts)</option>
                                <option value="16:9">16:9 (YT)</option>
                              </select>
                              <select
                                value={smRenderConfig[i]?.subtitles || 'srt'}
                                onChange={e => setSmRenderConfig(prev => ({...prev, [i]: {...(prev[i]||{}), subtitles: e.target.value}}))}
                                className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-xs"
                              >
                                <option value="none">Bez napisów</option>
                                <option value="srt">Export SRT</option>
                              </select>
                              <button
                                id={`sm-render-btn-${i}`}
                                onClick={() => { const a = getAdj(i, c); handleRenderShort({ ...c, start_sec: a.start, end_sec: a.end }, i); }}
                                className="bg-green-700 hover:bg-green-600 text-white text-xs font-medium px-3 py-1 rounded transition-colors"
                              >
                                ▶ Renderuj
                              </button>
                            </div>
                            
                            {smJobStatus[i] && (
                              <div className={`text-xs px-2 py-1 rounded ${
                                smJobStatus[i].status === 'done' ? 'bg-green-900 text-green-300' :
                                smJobStatus[i].status === 'error' ? 'bg-red-900 text-red-300' :
                                'bg-yellow-900 text-yellow-300'
                              }`}>
                                {smJobStatus[i].status === 'done' ? (
                                  <div className="flex flex-col gap-1">
                                    <span>Gotowe: {smJobStatus[i].result_paths?.raw || 'plik zapisany'}</span>
                                    {smJobStatus[i].result_paths?.raw && (
                                      <button
                                        onClick={() => {
                                          const rawPath = smJobStatus[i].result_paths?.raw || ''
                                          const folderPath = rawPath.includes('\\') || rawPath.includes('/')
                                            ? rawPath.substring(0, Math.max(rawPath.lastIndexOf('\\'), rawPath.lastIndexOf('/')))
                                            : rawPath
                                          navigator.clipboard.writeText(folderPath).then(() => {})
                                        }}
                                        className="mt-1 text-xs text-violet-400 hover:text-violet-300 border border-violet-500/30 rounded px-2 py-0.5 transition-colors self-start"
                                        title="Kopiuj ścieżkę folderu do schowka"
                                      >
                                        📋 Kopiuj ścieżkę folderu
                                      </button>
                                    )}
                                  </div>
                                ) : smJobStatus[i].status === 'error' ? (
                                  <span>Błąd: {smJobStatus[i].error}</span>
                                ) : (
                                  <span>Przetwarzam... ({smJobStatus[i].status})</span>
                                )}
                              </div>
                            )}
                            
                            {/* YouTube Inject Block */}
                            <div className="border-t border-gray-600 pt-3 mt-1">
                              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">► Wstrzyknij metadane na YouTube</p>
                              {ytChannels.length > 1 && (
                                <select
                                  className="w-full bg-gray-700 text-white text-xs rounded px-2 py-1 border border-gray-600 mb-2"
                                  value={smChannelOverride[i] ?? ''}
                                  onChange={e => setSmChannelOverride(prev => ({...prev, [i]: e.target.value}))}
                                >
                                  <option value="">🌐 {ytChannels.find((ch: any) => ch.channel_id === smGlobalChannelId)?.channel_title || 'Kanał globalny'}</option>
                                  {ytChannels.filter((ch: any) => ch.channel_id !== smGlobalChannelId).map((ch: any) => (
                                    <option key={ch.channel_id} value={ch.channel_id}>{ch.channel_title}</option>
                                  ))}
                                </select>
                              )}
                              <input
                                type="text"
                                placeholder="URL lub ID YouTube (wgrany z Premiere Pro)"
                                className="w-full bg-gray-700 text-white text-sm rounded px-3 py-2 border border-gray-600 focus:border-blue-500 focus:outline-none mb-2"
                                value={smTargetYtId[i] || ''}
                                onChange={e => setSmTargetYtId(prev => ({...prev, [i]: e.target.value}))}
                              />
                              <div className="grid grid-cols-3 gap-2 mb-2">
                                <select
                                  className="bg-gray-700 text-white text-sm rounded px-2 py-2 border border-gray-600"
                                  value={smSelectedPlaylist[i] || ''}
                                  onChange={e => setSmSelectedPlaylist(prev => ({...prev, [i]: e.target.value}))}
                                >
                                  <option value="">Playlista (opcj.)</option>
                                  {smPlaylists.map(pl => <option key={pl.id} value={pl.id}>{pl.title}</option>)}
                                </select>
                                <input
                                  type="datetime-local"
                                  className="bg-gray-700 text-white text-sm rounded px-2 py-2 border border-gray-600"
                                  value={smPublishAt[i] || ''}
                                  onChange={e => setSmPublishAt(prev => ({...prev, [i]: e.target.value}))}
                                />
                                <select
                                  className="bg-gray-700 text-white text-sm rounded px-2 py-2 border border-gray-600"
                                  value={smPrivacyStatus[i] || 'private'}
                                  onChange={e => setSmPrivacyStatus(prev => ({...prev, [i]: e.target.value}))}
                                >
                                  <option value="private">Prywatny</option>
                                  <option value="unlisted">Niepubliczny</option>
                                  <option value="public">Publiczny</option>
                                </select>
                              </div>
                              <div className="flex items-center gap-3">
                                <button
                                  onClick={() => setSmModalOpenFor(i)}
                                  disabled={!smTargetYtId[i]}
                                  className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded transition-colors"
                                >
                                  ► Podgląd i publikacja
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}
                        {smSelected.size > 0 && (
                          <div style={{position:'sticky',bottom:'8px',textAlign:'center',marginTop:'8px',zIndex:10}}>
                            <button onClick={() => { smSelected.forEach((selIdx: number) => { const c = smCandidates[selIdx]; const a = getAdj(selIdx, c); handleRenderShort({...c, start_sec: a.start, end_sec: a.end}, selIdx); }); setSmSelected(new Set()); }} style={{padding:'10px 24px',background:'linear-gradient(135deg,#059669,#10b981)',border:'none',borderRadius:'8px',color:'#fff',fontWeight:'600',fontSize:'14px',cursor:'pointer',boxShadow:'0 4px 12px rgba(16,185,129,0.3)'}}>
                              ► Renderuj zaznaczone ({smSelected.size})
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                    
                    {smError && (
                      <div className="bg-red-900 border border-red-700 text-red-300 rounded-lg p-3 text-sm">
                        {smError}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </main>

        {/* ShortMachine YouTube Inject Modal */}
        {smModalOpenFor !== null && smCandidates[smModalOpenFor] && (() => {
          const i = smModalOpenFor
          const c = smCandidates[i]
          const smSchemaData = {
            youtube_description_hook: smTitles[i] || c.suggested_title || c.title || '',
            video_description: c.hook || '',
            youtube_hashtags: smTags[i] || c.tags || []
          }
          const rawInput = smTargetYtId[i] || ''
          const smVideoId = rawInput.match(/(?:v=|youtu\.be\/|\/shorts\/)([A-Za-z0-9_-]{11})/)?.[1] || rawInput

          return (
            <YouTubePublishModal
              isOpen={true}
              onClose={() => setSmModalOpenFor(null)}
              videoId={smVideoId}
              schemaData={smSchemaData}
              wpUrl=""
              channels={(smChannelOverride[i] || smGlobalChannelId) ? [ytChannels.find((ch: any) => ch.channel_id === (smChannelOverride[i] || smGlobalChannelId)) ?? ytChannels[0]].filter(Boolean) : ytChannels}
              accessToken={accessToken || ""}
              apiUrl={process.env.NEXT_PUBLIC_API_URL || ''}
              publishAt={smPublishAt[i]}
              privacyStatus={smPrivacyStatus[i]}
              playlistId={smSelectedPlaylist[i]}
            />
          )
        })()}

        {/* Inject Modal */}
        {showInjectModal && result && (() => {
          const selectedPortal = portals.find((p) => p.id === selectedPortalId)
          return (
            <InjectModal
              schemaData={result.raw}
              videoUrl={result.inputUrl}
              accessToken={accessToken}
              onClose={() => setShowInjectModal(false)}
              selectedPortalId={selectedPortalId}
              portalName={selectedPortal?.name}
              portalUrl={selectedPortal?.url}
              ytChannels={ytChannels}
            />
          )
        })()}

        {ytModalOpen && result && (() => {
          const wpUrl = result.raw?.wp_article_url || result.raw?.published_url || ""
          const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''

          return (
            <YouTubePublishModal
              overrideDescription={ytDescription}
              isOpen={ytModalOpen}
              onClose={() => setYtModalOpen(false)}
              videoId={result.raw?.video_id || extractVideoId(result.inputUrl) || ""}
              schemaData={result.raw ?? {}}
              wpUrl={wpUrl}
              channels={ytChannels}
              accessToken={accessToken || ""}
              apiUrl={apiUrl}
            />
          )
        })()}

        {showAddPortalModal && (
          <AddPortalModal
            onClose={() => setShowAddPortalModal(false)}
            onSuccess={(portalId) => {
              setShowAddPortalModal(false)
              setSelectedPortalId(portalId)
            }}
          />
        )}
      </div>
    </ErrorBoundary>
  )
}