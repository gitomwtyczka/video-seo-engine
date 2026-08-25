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
  const match = url.match(/(?:youtu\.be\/|youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|shorts\/)([^"&?\/\s]{11})/)
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
} from './components'


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
