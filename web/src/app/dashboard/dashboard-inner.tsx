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
      {tabs.map((tab) => (\n        <button
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
    } catch (e: unknown) {\n      setPublishResult({ error: e instanceof Error ? e.message : 'Błąd połączenia' })
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
              ) : (\n                <div className="space-y-1">
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
      .replace(/[^\\w-]/g, '-').replace(/-+/g, '-')
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
    settings: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z',
    portals: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10',
    profiles: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
    calendar: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
    zap: 'M13 10V3L4 14h7v7l9-11h-7z',
  }

  return (
    <Link
      href={href}
      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
        active
          ? 'bg-violet-600/20 text-violet-400 font-medium'
          : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
      }`}
    >
      {icon && iconPath[icon] && (
        <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d={iconPath[icon]} />
        </svg>
      )}
      <span>{label}</span>
    </Link>
  )
}

function SchemaViewTab({ schema }: { schema: SchemaData | null }) {
  if (!schema) return null
  const fields = [
    { label: 'Focus Keyphrase', value: schema.focus_keyphrase, badge: 'SEO' },
    { label: 'Tytuł posta', value: schema.post_title },
    { label: 'Meta Description', value: schema.meta_description },
    { label: 'Slug WordPress', value: schema.wp_slug },
    { label: 'Lead artykułu', value: schema.lead },
  ].filter(f => f.value)

  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <div key={f.label} className="bg-gray-800/40 border border-gray-700/40 rounded-xl p-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-medium text-gray-400">{f.label}</span>
            {f.badge && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20">
                {f.badge}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-100 font-medium">{f.value}</p>
        </div>
      ))}
      <ResultSection
        title="Pełny JSON-LD Schema"
        copyText={schemaToScriptTag(schema)}
        copyId="full_schema"
        copiedKey={null}
        onCopy={() => navigator.clipboard.writeText(schemaToScriptTag(schema))}
        badge="JSON-LD"
      >
        <pre className="text-xs font-mono bg-gray-950/80 p-3 rounded-lg overflow-x-auto text-emerald-400 max-h-60 overflow-y-auto">
          {schemaToScriptTag(schema)}
        </pre>
      </ResultSection>
    </div>
  )
}

function ArticleTab({ schema, faq }: { schema: SchemaData | null; faq: FaqItem[] }) {
  if (!schema) return null
  return (
    <div className="space-y-4">
      {schema.post_title && (
        <div className="bg-gray-800/40 border border-gray-700/40 rounded-xl p-4">
          <span className="text-xs text-gray-500 block mb-1">Tytuł artykułu</span>
          <h2 className="text-lg font-bold text-white">{schema.post_title}</h2>
        </div>
      )}
      {schema.lead && (
        <div className="bg-violet-950/20 border border-violet-800/30 rounded-xl p-4">
          <span className="text-xs text-violet-400 font-medium block mb-1">Lead</span>
          <p className="text-sm text-gray-200 leading-relaxed italic">{schema.lead}</p>
        </div>
      )}
      {schema.article_body && (
        <div className="bg-gray-800/40 border border-gray-700/40 rounded-xl p-4">
          <span className="text-xs text-gray-500 block mb-2">Treść</span>
          <div className="text-sm text-gray-300 leading-relaxed space-y-3 whitespace-pre-line">
            {schema.article_body}
          </div>
        </div>
      )}
      {faq.length > 0 && (
        <div className="bg-gray-800/40 border border-gray-700/40 rounded-xl p-4">
          <span className="text-xs text-gray-500 block mb-3 font-medium">FAQ ({faq.length})</span>
          <div className="space-y-3">
            {faq.map((item, idx) => (
              <div key={idx} className="border-l-2 border-violet-500/40 pl-3 py-0.5">
                <p className="text-xs font-semibold text-gray-200">{item.question}</p>
                <p className="text-xs text-gray-400 mt-1">{item.answer}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ChaptersTab({ chapters }: { chapters: ChapterItem[] }) {
  if (chapters.length === 0) {
    return <p className="text-sm text-gray-500 italic">Brak wykrytych rozdziałów.</p>
  }
  return (
    <div className="space-y-2">
      {chapters.map((c, idx) => (
        <div
          key={idx}
          className="flex items-center justify-between p-3 bg-gray-800/30 border border-gray-700/30 rounded-xl hover:border-gray-600 transition-colors"
        >
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-md border border-violet-500/20">
              {secToTimestamp(c.startOffset ?? c.time)}
            </span>
            <span className="text-sm text-gray-200 font-medium">
              {c.name ?? c.label ?? '(bez tytułu)'}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

function YoutubeTab({
  schema,
  videoUrl,
  copiedKey,
  onCopy,
}: {
  schema: SchemaData | null
  videoUrl: string
  copiedKey: CopiedKey
  onCopy: (text: string, id: string) => void
}) {
  if (!schema) return null
  const ytText = buildYtDescription(schema, schema.wp_article_url ?? schema.published_url ?? schema.wp_url)

  return (
    <div className="space-y-4">
      <ResultSection
        title="Gotowy opis do YouTube"
        copyText={ytText}
        copyId="yt_desc"
        copiedKey={copiedKey}
        onCopy={onCopy}
        badge="Wideo SEO"
      >
        <pre className="text-xs font-mono bg-gray-950/80 p-4 rounded-lg overflow-x-auto text-gray-300 whitespace-pre-wrap max-h-96 overflow-y-auto leading-relaxed">
          {ytText || '(brak treści do wyświetlenia)'}
        </pre>
      </ResultSection>
    </div>
  )
}

function ShortsTab({ videoUrl }: { videoUrl: string }) {
  const vidId = extractVideoId(videoUrl)
  return (
    <div className="space-y-4">
      <div className="bg-gradient-to-r from-violet-900/30 to-fuchsia-900/20 border border-violet-700/40 rounded-xl p-5">
        <div className="flex items-center gap-3 mb-3">
          <span className="text-2xl">✂️</span>
          <div>
            <h3 className="text-base font-semibold text-white">ShortMachine — Moduł Shorts</h3>
            <p className="text-xs text-gray-400">Wyodrębnij najlepsze fragmenty do formatu 9:16 (TikTok, Reels, Shorts)</p>
          </div>
        </div>
        <p className="text-sm text-gray-300 leading-relaxed mb-4">
          Automatyczny montaż, kadrowanie wertykalne z detekcją twarzy oraz generowanie napisów.
        </p>
        <Link
          href={`/shortmachine${vidId ? `?video_id=${vidId}` : ''}`}
          className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity shadow-lg shadow-violet-900/20"
        >
          Otwórz edytor Shorts →
        </Link>
      </div>
    </div>
  )
}

// ─── Main DashboardInner ───────────────────────────────────────────────────

export default function DashboardInner() {
  const { data: session, status } = useSession()
  const router = useRouter()

  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<GenerateResponse | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('schema')
  const [copiedKey, setCopiedKey] = useState<CopiedKey>(null)
  const [showInjectModal, setShowInjectModal] = useState(false)
  const [showAddPortalModal, setShowAddPortalModal] = useState(false)
  const [showYtPublishModal, setShowYtPublishModal] = useState(false)
  const [selectedPortalId, setSelectedPortalId] = useState<string>('')
  const [ytChannels, setYtChannels] = useState<any[]>([])

  const { portals, loading: portalsLoading } = usePortals()
  const { userProfile, loading: profileLoading } = useProfiles()

  const {
    jobId,
    jobStatus,
    progress,
    step,
    error: jobError,
    startJob,
    cancelJob,
    reset: resetJobLoader,
  } = useJobLoader()

  const accessToken = (session as any)?.accessToken

  const fetchYtChannels = useCallback(async () => {
    if (!accessToken) return
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const res = await fetch(`${apiUrl}/v1/youtube/channels`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      })
      if (res.ok) {
        const data = await res.json()
        setYtChannels(data.channels || [])
      }
    } catch {
      // silent
    }
  }, [accessToken])

  useEffect(() => {
    if (accessToken) {
      fetchYtChannels()
    }
  }, [accessToken, fetchYtChannels])

  useEffect(() => {
    if (portals.length > 0 && !selectedPortalId) {
      setSelectedPortalId(portals[0].id)
    }
  }, [portals, selectedPortalId])

  const handleCopy = useCallback((text: string, id: string) => {
    navigator.clipboard.writeText(text)
    setCopiedKey(id)
    setTimeout(() => setCopiedKey(null), 2000)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const res = await fetch(`${apiUrl}/v1/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken && { Authorization: `Bearer ${accessToken}` }),
        },
        body: JSON.stringify({ video_url: url.trim() }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || data.error || `HTTP ${res.status}`)
      }

      if (data.status === 'processing' && data.job_id) {
        startJob(data.job_id, (completedData) => {
          setResult(completedData)
          setLoading(false)
        })
      } else {
        setResult(data)
        setLoading(false)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Wystąpił błąd podczas generowania.')
      setLoading(false)
    }
  }

  const schema = result?.schema_data ?? null
  const chapters = extractChapters(schema)
  const faq = extractFaq(schema)
  const selectedPortal = portals.find(p => p.id === selectedPortalId)

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gray-950 text-gray-100 flex">
        {/* Sidebar */}
        <aside className="w-64 border-r border-gray-800 bg-gray-900/50 flex flex-col justify-between p-4 shrink-0">
          <div>
            <div className="flex items-center gap-2.5 px-3 py-4 mb-6">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-violet-600 to-fuchsia-600 flex items-center justify-center font-bold text-white text-sm shadow-lg shadow-violet-900/30">
                V
              </div>
              <div>
                <h1 className="font-bold text-sm bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
                  Video SEO Engine
                </h1>
                <span className="text-[10px] text-gray-500 font-mono">v1.0.0</span>
              </div>
            </div>

            <nav className="space-y-1">
              <NavItem icon="grid" label="Generator SEO" href="/dashboard" active />
              <NavItem icon="clock" label="Historia zadań" href="/historia" />
              <NavItem icon="calendar" label="Kalendarz wpisów" href="/kalendarz" />
              <NavItem icon="portals" label="Portale WordPress" href="/portale" />
              <NavItem icon="profiles" label="Profile treści" href="/profile" />
              <NavItem icon="zap" label="ShortMachine" href="/shortmachine" />
              <NavItem icon="settings" label="Ustawienia" href="/ustawienia" />
            </nav>
          </div>

          <div className="space-y-3">
            {/* User profile widget */}
            {userProfile && (
              <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-violet-400 uppercase tracking-wider">
                    {userProfile.plan.display_name}
                  </span>
                  <span className="text-[10px] text-gray-400">
                    {userProfile.usage.used_this_month} / {userProfile.usage.quota}
                  </span>
                </div>
                <div className="w-full h-1.5 bg-gray-700 rounded-full overflow-hidden mb-2">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      userProfile.usage.percent > 90 ? 'bg-red-500' : 'bg-violet-500'
                    }`}
                    style={{ width: `${Math.min(userProfile.usage.percent, 100)}%` }}
                  />
                </div>
                <ManageSubscriptionLink accessToken={accessToken} />
              </div>
            )}

            <div className="pt-2 border-t border-gray-800 flex items-center justify-between px-2">
              <span className="text-xs text-gray-400 truncate max-w-[140px]">
                {session?.user?.email ?? ''}
              </span>
              <button
                onClick={() => signOut({ callbackUrl: '/login' })}
                className="text-xs text-gray-500 hover:text-red-400 transition-colors"
              >
                Wyloguj
              </button>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 flex flex-col min-w-0">
          <EmailVerificationBanner isVerified={userProfile?.is_verified ?? true} />

          <div className="p-8 max-w-5xl mx-auto w-full space-y-8">
            {/* Header */}
            <div>
              <h2 className="text-2xl font-bold text-white tracking-tight">Generator Video SEO</h2>
              <p className="text-sm text-gray-400 mt-1">
                Wklej link do YouTube, aby wygenerować zoptymalizowane pod SEO artykuły, znaczniki Schema.org, rozdziały oraz opisy.
              </p>
            </div>

            {/* Input Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="flex gap-3">
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=..."
                  required
                  className="flex-1 bg-gray-900 border border-gray-800 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="px-6 py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-xl font-semibold text-sm text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2 shadow-lg shadow-violet-900/20"
                >
                  {loading ? (
                    <><span className="animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> Przetwarzanie...</>
                  ) : (
                    <>✨ Generuj</>
                  )}
                </button>
              </div>

              {/* Portal selection */}
              <div className="flex items-center gap-3 text-xs text-gray-400">
                <span>Domyślny portal:</span>
                <select
                  value={selectedPortalId}
                  onChange={(e) => {
                    if (e.target.value === '__add__') {
                      setShowAddPortalModal(true)
                    } else {
                      setSelectedPortalId(e.target.value)
                    }
                  }}
                  className="bg-gray-900 border border-gray-800 rounded-lg px-2.5 py-1 text-xs text-gray-300 focus:outline-none focus:border-violet-500 cursor-pointer"
                >
                  {portals.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                  <option value="__manual__">Ręczne wpisanie danych</option>
                  <option value="__add__">+ Dodaj nowy portal</option>
                </select>
              </div>
            </form>

            {/* Error state */}
            {error && (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center justify-between">
                <span>⚠️ {error}</span>
                <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 text-xs underline">Zamknij</button>
              </div>
            )}

            {/* Results */}
            {schema && (
              <div className="space-y-6 animate-in fade-in-50 duration-300">
                {/* Action Bar */}
                <div className="flex items-center justify-between bg-gray-900/60 border border-gray-800 p-4 rounded-xl">
                  <div>
                    <h3 className="font-semibold text-white text-sm">Wyniki analizy SEO</h3>
                    <p className="text-xs text-gray-400">
                      Czas przetwarzania: {result?.processing_time_s ? `${result.processing_time_s.toFixed(1)}s` : 'b/d'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowYtPublishModal(true)}
                      className="px-3.5 py-2 bg-red-600/20 text-red-400 border border-red-500/30 rounded-lg text-xs font-medium hover:bg-red-600/30 transition-colors flex items-center gap-1.5"
                    >
                      <span>📺</span> Publikuj na YouTube
                    </button>
                    <button
                      onClick={() => setShowInjectModal(true)}
                      className="px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-xs font-medium hover:opacity-90 transition-opacity flex items-center gap-1.5 shadow-md shadow-violet-900/20"
                    >
                      <span>🚀</span> Publikuj na WordPress
                    </button>
                  </div>
                </div>

                {/* Tabs */}
                <TabBar
                  active={activeTab}
                  onChange={setActiveTab}
                  chaptersCount={chapters.length}
                  faqCount={faq.length}
                />

                {/* Tab content */}
                <div>
                  {activeTab === 'schema' && <SchemaViewTab schema={schema} />}
                  {activeTab === 'article' && <ArticleTab schema={schema} faq={faq} />}
                  {activeTab === 'chapters' && <ChaptersTab chapters={chapters} />}
                  {activeTab === 'youtube' && (
                    <YoutubeTab
                      schema={schema}
                      videoUrl={url}
                      copiedKey={copiedKey}
                      onCopy={handleCopy}
                    />
                  )}
                  {activeTab === 'shorts' && <ShortsTab videoUrl={url} />}
                </div>
              </div>
            )}
          </div>
        </main>

        {/* Modals */}
        {showInjectModal && schema && (
          <InjectModal
            schemaData={schema}
            videoUrl={url}
            selectedPortalId={selectedPortalId}
            portalName={selectedPortal?.name}
            portalUrl={selectedPortal?.url}
            accessToken={accessToken}
            onClose={() => setShowInjectModal(false)}
            ytChannels={ytChannels}
          />
        )}

        {showYtPublishModal && schema && (
          <YouTubePublishModal
            videoId={extractVideoId(url)}
            schema={schema}
            isOpen={showYtPublishModal}
            onClose={() => setShowYtPublishModal(false)}
            channels={ytChannels}
            accessToken={accessToken || ""}
            apiUrl={process.env.NEXT_PUBLIC_API_URL || ''}
          />
        )}

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
