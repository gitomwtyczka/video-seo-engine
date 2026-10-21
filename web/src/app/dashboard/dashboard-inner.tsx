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
import { getTranslations } from '../i18n'

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
  const [adaptingAllLang, setAdaptingAllLang] = useState<string | null>(null)
  const [adaptError, setAdaptError] = useState<string>('')
  const [showMultilangUpsell, setShowMultilangUpsell] = useState<boolean>(false)
  const [addonCheckoutLoading, setAddonCheckoutLoading] = useState<boolean>(false)

  const [showInjectModal, setShowInjectModal] = useState(false)
  const [ytModalOpen, setYtModalOpen] = useState(false)
  const [ytChannels, setYtChannels] = useState<any[]>([])
  const [ytDescription, setYtDescription] = useState<string>('')

  const buildTranslationsState = useCallback((sData: SchemaData, baseLang: string) => {
    const initial: Record<string, Record<string, SchemaData>> = {
      article: { [baseLang]: sData },
      youtube: { [baseLang]: sData },
      chapters: { [baseLang]: sData },
      schema: { [baseLang]: sData },
    }
    const savedTranslations = (sData?.translations as Record<string, Record<string, Record<string, unknown>>>) || {}
    for (const [langCode, langDict] of Object.entries(savedTranslations)) {
      if (!langDict || typeof langDict !== 'object') continue
      for (const tab of ['article', 'youtube', 'chapters', 'schema']) {
        const mergedTabObj: Record<string, unknown> = {
          ...(langDict.all || {}),
          ...(tab === 'chapters' ? (langDict.youtube || {}) : {}),
          ...(tab === 'youtube' ? (langDict.chapters || {}) : {}),
          ...(langDict[tab] || {}),
        }
        if (Object.keys(mergedTabObj).length > 0) {
          initial[tab][langCode] = {
            ...sData,
            ...mergedTabObj,
            target_lang: langCode,
          }
        }
      }
    }
    return initial
  }, [])

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
      setMaterialTranslations(buildTranslationsState(sData, initTarget))
      setActiveTabLang({
        article: initTarget,
        youtube: initTarget,
        chapters: initTarget,
        schema: initTarget,
      })
      setUrl(jobData.video_url)
      setActiveTab('article')
    }
  }, [jobData, buildTranslationsState])

  useEffect(() => {
    if (status === 'unauthenticated') router.push('/login')
  }, [status, router])

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        if (typeof window !== 'undefined' && (window.location.search.includes('upgraded=1') || window.location.search.includes('payment=topup_success'))) {
          try {
            const sessionId = new URLSearchParams(window.location.search).get('session_id') || undefined
            await apiPost('/v1/payments/verify-session', { session_id: sessionId })
          } catch {
            // ignore
          }
        }
        const data = await apiGet<UserProfile>('/v1/users/me')
        setUserProfile(data)
      } catch {
        // silent
      }
    }
    fetchProfile()
  }, [])

  const userPlan = userProfile?.plan?.id ?? 'free'

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
    setTargetLang(newLang)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('vse_ui_lang', newLang)
      window.dispatchEvent(new CustomEvent('vse-lang-change', { detail: newLang }))
    }
  }

  const handleCheckoutPlan = async (planId: string) => {
    setAddonCheckoutLoading(true)
    try {
      const res = await apiPost<{ session_url?: string; checkout_url?: string }>(
        '/v1/payments/create-checkout-session',
        { plan_id: planId }
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

  const handleBuyMultilangAddon = async () => {
    await handleCheckoutPlan(userPlan === 'free' ? 'starter_multilang' : 'multilang_addon')
  }

  const getCurrentJobIdParam = () => {
    if (jobId) return jobId
    if (typeof window !== 'undefined') {
      return new URLSearchParams(window.location.search).get('job_id') || undefined
    }
    return undefined
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
      setActiveTabLang((prev) => ({
        ...prev,
        [tab]: langCode,
        ...(tab === 'youtube' || tab === 'chapters' ? { youtube: langCode, chapters: langCode } : {}),
      }))
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
        job_id: getCurrentJobIdParam(),
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

  const handleAdaptAllMaterials = async (langCode: string) => {
    if (!result?.raw) return
    setAdaptError('')

    if (!canAdaptPerMaterial) {
      setShowMultilangUpsell(true)
      return
    }

    const allTabsCached = ['article', 'youtube', 'chapters', 'schema'].every(
      (tKey) => Boolean(materialTranslations[tKey]?.[langCode])
    )
    if (allTabsCached) {
      setActiveTabLang({
        article: langCode,
        youtube: langCode,
        chapters: langCode,
        schema: langCode,
      })
      return
    }

    setAdaptingAllLang(langCode)
    setAdaptingLang(langCode)
    try {
      const resp = await apiPost<{
        status: string
        material_type: string
        target_lang: string
        adapted_data: Record<string, unknown>
      }>('/v1/adapt-material', {
        material_type: 'all',
        target_lang: langCode,
        source_data: result.raw,
        youtube_id: result.videoId,
        job_id: getCurrentJobIdParam(),
      })

      if (resp?.adapted_data) {
        const mergedSchema: SchemaData = {
          ...result.raw,
          ...resp.adapted_data,
          target_lang: langCode,
        }
        setMaterialTranslations((prev) => ({
          ...prev,
          article: { ...(prev.article || {}), [langCode]: mergedSchema },
          youtube: { ...(prev.youtube || {}), [langCode]: mergedSchema },
          chapters: { ...(prev.chapters || {}), [langCode]: mergedSchema },
          schema: { ...(prev.schema || {}), [langCode]: mergedSchema },
        }))
        setActiveTabLang({
          article: langCode,
          youtube: langCode,
          chapters: langCode,
          schema: langCode,
        })
      }
    } catch (err: unknown) {
      setAdaptError(err instanceof Error ? err.message : 'Błąd tłumaczenia całego pakietu')
    } finally {
      setAdaptingAllLang(null)
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
        try {
          data = await apiPost<GenerateResponse>('/v1/generate', {
            video_url: url.trim(),
            llm_provider: 'claude',
            lang: effectiveTargetLang,
            target_lang: effectiveTargetLang,
            ui_lang: uiLang,
            publication_type: publicationType,
            portal_id: portalIdParam,
          })
        } catch (genErr: unknown) {
          const msg = genErr instanceof Error ? genErr.message : String(genErr)
          if (msg.includes('504') || msg.includes('524') || msg.includes('502') || msg.includes('Gateway')) {
            const vid = extractVideoId(url.trim())
            if (vid) {
              for (let attempt = 0; attempt < 25; attempt++) {
                await new Promise((r) => setTimeout(r, 4000))
                try {
                  const hist = await apiGet<Array<{ id: string; video_id?: string; video_url?: string; status: string; has_schema?: boolean }>>('/v1/jobs/history?limit=10')
                  const match = Array.isArray(hist)
                    ? hist.find((j) => (j.video_id === vid || (j.video_url && j.video_url.includes(vid))) && (j.status === 'done' || j.has_schema))
                    : undefined
                  if (match?.id) {
                    const fullJob = await apiGet<{ id: string; video_id?: string; video_url: string; schema_data?: SchemaData }>(`/v1/jobs/${match.id}`)
                    if (fullJob?.schema_data) {
                      data = {
                        status: 'ok',
                        video_id: fullJob.video_id || vid,
                        processing_time_s: 0,
                        schema_data: fullJob.schema_data,
                        source_lang: (fullJob.schema_data.source_lang as string) || 'pl',
                        target_lang: (fullJob.schema_data.target_lang as string) || effectiveTargetLang,
                      }
                      break
                    }
                  }
                } catch {
                  // continue polling
                }
              }
            }
          }
          if (!data) throw genErr
        }
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
      setMaterialTranslations(buildTranslationsState(schema, detectedTargetLang))
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
  const quotes = (schema?.quotes as QuoteItem[] | undefined) ?? []
  const planLabel =
    userProfile?.plan_badge ||
    (userProfile?.has_multilang_addon && (userPlan === 'starter' || userPlan === 'free')
      ? 'Starter + 🌐 8 Jęz.'
      : (userProfile?.plan?.display_name ?? 'Free'))
  const usageUsed = userProfile?.usage?.used_this_month ?? userProfile?.used_this_month ?? 0
  const usageQuota = userProfile?.usage?.quota ?? userProfile?.monthly_quota ?? 5
  const extraQuotaBalance = userProfile?.extra_quota_balance ?? userProfile?.usage?.extra_quota_balance ?? 0
  const customMonthlyQuota = userProfile?.custom_monthly_quota ?? userProfile?.usage?.custom_monthly_quota ?? null
  const usagePercent = usageQuota === -1 ? 15 : usageQuota > 0 ? Math.min(100, (usageUsed / usageQuota) * 100) : 0

  const sourceLangMeta = VSE_LANGUAGES.find((l) => l.code === (result?.sourceLang || result?.raw?.source_lang || 'pl'))
  const targetLangMeta = VSE_LANGUAGES.find((l) => l.code === currentTabLang) || VSE_LANGUAGES[0]
  const t = getTranslations(uiLang)

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gray-950 text-white">
        {/* Sidebar */}
        <aside className="fixed left-0 top-0 h-full w-64 bg-gray-900 border-r border-gray-800 flex flex-col z-20">
          <div className="p-5 border-b border-gray-800">
            <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-violet-600 to-fuchsia-600 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.069A1 1 0 0121 8.87v6.26a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <span className="font-bold text-white block">PressAI VSE</span>
                <span className="text-xs text-gray-500">Video SEO Engine</span>
              </div>
            </Link>
          </div>

          <nav className="flex-1 p-4 space-y-1">
            <NavItem icon="grid" label={t.navDashboard} href="/dashboard" active />
            <NavItem icon="clock" label={t.navHistory} href="/historia" />
            <NavItem icon="settings" label={t.navSettings} href="/ustawienia" />
            <NavItem icon="grid" label={t.navPricing} href="/cennik" />
          </nav>

          {/* User info + plan + UI language */}
          <div className="p-4 border-t border-gray-800">
            <div className="mb-3">
              <div className="flex justify-between items-center text-xs text-gray-400 mb-1">
                <span>{t.navUsed}</span>
                <span className="font-mono text-gray-200">
                  {usageUsed}/{usageQuota === -1 ? '∞' : usageQuota}
                  {customMonthlyQuota !== null && (
                    <span className="ml-1 text-[10px] text-amber-400 font-semibold">(VIP)</span>
                  )}
                </span>
              </div>
              <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-full transition-all"
                  style={{ width: `${usagePercent}%` }}
                />
              </div>
              <div className="flex items-center justify-between mt-1.5">
                {extraQuotaBalance > 0 ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                    ⚡ +{extraQuotaBalance} Top-Up
                  </span>
                ) : (
                  <span className="text-[10px] text-gray-500">Top-Up: 0 filmów</span>
                )}
                <a
                  href="/cennik#topup"
                  className="text-[11px] font-medium text-emerald-400 hover:text-emerald-300 transition-colors"
                >
                  + Dokup pakiet Top-Up
                </a>
              </div>
            </div>

            <div className="flex items-center gap-3 mb-3">
              <div className="w-8 h-8 rounded-full bg-violet-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
                {session?.user?.email?.[0]?.toUpperCase() || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white truncate">{session?.user?.email}</p>
                <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${
                      userPlan !== 'free' || hasMultilangAddon
                        ? 'bg-gradient-to-r from-violet-600/30 to-emerald-600/30 text-emerald-300 border-emerald-500/40'
                        : 'bg-gray-800 text-gray-300 border-gray-700'
                    }`}
                  >
                    Plan {planLabel}
                  </span>
                  {userProfile?.desktop_runner_active && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      💻 Runner
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
                {t.navChangePlan}
              </a>
              {!hasMultilangAddon && (
                <button
                  type="button"
                  onClick={handleBuyMultilangAddon}
                  disabled={addonCheckoutLoading}
                  className="text-left text-xs text-emerald-400 hover:text-emerald-300 transition-colors py-0.5"
                >
                  {t.navBuyAddon}
                </button>
              )}
              {(userProfile?.plan?.id !== 'free' || hasMultilangAddon) && (
                <ManageSubscriptionLink accessToken={(session as { accessToken?: string })?.accessToken} />
              )}
            </div>

            {/* Compact UI Language Switcher at the bottom of Sidebar */}
            <div className="mb-3 pt-2.5 border-t border-gray-800/80">
              <div className="flex items-center justify-between gap-2">
                <label htmlFor="sidebar-ui-lang" className="text-[11px] text-gray-400 truncate">
                  🌐 {t.uiLangLabel}:
                </label>
                <select
                  id="sidebar-ui-lang"
                  aria-label={t.uiLangLabel}
                  value={uiLang}
                  onChange={(e) => handleUiLangChange(e.target.value)}
                  className="w-28 flex-shrink-0 bg-gray-950 border border-gray-800 hover:border-gray-600 text-xs text-gray-200 rounded-lg px-2 py-1 cursor-pointer focus:outline-none focus:border-violet-500"
                >
                  {VSE_LANGUAGES.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.label} ({l.short})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button
              onClick={() => signOut({ callbackUrl: '/login' })}
              className="w-full text-left text-sm text-gray-400 hover:text-white transition-colors py-1"
            >
              → {t.navSignOut}
            </button>
          </div>
        </aside>

        {/* Main content */}
        <main className="ml-64 p-8">
          <div className="max-w-4xl">

            <EmailVerificationBanner
              isVerified={userProfile?.is_verified}
              accessToken={(session as { accessToken?: string })?.accessToken}
            />

            <div className="flex flex-wrap items-start justify-between gap-4 mb-1">
              <h1 className="text-2xl font-bold text-white">{t.heading}</h1>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-xs text-violet-300">
                {t.crossLangBadge}
              </span>
            </div>
            <p className="text-gray-400 mb-8">
              {t.subheading}
            </p>

            {jobLoading && (
              <div className="mb-6 flex items-center gap-3 p-4 bg-violet-500/5 border border-violet-500/20 rounded-xl">
                <span className="animate-spin inline-block w-4 h-4 border-2 border-violet-300/30 border-t-violet-400 rounded-full" />
                <span className="text-sm text-violet-300">{t.historyLoading}</span>
              </div>
            )}

            {jobError && (
              <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
                ⚠️ {jobError}
              </div>
            )}

            {jobId && result && (
              <div className="mb-6 flex items-center gap-2 p-3 bg-blue-500/5 border border-blue-500/20 rounded-xl">
                <span className="text-xs text-blue-400">{t.historyLoaded}</span>
                <Link href="/historia" className="text-xs text-gray-500 hover:text-white ml-auto transition-colors">
                  {t.historyBack}
                </Link>
              </div>
            )}

            {/* Portal, Publication Type & Target Language Selector */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">{t.targetPortal}</label>
                {portalsLoading ? (
                  <div className="flex items-center gap-2 h-[42px] text-sm text-gray-500">
                    <span className="animate-spin inline-block w-3 h-3 border border-gray-500 border-t-violet-400 rounded-full" />
                    {t.loading}
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
                    <option value="" disabled>{t.noPortals}</option>
                    <option value="__add__">{t.addPortal}</option>
                    <option value="__manual__">{t.manualPortal}</option>
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
                        {p.is_plugin_connected || p.auth_mode === 'plugin_token' ? `🔌 ${p.name} (Wtyczka v3.0)` : p.name}
                      </option>
                    ))}
                    <option value="__add__">{t.addPortal}</option>
                    <option value="__manual__">{t.manualPortal}</option>
                  </select>
                )}
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">{t.publicationType}</label>
                <select
                  id="publication-type-selector"
                  value={publicationType}
                  onChange={(e) => setPublicationType(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer"
                  style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3E%3Cpath stroke=\'%236b7280\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.5rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }}
                >
                  <option value="full_analysis">{t.pubFullAnalysis}</option>
                  <option value="news">{t.pubNews}</option>
                  <option value="explainer">{t.pubExplainer}</option>
                  <option value="wywiad">{t.pubInterview}</option>
                  <option value="poradnik">{t.pubGuide}</option>
                  <option value="felieton">{t.pubColumn}</option>
                  <option value="reportaz">{t.pubReportage}</option>
                  <option value="watching_page">{t.pubVideoPage}</option>
                  <option value="discover">{t.pubDiscover}</option>
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs text-gray-400">
                    {t.targetLangLabel}{' '}
                    <span className="text-[10px] text-violet-400">({t.targetLangDefaultHint})</span>
                  </label>
                  {!canOverrideTargetLang && (
                    <button
                      type="button"
                      onClick={() => setShowMultilangUpsell(true)}
                      className="text-[11px] text-emerald-400 hover:text-emerald-300 font-medium"
                    >
                      {t.unlock8Langs}
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
                        {l.label} ({l.short}){locked ? t.lockedSuffix : ''}
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
                    <span className="text-sm font-semibold text-white">{t.upsellTitle}</span>
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      {userPlan === 'free' ? 'Starter 49 zł + Add-on 29 zł' : '+29 PLN / mo'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-300 leading-relaxed">
                    {t.upsellDesc}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2 flex-shrink-0">
                  {userPlan === 'free' ? (
                    <>
                      <button
                        type="button"
                        onClick={() => handleCheckoutPlan('starter_multilang')}
                        disabled={addonCheckoutLoading}
                        className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white rounded-lg transition-colors whitespace-nowrap"
                      >
                        {addonCheckoutLoading ? t.loading : '🚀 Wybierz Starter + Pakiet 8 Języków (78 zł/mies.)'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleCheckoutPlan('pro')}
                        disabled={addonCheckoutLoading}
                        className="px-3.5 py-2 bg-violet-600 hover:bg-violet-500 text-xs font-semibold text-white rounded-lg transition-colors whitespace-nowrap"
                      >
                        💎 Wybierz Plan Pro — 8 Języków W CENIE (149 zł/mies.)
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => handleCheckoutPlan('multilang_addon')}
                        disabled={addonCheckoutLoading}
                        className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white rounded-lg transition-colors whitespace-nowrap"
                      >
                        {addonCheckoutLoading ? t.loading : '🌐 Dokup Pakiet Wielojęzyczny (+29 zł/mies.)'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleCheckoutPlan('pro')}
                        disabled={addonCheckoutLoading}
                        className="px-3.5 py-2 bg-violet-600 hover:bg-violet-500 text-xs font-semibold text-white rounded-lg transition-colors whitespace-nowrap"
                      >
                        💎 Upgrade do Pro (149 zł/mies.)
                      </button>
                    </>
                  )}
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
                {t.modeYoutube}
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
                {t.modeAudio}
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
                    placeholder={t.urlPlaceholder}
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
                            {audioFile ? audioFile.name : t.audioDropTitle}
                          </p>
                          <p className="text-xs text-gray-500">
                            {audioFile ? `${(audioFile.size / (1024 * 1024)).toFixed(2)} MB` : t.audioDropFormats}
                          </p>
                        </div>
                      </div>
                      <span className="text-xs bg-gray-800 group-hover:bg-violet-600 text-gray-300 group-hover:text-white px-3 py-1.5 rounded-lg transition-colors whitespace-nowrap ml-2">
                        {audioFile ? t.changeFile : t.chooseFile}
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
                    <><span className="animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> {inputMode === 'audio' ? t.generatingAudioBtn : t.generatingBtn}</>
                  ) : (
                    <>{t.generateBtn}</>
                  )}
                </button>
              </div>

              {loading && (
                <div className="mt-3 flex items-center gap-2 text-sm text-gray-400">
                  <span className="animate-spin inline-block w-3 h-3 border border-gray-500 border-t-violet-400 rounded-full" />
                  {inputMode === 'audio'
                    ? t.loadingAudioMsg
                    : t.loadingVideoMsg}
                </div>
              )}

              {error && (
                <div className="mt-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm flex items-start gap-2">
                  <span className="flex-shrink-0 mt-0.5">⚠️</span>
                  <div>
                    <p className="font-medium mb-0.5">{t.errorTitle}</p>
                    <p className="text-red-300/80">{error}</p>
                  </div>
                </div>
              )}
            </form>

            {!result && !loading && (
              <>
                <div className="grid grid-cols-3 gap-4 mb-6">
                  {[
                    {
                      label: t.statMonthly,
                      value: `${usageUsed}/${usageQuota === -1 ? '∞' : usageQuota}`,
                      sub: extraQuotaBalance > 0 ? `Plan ${planLabel} • ⚡ +${extraQuotaBalance} Top-Up` : `Plan ${planLabel}`,
                    },
                    { label: t.statBenchmark, value: '8/10', sub: t.statBenchmarkSub },
                    { label: t.statSchema, value: 'v5.3', sub: 'Google 2026' },
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
                      <h2 className="text-lg font-semibold text-white">{t.resultsHeading}</h2>
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-violet-500/10 border border-violet-500/30 text-xs text-violet-300">
                        🌐 {t.sourceLabel}: {sourceLangMeta ? `${sourceLangMeta.flag} ${sourceLangMeta.short}` : (result.sourceLang || 'AUTO').toUpperCase()} → {t.outputLabel}: {targetLangMeta.flag} {targetLangMeta.label} ({targetLangMeta.short})
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {t.sourceLabel}: <span className="font-mono">{result.videoId}</span>
                      {result.time && <> • {result.time.toFixed(1)}s</>}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-sm rounded-full border border-emerald-500/20">
                      {t.generatedBadge}
                    </span>
                    {isPro && (
                      <button
                        onClick={() => setShowInjectModal(true)}
                        className="px-4 py-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-sm font-medium text-white rounded-full hover:opacity-90 transition-all flex items-center gap-1.5"
                      >
                        {t.sendToPortalBtn}
                      </button>
                    )}
                    {ytChannels.length > 0 && !result?.inputUrl?.startsWith('audio://') && !result?.videoId?.startsWith('audio_') && (
                      <button
                        onClick={() => setYtModalOpen(true)}
                        className="px-4 py-1.5 bg-gradient-to-r from-red-600 to-red-500 text-sm font-medium text-white rounded-full hover:opacity-90 transition-all flex items-center gap-1.5 ml-2"
                      >
                        {t.sendToYoutubeBtn}
                      </button>
                    )}
                  </div>
                </div>

                {/* Global Package Translation Bar (Translate ALL tabs at once) */}
                <div className="mb-3 p-3 bg-gradient-to-r from-violet-950/50 via-gray-900 to-fuchsia-950/30 border border-violet-500/30 rounded-xl flex flex-wrap items-center justify-between gap-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-violet-200 flex items-center gap-1.5">
                      🌐 {uiLang === 'pl' ? 'Przetłumacz cały pakiet (wszystkie zakładki) na:' : 'Translate entire package (all tabs) to:'}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {VSE_LANGUAGES.map((l) => {
                      const allCached = ['article', 'youtube', 'chapters', 'schema'].every(
                        (tKey) => Boolean(materialTranslations[tKey]?.[l.code])
                      )
                      const allActive = ['article', 'youtube', 'chapters', 'schema'].every(
                        (tKey) => (activeTabLang[tKey] || result?.targetLang || 'pl') === l.code
                      )
                      const isLocked = !canAdaptPerMaterial && !allActive
                      const isAdaptingThisAll = adaptingAllLang === l.code
                      return (
                        <button
                          key={`all-${l.code}`}
                          type="button"
                          disabled={Boolean(adaptingLang)}
                          onClick={() => handleAdaptAllMaterials(l.code)}
                          className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all flex items-center gap-1 ${
                            allActive
                              ? 'bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white border-violet-400 shadow-sm'
                              : allCached
                              ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/25'
                              : 'bg-gray-800/90 text-gray-200 border-gray-700 hover:border-violet-400 hover:text-white'
                          }`}
                          title={`${l.label} (${l.short})`}
                        >
                          <span>{l.flag}</span>
                          <span>{l.short}</span>
                          {isAdaptingThisAll && (
                            <span className="animate-spin inline-block w-3 h-3 border border-white/40 border-t-white rounded-full ml-0.5" />
                          )}
                          {!isAdaptingThisAll && allCached && (
                            <span className="text-[10px] text-emerald-300">✓</span>
                          )}
                          {isLocked && <span className="text-[10px] opacity-80">🔒</span>}
                        </button>
                      )
                    })}
                  </div>
                </div>

                <TabBar
                  active={activeTab}
                  onChange={setActiveTab}
                  chaptersCount={chapters.length}
                  faqCount={faq.length}
                  uiLang={uiLang}
                />

                {/* Per-Material Language Switcher Bar ("Złoty Środek") */}
                {activeTab !== 'shorts' && (
                  <div className="mb-4 p-3 bg-gray-900/90 border border-gray-800 rounded-xl">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-medium text-gray-400 flex items-center gap-1.5">
                        🌐 {t.materialLangLabel}
                      </span>
                      <div className="flex flex-wrap items-center gap-1.5">
                        {VSE_LANGUAGES.map((l) => {
                          const isCurrent = currentTabLang === l.code
                          const isCached = Boolean(materialTranslations[activeTab]?.[l.code])
                          const isLocked = !canAdaptPerMaterial && !isCurrent
                          const isAdaptingThis = adaptingLang === l.code && !adaptingAllLang
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
                              title={`${l.label} (${l.short})`}
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
                        {!['article', 'youtube', 'chapters', 'schema'].every((tKey) => Boolean(materialTranslations[tKey]?.[currentTabLang])) && (
                          <button
                            type="button"
                            disabled={Boolean(adaptingLang)}
                            onClick={() => handleAdaptAllMaterials(currentTabLang)}
                            className="ml-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 border border-violet-500/40 transition-all flex items-center gap-1"
                          >
                            ⚡ {uiLang === 'pl' ? `Przetłumacz wszystkie zakładki na ${targetLangMeta.short}` : `Translate all tabs to ${targetLangMeta.short}`}
                          </button>
                        )}
                      </div>
                    </div>

                    {adaptingLang && (
                      <div className="mt-2.5 flex items-center gap-2 text-xs text-violet-300">
                        <span className="animate-spin inline-block w-3 h-3 border border-violet-400/30 border-t-violet-400 rounded-full" />
                        {adaptingAllLang
                          ? (uiLang === 'pl' ? 'Tłumaczenie całego pakietu (wszystkich zakładek) na:' : 'Translating entire package (all tabs) to:')
                          : t.adaptingMsg}{' '}
                        <strong>{VSE_LANGUAGES.find((x) => x.code === adaptingLang)?.label}</strong>... {t.adaptingNoQuota}
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
                  <ArticleTab
                    schema={schema}
                    faq={faq}
                    quotes={quotes}
                    copiedKey={copiedKey}
                    onCopy={handleCopy}
                  />
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
                  (userPlan === 'agency' || userProfile?.is_admin) ? (
                    <ShortMachineTab
                      ytChannels={ytChannels}
                      initialYoutubeId={result?.videoId || extractVideoId(url) || extractVideoId(result?.inputUrl || '')}
                      accessToken={accessToken}
                      session={session}
                      source={(result?.raw?.source as string) || (result?.inputUrl?.startsWith('audio://') || result?.videoId?.startsWith('audio_') ? 'audio' : 'youtube')}
                      isAudio={result?.raw?.source === 'audio' || result?.inputUrl?.startsWith('audio://') || result?.videoId?.startsWith('audio_')}
                    />
                  ) : (
                    <div className="bg-gray-900 border border-violet-500/30 rounded-2xl p-6 md:p-8">
                      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                        <div className="flex items-center gap-2.5">
                          <span className="px-3 py-1 rounded-full text-xs font-bold bg-violet-500/20 text-violet-300 border border-violet-500/40 uppercase tracking-wider">
                            🎬 Moduł Specjalistyczny · Plan Agency / Add-on
                          </span>
                        </div>
                        <Link
                          href="/shortmachine"
                          className="text-xs text-violet-400 hover:text-violet-300 underline underline-offset-2"
                        >
                          Dowiedz się więcej o ShortMachine →
                        </Link>
                      </div>
                      <h3 className="text-xl font-bold text-white mb-2">
                        ShortMachine AI — Automatyczne rolki 9:16 i markery montażowe NLE
                      </h3>
                      <p className="text-sm text-gray-300 leading-relaxed mb-5">
                        Moduł <strong className="text-white">ShortMachine</strong> automatycznie wybiera najbardziej wiralowe fragmenty z długiego wideo lub nagrania audio, generuje scenariusze Shorts / Reels / TikTok, eksportuje markery XML/EDL do <strong className="text-white">Premiere Pro / DaVinci Resolve</strong> oraz wycina gotowe klipy MP4 9:16 przez lokalny <strong className="text-white">VSE Desktop Runner</strong>.
                      </p>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
                        <div className="bg-gray-800/60 border border-gray-700/60 rounded-xl p-3.5">
                          <p className="text-xs font-semibold text-white mb-1">🎯 AI Viral Hooks</p>
                          <p className="text-xs text-gray-400">Automatyczna detekcja najmocniejszych 30–60s momentów z transkrypcji.</p>
                        </div>
                        <div className="bg-gray-800/60 border border-gray-700/60 rounded-xl p-3.5">
                          <p className="text-xs font-semibold text-white mb-1">🎞️ Premiere &amp; DaVinci</p>
                          <p className="text-xs text-gray-400">Eksport gotowej osi czasu i markerów dla montażystów wideo.</p>
                        </div>
                        <div className="bg-gray-800/60 border border-gray-700/60 rounded-xl p-3.5">
                          <p className="text-xs font-semibold text-white mb-1">✂️ Auto-Cutter 9:16</p>
                          <p className="text-xs text-gray-400">Lokalne wycinanie pionowych klipów MP4 przez VSE Desktop Runner.</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-3">
                        <Link
                          href="/cennik"
                          className="px-5 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:opacity-90 rounded-xl text-xs font-semibold text-white transition-all"
                        >
                          💎 Odblokuj w planie Agency →
                        </Link>
                        <Link
                          href="/shortmachine"
                          className="px-4 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-xl text-xs font-medium text-gray-200 transition-colors"
                        >
                          Zobacz stronę modułu ShortMachine
                        </Link>
                      </div>
                    </div>
                  )
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
