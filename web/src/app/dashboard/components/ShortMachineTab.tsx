'use client'

import React, { useState, useEffect, useRef } from 'react'
import { extractYoutubeId } from '../utils'
import { YouTubePublishModal } from '../YouTubePublishModal'

interface ShortMachineTabProps {
  ytChannels: any[]
  initialYoutubeId?: string
  accessToken?: string
  session?: any
}

export function ShortMachineTab({ ytChannels, initialYoutubeId, accessToken, session }: ShortMachineTabProps) {
  // ShortMachine state
  const [smYoutubeId, setSmYoutubeId] = useState(initialYoutubeId || '')
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



  return (
    <>
ówny widok aplikacji po zalogowaniu
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
    </>
  )
}

export default ShortMachineTab
