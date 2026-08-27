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

// ─── Types ──────────────────────────────────────────────────────────────────

interface GenerateResponse {
  status: string
  video_id: string
  processing_time_s?: number
  schema_data?: SchemaData | null
  error?: string | null
}

interface SchemaData {
  focus_keyphrase?: string
  post_title?: string
  meta_description?: string
  wp_slug?: string
  lead?: string
  article_body?: string
  chapters?: ChapterItem[]
  faq?: FaqItem[]
  quotes?: QuoteItem[]
  youtube_description_body?: string
  youtube_description_hook?: string
  youtube_description?: string
  video_description?: string
  youtube_mid_cta?: string
  youtube_credits?: string
  youtube_hashtags?: string[] | string
  wp_article_url?: string
  published_url?: string
  wp_url?: string
  source?: string
  media_id?: string
  [key: string]: unknown
}

interface ChapterItem {
  name?: string
  startOffset?: number
  endOffset?: number
  label?: string
  time?: number
}

interface FaqItem {
  question?: string
  answer?: string
}

interface QuoteItem {
  text?: string
  author?: string
}

interface UserPlan {
  id: string
  display_name: string
  monthly_quota: number
}

interface UserProfile {
  email: string
  is_verified?: boolean
  plan: UserPlan
  usage: { used_this_month: number; quota: number; percent: number }
}

interface InjectResult {
  status?: string
  wp_post_id?: number
  post_url?: string
  created?: boolean
  error?: string
  yt_results?: Record<string, string>
}

type CopiedKey = string | null
type TabKey = 'schema' | 'article' | 'chapters' | 'youtube' | 'shorts'

// ─── Helpers ────────────────────────────────────────────────────────────────

function extractChapters(schema: SchemaData | null | undefined): ChapterItem[] {
  if (!schema) return []
  const graph = schema['@graph']
  if (Array.isArray(graph)) {
    const clips = (graph as Record<string, unknown>[]).filter(
      (n) => n['@type'] === 'Clip'
    )
    if (clips.length > 0)
      return clips.map((c) => ({
        name: c.name as string | undefined,
        startOffset: c.startOffset as number | undefined,
        endOffset: c.endOffset as number | undefined,
      }))
  }
  if (Array.isArray(schema.chapters)) {
    return schema.chapters.map((c: ChapterItem) => ({
      name: c.name ?? c.label,
      startOffset: c.startOffset ?? c.time,
      endOffset: c.endOffset,
    }))
  }
  return []
}

function extractFaq(schema: SchemaData | null | undefined): FaqItem[] {
  if (!schema) return []
  const graph = schema['@graph']
  if (Array.isArray(graph)) {
    const faqPage = (graph as Record<string, unknown>[]).find(
      (n) => n['@type'] === 'FAQPage'
    )
    if (faqPage) {
      const items = faqPage['mainEntity']
      if (Array.isArray(items))
        return (items as Record<string, unknown>[]).map((q) => ({
          question: q['name'] as string | undefined,
          answer: ((q['acceptedAnswer'] as Record<string, unknown>)?.['text']) as string | undefined,
        }))
    }
  }
  if (Array.isArray(schema.faq)) return schema.faq
  return []
}

function secToTimestamp(sec?: number): string {
  if (sec == null) return '?'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function chaptersToText(chapters: ChapterItem[]): string {
  return chapters
    .map((c) => `${secToTimestamp(c.startOffset ?? c.time)} — ${c.name ?? c.label ?? '(bez tytułu)'}`)
    .join('\n')
}

function faqToHtml(faq: FaqItem[]): string {
  const items = faq
    .map(
      (f) =>
        `<details><summary>${f.question ?? ''}</summary>\n${f.answer ?? ''}\n</details>`
    )
    .join('\n')
  return `<h3>Często zadawane pytania</h3>\n${items}`
}

function schemaToScriptTag(schema: SchemaData | null): string {
  return `<script type="application/ld+json">\n${JSON.stringify(schema ?? {}, null, 2)}\n</script>`
}

function articleToText(schema: SchemaData | null, faq: FaqItem[]): string {
  const parts: string[] = []
  if (schema?.post_title) parts.push(`# ${schema.post_title}\n`)
  if (schema?.lead) parts.push(`${schema.lead}\n`)
  if (schema?.article_body) parts.push(`${schema.article_body}\n`)
  if (faq.length > 0) {
    parts.push('## FAQ\n')
    faq.forEach((f) => {
      parts.push(`**${f.question ?? ''}**\n${f.answer ?? ''}\n`)
    })
  }
  return parts.join('\n')
}

function loadWpCredentials(): { wpUrl: string; wpUser: string; wpPassword: string } {
  if (typeof window === 'undefined') return { wpUrl: 'https://', wpUser: '', wpPassword: '' }
  try {
    const saved = localStorage.getItem('vse_wp_credentials')
    if (saved) return JSON.parse(saved)
  } catch { /* ignore */ }
  return { wpUrl: 'https://', wpUser: '', wpPassword: '' }
}

function saveWpCredentials(creds: { wpUrl: string; wpUser: string; wpPassword: string }): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem('vse_wp_credentials', JSON.stringify(creds))
  } catch { /* ignore */ }
}

function extractVideoId(url: string): string {
  if (!url) return ''
  if (url.startsWith('audio://')) return url.replace('audio://', '')
  if (url.startsWith('audio_')) return url
  const match = url.match(/(?:youtu\.be\/|youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|shorts\/)([^"&?\/\\s]{11})/)
  return match ? match[1] : (url.length === 11 ? url : '')
}

function buildYtDescription(schema: SchemaData | null | undefined, wpUrl?: string): string {
  if (!schema) return ''
  const parts: string[] = []

  const body = schema?.youtube_description_body ?? schema?.youtube_description_hook ?? schema?.video_description ?? ''
  if (body) parts.push(body as string)

  if (wpUrl) parts.push(`🔗 Artykuł: ${wpUrl}`)

  if (schema.youtube_mid_cta) parts.push(schema.youtube_mid_cta as string)

  const rawChapters = schema.chapters
  if (Array.isArray(rawChapters) && rawChapters.length > 0) {
    const lines = rawChapters.map((c: ChapterItem) => {
      const sec = c.time ?? c.startOffset ?? 0
      const m = Math.floor(sec / 60).toString().padStart(2, '0')
      const s = Math.floor(sec % 60).toString().padStart(2, '0')
      const title = c.label ?? c.name ?? ''
      return `${m}:${s} ${title}`.trim()
    })
    parts.push('ROZDZIAŁY:\n' + lines.join('\n'))
  }

  if (schema.youtube_credits) parts.push(schema.youtube_credits as string)

  const hashtags = schema.youtube_hashtags
  if (hashtags) {
    if (Array.isArray(hashtags)) {
      const tags = (hashtags as string[])
        .map(t => t.startsWith('#') ? t : `#${t}`)
        .join(', ')
      if (tags) parts.push(tags)
    } else if (typeof hashtags === 'string') {
      parts.push(hashtags)
    }
  }

  return parts.join('\n\n')
}

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
  const [result, setResult] = useState<{ raw: SchemaData; videoId: string; time?: number; inputUrl: string } | null>(null)
  const [error, setError] = useState('')
  const [copiedKey, setCopiedKey] = useState<CopiedKey>(null)
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('article')

  const [showInjectModal, setShowInjectModal] = useState(false)
  const [ytModalOpen, setYtModalOpen] = useState(false)
  const [ytChannels, setYtChannels] = useState<any[]>([])
  const [ytDescription, setYtDescription] = useState<string>('')

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

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (inputMode === 'url' && !url.trim()) return
    if (inputMode === 'audio' && !audioFile) return

    setLoading(true)
    setError('')
    setResult(null)

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
        formData.append('lang', 'pl')
        formData.append('llm_provider', 'claude')

        data = await apiPostForm<GenerateResponse>('/v1/audio/generate', formData)
      } else {
        data = await apiPost<GenerateResponse>('/v1/generate', {
          video_url: url.trim(),
          llm_provider: 'claude',
          lang: 'pl',
          publication_type: publicationType,
          portal_id: portalIdParam,
        })
      }

      if (!data) throw new Error('Pusta odpowiedź serwera')
      if (data.error) throw new Error(data.error)

      const schema = data.schema_data ?? null
      if (!schema) throw new Error('Serwer nie zwrócił schema_data')

      const effectiveInputUrl = inputMode === 'audio' ? `audio://${data.video_id}` : url.trim()
      setResult({ raw: schema, videoId: data.video_id, time: data.processing_time_s, inputUrl: effectiveInputUrl })
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

            <h1 className="text-2xl font-bold text-white mb-1">Video & Audio SEO Engine</h1>
            <p className="text-gray-400 mb-8">
              Wklej link YouTube lub wgraj plik MP3 — AI wygeneruje kompletny pakiet SEO, transkrypcję i artykuł.
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
            </div>

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
                    placeholder="https://www.youtube.com/watch?v=..."
                    className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
                  />
                ) : (
                  <div className="flex-1 flex items-center">
                    <label className="w-full flex items-center justify-between bg-gray-900 border border-dashed border-gray-700 hover:border-violet-500 rounded-xl px-4 py-3 cursor-pointer transition-colors group">
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
                <div className="flex items-center justify-between mb-5">
                  <div>
                    <h2 className="text-lg font-semibold text-white">Wyniki SEO</h2>
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
              videoId={result?.videoId || result?.raw?.video_id || extractVideoId(result?.inputUrl || "") || ""}
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
