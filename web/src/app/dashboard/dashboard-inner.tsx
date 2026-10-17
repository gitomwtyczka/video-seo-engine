'use client'

/**
 * CO: Dashboard — główny widok aplikacji po zalogowaniu
 * PO CO: Daje użytkownikowi dwie ścieżki:
 *   A (Free/Starter) — generuje SEO i pokazuje gotowe snippety HTML do skopiowania
 *   B (Pro/Agency)   — dodatkowo umożliwia automatyczną publikację na WordPress
 * JAK: Wywołuje POST /v1/generate lub POST /v1/audio/generate → schema_data → renderuje zakładki wynikowe
 *      (Schemat, Artykuł, Rozdziały, Opis YouTube, ShortMachine). Dla planu pro/agency InjectModal → POST /v1/inject.
 */

import { useSession, signOut } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect, useState, useCallback, useRef } from 'react'
import Link from 'next/link'
import { apiGet, apiPost, apiPostForm } from '../lib/api-client'
import { useJobLoader } from './use-job-loader'
import { usePortals, type Portal } from './use-portals'
import { useProfiles, type Profile } from './use-profiles'
import EmailVerificationBanner from './email-verification-banner'
import { ErrorBoundary } from './error-boundary'
import { YouTubePublishModal } from './YouTubePublishModal'

import {
  VSE_LANGUAGES,
  type GenerateResponse,
  type SchemaData,
  type ChapterItem,
  type FaqItem,
  type QuoteItem,
  type UserPlan,
  type UserProfile,
  type InjectResult,
  type CopiedKey,
  type TabKey,
} from './types'
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

// ─── Subcomponents (wydzielone do ./components) ──────────────────────────────────
import {
  CopyButton,
  ResultSection,
  TabBar,
  ManageSubscriptionLink,
  NavItem,
  WpQuickPanel,
  InjectModal,
  AddPortalModal,
  SchemaTab,
  ArticleTab,
  ChaptersTab,
  YouTubeTab,
  ShortMachineTab,
} from './components'


// ─── Main Component ─────────────────────────────────────────────────────────

export default function DashboardInner() {
  const { data: session, status } = useSession()
  const router = useRouter()

  const [inputMode, setInputMode] = useState<'url' | 'audio'>('url')
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{
    raw: SchemaData
    videoId: string
    time?: number
    inputUrl: string
    sourceLang?: string
    targetLang?: string
  } | null>(null)
  const [error, setError] = useState('')
  const [copiedKey, setCopiedKey] = useState<CopiedKey>(null)
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('article')

  // Multi-Language & Cross-Language Engine ("Złoty Środek") state
  const [uiLang, setUiLang] = useState<string>('pl')
  const [targetLang, setTargetLang] = useState<string>('pl')
  const [materialTranslations, setMaterialTranslations] = useState<Record<string, Record<string, SchemaData>>>({})
  const [activeTabLang, setActiveTabLang] = useState<Record<string, string>>({})
  const [adaptingLang, setAdaptingLang] = useState<string | null>(null)
  const [adaptError, setAdaptError] = useState<string>('')
  const [showMultilangUpsell, setShowMultilangUpsell] = useState<boolean>(false)
  const [addonCheckoutLoading, setAddonCheckoutLoading] = useState<boolean>(false)

  const [showInjectModal, setShowInjectModal] = useState(false)
  const [ytModalOpen, setYtModalOpen] = useState(false)
  const [ytChannels, setYtChannels] = useState<any[]>([])
  const [ytDescription, setYtDescription] = useState<string>('')

  // Load saved UI language from localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return
    const saved = window.localStorage.getItem('vse_ui_lang')
    if (saved && VSE_LANGUAGES.some((l) => l.code === saved)) {
      setUiLang(saved)
      setTargetLang(saved)
    }
  }, [])

  useEffect(() => {
    apiGet<any[]>('/v1/youtube/channels')
      .then((data) => setYtChannels(Array.isArray(data) ? data : []))
      .catch(() => setYtChannels([]))
  }, [])


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
  const [publicationType, setPublicationType] = useState<string>('full_analysis')
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
      const sData = jobData.schema_data as SchemaData
      const initTarget = (sData.target_lang as string) || 'pl'
      const initSource = (sData.source_lang as string) || 'pl'
      setResult({
        raw: sData,
        videoId,
        inputUrl: jobData.video_url,
        sourceLang: initSource,
        targetLang: initTarget,
      })
      setMaterialTranslations({
        article: { [initTarget]: sData },
        youtube: { [initTarget]: sData },
        chapters: { [initTarget]: sData },
        schema: { [initTarget]: sData },
      })
      setActiveTabLang({
        article: initTarget,
        youtube: initTarget,
        chapters: initTarget,
        schema: initTarget,
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
      try {
        const data = await apiGet<UserProfile>('/v1/users/me')
        setUserProfile(data)
      } catch {
        // silent
      }
    }
    fetchProfile()
  }, [])

  const isPro =
    (userProfile != null && ['pro', 'agency'].includes(userProfile.plan.id)) ||
    (userProfile == null && ['pro', 'agency'].includes((session?.user as any)?.plan ?? ''))

  const hasMultilangAddon =
    isPro ||
    Boolean(userProfile?.is_admin) ||
    Boolean(userProfile?.has_multilang_addon) ||
    Boolean(userProfile?.multilang?.has_multilang_addon)

  const canOverrideTargetLang =
    hasMultilangAddon || Boolean(userProfile?.multilang?.allow_target_override)

  const canAdaptPerMaterial =
    hasMultilangAddon || Boolean(userProfile?.multilang?.allow_per_material_adapt)

  const handleUiLangChange = (newLang: string) => {
    setUiLang(newLang)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('vse_ui_lang', newLang)
    }
    if (!canOverrideTargetLang) {
      setTargetLang(newLang)
    }
  }

  const handleBuyMultilangAddon = async () => {
    setAddonCheckoutLoading(true)
    try {
      const res = await apiPost<{ session_url?: string; checkout_url?: string }>(
        '/v1/payments/checkout-addon',
        { addon: 'multilang' }
      )
      const redirectUrl = res?.session_url || res?.checkout_url
      if (redirectUrl) {
        window.location.href = redirectUrl
      }
    } catch (err: unknown) {
      setAdaptError(err instanceof Error ? err.message : 'Nie udało się utworzyć sesji płatności Stripe')
    } finally {
      setAddonCheckoutLoading(false)
    }
  }

  const handleAdaptMaterial = async (tab: TabKey, langCode: string) => {
    if (!result?.raw) return
    setAdaptError('')

    if (!canAdaptPerMaterial) {
      setShowMultilangUpsell(true)
      return
    }

    // Instant cache hit (0ms)
    const cached = materialTranslations[tab]?.[langCode]
    if (cached) {
      setActiveTabLang((prev) => ({ ...prev, [tab]: langCode }))
      return
    }

    const materialTypeMap: Record<string, string> = {
      article: 'article',
      youtube: 'youtube',
      chapters: 'youtube',
      schema: 'schema',
    }
    const materialType = materialTypeMap[tab] || 'article'

    setAdaptingLang(langCode)
    try {
      const resp = await apiPost<{
        status: string
        material_type: string
        target_lang: string
        adapted_data: Record<string, unknown>
      }>('/v1/adapt-material', {
        material_type: materialType,
        target_lang: langCode,
        source_data: result.raw,
        youtube_id: result.videoId,
      })

      if (resp?.adapted_data) {
        const mergedSchema: SchemaData = {
          ...result.raw,
          ...resp.adapted_data,
          target_lang: langCode,
        }
        setMaterialTranslations((prev) => {
          const next = { ...prev }
          next[tab] = { ...(next[tab] || {}), [langCode]: mergedSchema }
          if (tab === 'youtube' || tab === 'chapters') {
            next.youtube = { ...(next.youtube || {}), [langCode]: mergedSchema }
            next.chapters = { ...(next.chapters || {}), [langCode]: mergedSchema }
          }
          return next
        })
        setActiveTabLang((prev) => ({
          ...prev,
          [tab]: langCode,
          ...(tab === 'youtube' || tab === 'chapters' ? { youtube: langCode, chapters: langCode } : {}),
        }))
      }
    } catch (err: unknown) {
      setAdaptError(err instanceof Error ? err.message : 'Błąd tłumaczenia materiału')
    } finally {
      setAdaptingLang(null)
    }
  }

  const handleCopy = useCallback(async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedKey(id)
      setTimeout(() => setCopiedKey(null), 2000)
    } catch {
      // silent
    }
  }, [])

  const currentTabLang = activeTabLang[activeTab] || result?.targetLang || (result?.raw?.target_lang as string) || targetLang || 'pl'
  const activeSchema: SchemaData | null =
    (result && materialTranslations[activeTab]?.[currentTabLang]) || result?.raw || null

  useEffect(() => {
    if (activeSchema) {
      const wpLink = activeSchema?.wp_url as string | undefined
      setYtDescription(buildYtDescription(activeSchema, wpLink))
    }
  }, [activeSchema])

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (inputMode === 'url' && !url.trim()) return
    if (inputMode === 'audio' && !audioFile) return

    setLoading(true)
    setError('')
    setAdaptError('')
    setShowMultilangUpsell(false)
    setResult(null)

    const effectiveTargetLang = canOverrideTargetLang ? targetLang : uiLang

    try {
      let data: GenerateResponse | null = null
      const portalIdParam =
        selectedPortalId === '__manual__' || selectedPortalId === '__add__' || !selectedPortalId
          ? undefined
          : selectedPortalId.trim()

      if (inputMode === 'audio' && audioFile) {
        const formData = new FormData()
        formData.append('file', audioFile)
        formData.append('publication_type', publicationType)
        if (portalIdParam) {
          formData.append('portal_id', portalIdParam)
        }
        formData.append('lang', effectiveTargetLang)
        formData.append('target_lang', effectiveTargetLang)
        formData.append('ui_lang', uiLang)
        formData.append('llm_provider', 'claude')

        data = await apiPostForm<GenerateResponse>('/v1/audio/generate', formData)
      } else {
        data = await apiPost<GenerateResponse>('/v1/generate', {
          video_url: url.trim(),
          llm_provider: 'claude',
          lang: effectiveTargetLang,
          target_lang: effectiveTargetLang,
          ui_lang: uiLang,
          publication_type: publicationType,
          portal_id: portalIdParam,
        })
      }

      if (!data) throw new Error('Pusta odpowiedź serwera')
      if (data.error) throw new Error(data.error)

      const schema = data.schema_data ?? null
      if (!schema) throw new Error('Serwer nie zwrócił schema_data')

      const detectedSourceLang = (data.source_lang || schema.source_lang || 'pl') as string
      const detectedTargetLang = (data.target_lang || schema.target_lang || effectiveTargetLang) as string
      const effectiveInputUrl = inputMode === 'audio' ? `audio://${data.video_id}` : url.trim()

      setResult({
        raw: schema,
        videoId: data.video_id,
        time: data.processing_time_s,
        inputUrl: effectiveInputUrl,
        sourceLang: detectedSourceLang,
        targetLang: detectedTargetLang,
      })
      setMaterialTranslations({
        article: { [detectedTargetLang]: schema },
        youtube: { [detectedTargetLang]: schema },
        chapters: { [detectedTargetLang]: schema },
        schema: { [detectedTargetLang]: schema },
      })
      setActiveTabLang({
        article: detectedTargetLang,
        youtube: detectedTargetLang,
        chapters: detectedTargetLang,
        schema: detectedTargetLang,
      })
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

  const schema = activeSchema
  const chapters = extractChapters(schema)
  const faq = extractFaq(schema)
  const planLabel = userProfile?.plan?.display_name ?? 'Free'
  const usageUsed = userProfile?.usage?.used_this_month ?? 0
  const usageQuota = userProfile?.usage?.quota ?? 5

  const sourceLangMeta = VSE_LANGUAGES.find((l) => l.code === (result?.sourceLang || result?.raw?.source_lang || 'pl'))
  const targetLangMeta = VSE_LANGUAGES.find((l) => l.code === currentTabLang) || VSE_LANGUAGES[0]

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gray-950 text-white">
        {/* Sidebar */}
        <aside className="fixed left-0 top-0 h-full w-64 bg-gray-900 border-r border-gray-800 flex flex-col z-20">
          <div className="p-6 border-b border-gray-800">
            <div className="flex items-center justify-between gap-2">
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

              {/* Compact UI Language Switcher (🌐 PL ▾) */}
              <div title="Język interfejsu i domyślny język generowania">
                <select
                  aria-label="Język panelu"
                  value={uiLang}
                  onChange={(e) => handleUiLangChange(e.target.value)}
                  className="bg-gray-800 border border-gray-700 hover:border-violet-500 text-xs font-semibold text-gray-200 rounded-lg px-2 py-1.5 cursor-pointer focus:outline-none focus:border-violet-500"
                >
                  {VSE_LANGUAGES.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.flag} {l.short}
                    </option>
                  ))}
                </select>
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
                <div className="flex items-center gap-1.5">
                  <p className="text-xs text-violet-400">{planLabel}</p>
                  {hasMultilangAddon && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                      🌐 8 języków
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-1 mb-3">
              <a
                href="/cennik"
                className="text-xs text-gray-400 hover:text-violet-300 transition-colors py-0.5"
              >
                ↑ Zmień plan
              </a>
              {!hasMultilangAddon && (
                <button
                  type="button"
                  onClick={handleBuyMultilangAddon}
                  disabled={addonCheckoutLoading}
                  className="text-left text-xs text-emerald-400 hover:text-emerald-300 transition-colors py-0.5"
                >
                  🌐 + Pakiet Wielojęzyczny (29 zł)
                </button>
              )}
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

            <div className="flex items-start justify-between gap-4 mb-1">
              <h1 className="text-2xl font-bold text-white">Video & Audio SEO Engine</h1>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-xs text-violet-300">
                🌐 Cross-Language Engine (8 języków)
              </span>
            </div>
            <p className="text-gray-400 mb-8">
              Wklej link YouTube (w dowolnym języku!) lub wgraj plik MP3 — AI wygeneruje kompletny pakiet SEO, rozdziały i artykuł w wybranym języku.
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

            {/* Portal, Publication Type & Target Language Selector */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
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
                  <option value="news">📰 News</option>
                  <option value="explainer">💡 Explainer</option>
                  <option value="wywiad">🎤 Wywiad</option>
                  <option value="poradnik">📋 Poradnik</option>
                  <option value="felieton">✍️ Felieton</option>
                  <option value="reportaz">📸 Reportaż</option>
                  <option value="watching_page">🎬 Strona z filmem</option>
                  <option value="discover">🔍 Discover</option>
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs text-gray-400">Język wyniku SEO</label>
                  {!canOverrideTargetLang && (
                    <button
                      type="button"
                      onClick={() => setShowMultilangUpsell(true)}
                      className="text-[11px] text-emerald-400 hover:text-emerald-300 font-medium"
                    >
                      🔒 Odblokuj 8 języków
                    </button>
                  )}
                </div>
                <select
                  id="target-lang-selector"
                  value={canOverrideTargetLang ? targetLang : uiLang}
                  onChange={(e) => {
                    const nextLang = e.target.value
                    if (!canOverrideTargetLang && nextLang !== uiLang) {
                      setShowMultilangUpsell(true)
                      return
                    }
                    setTargetLang(nextLang)
                  }}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer"
                  style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3E%3Cpath stroke=\'%236b7280\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.5rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }}
                >
                  {VSE_LANGUAGES.map((l) => {
                    const locked = !canOverrideTargetLang && l.code !== uiLang
                    return (
                      <option key={l.code} value={l.code}>
                        {l.flag} {l.label} ({l.short}){locked ? ' 🔒 (Pakiet Wielojęzyczny / Pro)' : ''}
                      </option>
                    )
                  })}
                </select>
              </div>
            </div>

            {/* Upsell Banner for Multi-Language Add-on (+29 PLN/mo) or Pro */}
            {showMultilangUpsell && !hasMultilangAddon && (
              <div className="mb-5 p-4 bg-gradient-to-r from-violet-950/70 via-gray-900 to-emerald-950/50 border border-violet-500/40 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-white">🌐 Pakiet Wielojęzyczny — publikuj na rynki zagraniczne</span>
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      +29 zł / mies.
                    </span>
                  </div>
                  <p className="text-xs text-gray-300 leading-relaxed">
                    W Twoim obecnym planie możesz wklejać filmy w dowolnym języku i generować SEO w języku panelu ({uiLang.toUpperCase()}).
                    Aby dowolnie zmieniać język docelowy przed generowaniem oraz tłumaczyć pojedyncze zakładki (Artykuł, YouTube, Rozdziały, Schema) 1 kliknięciem na 8 języków:
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2 flex-shrink-0">
                  <button
                    type="button"
                    onClick={handleBuyMultilangAddon}
                    disabled={addonCheckoutLoading}
                    className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white rounded-lg transition-colors whitespace-nowrap"
                  >
                    {addonCheckoutLoading ? 'Przekierowanie...' : '🌐 Dokup Pakiet (+29 zł/mies.)'}
                  </button>
                  <Link
                    href="/cennik"
                    className="px-3.5 py-2 bg-violet-600 hover:bg-violet-500 text-xs font-semibold text-white rounded-lg transition-colors whitespace-nowrap"
                  >
                    🚀 Przejdź na Pro (149 zł — w cenie!)
                  </Link>
                  <button
                    type="button"
                    onClick={() => setShowMultilangUpsell(false)}
                    className="text-xs text-gray-400 hover:text-white px-2 py-1"
                  >
                    ✕
                  </button>
                </div>
              </div>
            )}

            {/* Input Mode Selector */}
            <div className="flex gap-2 mb-3">
              <button
                type="button"
                onClick={() => { setInputMode('url'); setError('') }}
                className={`px-4 py-2 text-xs font-semibold rounded-xl border transition-all flex items-center gap-1.5 ${
                  inputMode === 'url'
                    ? 'bg-violet-600/20 text-violet-300 border-violet-500/50 shadow-sm'
                    : 'bg-gray-900 text-gray-400 border-gray-800 hover:text-gray-200'
                }`}
              >
                🎬 YouTube URL
              </button>
              <button
                type="button"
                onClick={() => { setInputMode('audio'); setError('') }}
                className={`px-4 py-2 text-xs font-semibold rounded-xl border transition-all flex items-center gap-1.5 ${
                  inputMode === 'audio'
                    ? 'bg-violet-600/20 text-violet-300 border-violet-500/50 shadow-sm'
                    : 'bg-gray-900 text-gray-400 border-gray-800 hover:text-gray-200'
                }`}
              >
                🎤 Plik MP3 / Audio
              </button>
            </div>

            {/* URL / Audio Form */}
            <form onSubmit={handleGenerate} className="mb-8">
              <div className="flex gap-3">
                {inputMode === 'url' ? (
                  <input
                    id="youtube-url-input"
                    type="text"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://www.youtube.com/watch?v=... (polski lub zagraniczny film)"
                    className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
                  />
                ) : (
                  <div className="flex-1 flex items-center">
                    <label
                      onDragOver={(e) => {
                        e.preventDefault()
                        e.currentTarget.style.borderColor = '#a855f7'
                      }}
                      onDragLeave={(e) => {
                        e.currentTarget.style.borderColor = ''
                      }}
                      onDrop={(e) => {
                        e.preventDefault()
                        e.currentTarget.style.borderColor = ''
                        const file = e.dataTransfer.files?.[0]
                        if (file) setAudioFile(file)
                      }}
                      className="w-full flex items-center justify-between bg-gray-900 border border-dashed border-gray-700 hover:border-violet-500 rounded-xl px-4 py-3 cursor-pointer transition-colors group"
                    >
                      <div className="flex items-center gap-3 truncate">
                        <span className="text-xl">🎙️</span>
                        <div className="truncate">
                          <p className="text-sm text-white font-medium truncate">
                            {audioFile ? audioFile.name : 'Wybierz lub upuść plik audio (MP3, WAV, M4A)...'}
                          </p>
                          <p className="text-xs text-gray-500">
                            {audioFile ? `${(audioFile.size / (1024 * 1024)).toFixed(2)} MB` : 'Obsługiwane formaty: MP3, WAV, M4A, OGG, FLAC'}
                          </p>
                        </div>
                      </div>
                      <span className="text-xs bg-gray-800 group-hover:bg-violet-600 text-gray-300 group-hover:text-white px-3 py-1.5 rounded-lg transition-colors whitespace-nowrap ml-2">
                        {audioFile ? 'Zmień plik' : 'Wybierz plik'}
                      </span>
                      <input
                        type="file"
                        accept=".mp3,.wav,.m4a,.ogg,.aac,.flac,.wma,.mp4,audio/*"
                        className="hidden"
                        onChange={(e) => {
                          const f = e.target.files?.[0]
                          if (f) setAudioFile(f)
                        }}
                      />
                    </label>
                  </div>
                )}
                <button
                  id="generate-btn"
                  type="submit"
                  disabled={loading || (inputMode === 'url' ? !url.trim() : !audioFile)}
                  className="px-6 py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-xl font-semibold text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2 whitespace-nowrap"
                >
                  {loading ? (
                    <><span className="animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> {inputMode === 'audio' ? 'Transkrypcja i AI...' : 'Generuję...'}</>
                  ) : (
                    <>✦ Generuj SEO</>
                  )}
                </button>
              </div>

              {loading && (
                <div className="mt-3 flex items-center gap-2 text-sm text-gray-400">
                  <span className="animate-spin inline-block w-3 h-3 border border-gray-500 border-t-violet-400 rounded-full" />
                  {inputMode === 'audio'
                    ? 'Transkrypcja audio (faster-whisper) i generowanie schema... (~30-60s)'
                    : 'Pobieranie transkryptu i generowanie schema... (~50s)'}
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
                    { label: 'Materiały w tym miesiącu', value: `${usageUsed}/${usageQuota}`, sub: `Plan ${planLabel}` },
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
                <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
                  <div>
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <h2 className="text-lg font-semibold text-white">Wyniki SEO</h2>
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-violet-500/10 border border-violet-500/30 text-xs text-violet-300">
                        🌐 Źródło: {sourceLangMeta ? `${sourceLangMeta.flag} ${sourceLangMeta.short}` : (result.sourceLang || 'AUTO').toUpperCase()} → Wynik: {targetLangMeta.flag} {targetLangMeta.label} ({targetLangMeta.short})
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Źródło: <span className="font-mono">{result.videoId}</span>
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
                    {ytChannels.length > 0 && !result?.inputUrl?.startsWith('audio://') && !result?.videoId?.startsWith('audio_') && (
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

                {/* Per-Material Language Switcher Bar ("Złoty Środek") */}
                {activeTab !== 'shorts' && (
                  <div className="mb-4 p-3 bg-gray-900/90 border border-gray-800 rounded-xl">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-medium text-gray-400 flex items-center gap-1.5">
                        🌐 Język tego materiału:
                      </span>
                      <div className="flex flex-wrap items-center gap-1.5">
                        {VSE_LANGUAGES.map((l) => {
                          const isCurrent = currentTabLang === l.code
                          const isCached = Boolean(materialTranslations[activeTab]?.[l.code])
                          const isLocked = !canAdaptPerMaterial && !isCurrent
                          const isAdaptingThis = adaptingLang === l.code
                          return (
                            <button
                              key={l.code}
                              type="button"
                              disabled={Boolean(adaptingLang)}
                              onClick={() => handleAdaptMaterial(activeTab, l.code)}
                              className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all flex items-center gap-1 ${
                                isCurrent
                                  ? 'bg-violet-600 text-white border-violet-500 shadow-sm'
                                  : isCached
                                  ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/20'
                                  : 'bg-gray-800/80 text-gray-300 border-gray-700 hover:border-violet-500/50 hover:text-white'
                              }`}
                              title={
                                isLocked
                                  ? `Odblokuj tłumaczenie na ${l.label} (Pakiet Wielojęzyczny +29 zł lub plan Pro)`
                                  : `Przełącz / przetłumacz ten materiał na ${l.label}`
                              }
                            >
                              <span>{l.flag}</span>
                              <span>{l.short}</span>
                              {isAdaptingThis && (
                                <span className="animate-spin inline-block w-3 h-3 border border-white/40 border-t-white rounded-full ml-0.5" />
                              )}
                              {!isAdaptingThis && isCached && !isCurrent && (
                                <span className="text-[10px] text-emerald-400">✓</span>
                              )}
                              {isLocked && <span className="text-[10px] opacity-80">🔒</span>}
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    {adaptingLang && (
                      <div className="mt-2.5 flex items-center gap-2 text-xs text-violet-300">
                        <span className="animate-spin inline-block w-3 h-3 border border-violet-400/30 border-t-violet-400 rounded-full" />
                        Tłumaczenie i adaptacja SEO tej zakładki na język{' '}
                        <strong>{VSE_LANGUAGES.find((x) => x.code === adaptingLang)?.label}</strong>... (nie zużywa limitu wideo)
                      </div>
                    )}

                    {adaptError && (
                      <div className="mt-2.5 text-xs text-red-400">
                        ⚠️ {adaptError}
                      </div>
                    )}
                  </div>
                )}

                {/* Tab: Schemat */}
                {activeTab === 'schema' && (
                  <SchemaTab schema={schema} copiedKey={copiedKey} onCopy={handleCopy} />
                )}

                {/* Tab: Artykuł */}
                {activeTab === 'article' && (
                  <ArticleTab schema={schema} faq={faq} copiedKey={copiedKey} onCopy={handleCopy} />
                )}

                {/* Tab: Rozdziały */}
                {activeTab === 'chapters' && (
                  <ChaptersTab chapters={chapters} copiedKey={copiedKey} onCopy={handleCopy} />
                )}

                {/* Tab: Opis YouTube */}
                {activeTab === 'youtube' && (
                  <YouTubeTab ytDescription={ytDescription} copiedKey={copiedKey} onCopy={handleCopy} />
                )}

                {/* Tab: ShortMachine */}
                {activeTab === 'shorts' && (
                  <ShortMachineTab
                    ytChannels={ytChannels}
                    initialYoutubeId={result?.videoId || extractVideoId(url) || extractVideoId(result?.inputUrl || '')}
                    accessToken={accessToken}
                    session={session}
                    source={(result?.raw?.source as string) || (result?.inputUrl?.startsWith('audio://') || result?.videoId?.startsWith('audio_') ? 'audio' : 'youtube')}
                    isAudio={result?.raw?.source === 'audio' || result?.inputUrl?.startsWith('audio://') || result?.videoId?.startsWith('audio_')}
                  />
                )}
              </div>
            )}
          </div>
        </main>

        {/* Inject Modal */}
        {showInjectModal && result && (() => {
          const selectedPortal = portals.find((p) => p.id === selectedPortalId)
          return (
            <InjectModal
              schemaData={activeSchema || result.raw}
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
          const wpUrl = (activeSchema || result.raw)?.wp_article_url || (activeSchema || result.raw)?.published_url || ""
          const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''

          return (
            <YouTubePublishModal
              overrideDescription={ytDescription}
              isOpen={ytModalOpen}
              onClose={() => setYtModalOpen(false)}
              videoId={result?.videoId || result?.raw?.video_id || extractVideoId(result?.inputUrl || "") || ""}
              schemaData={activeSchema ?? result.raw ?? {}}
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
