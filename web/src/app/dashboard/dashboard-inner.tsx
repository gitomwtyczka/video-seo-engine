'use client'



/**

 * CO: Dashboard — główny widok aplikacji po zalogowaniu

 * PO CO: Daje użytkownikowi dwie ścieżki:

 *   A (Free/Starter) — generuje SEO i pokazuje gotowe snippety HTML do skopiowania

 *   B (Pro/Agency)   — dodatkowo umożliwia automatyczną publikację na WordPress

 * JAK: Wywołuje POST /v1/generate → schema_data → renderuje 3 zakładki wynikowe

 *      (Schemat, Artykuł, Rozdziały). Dla planu pro/agency InjectModal → POST /v1/inject.

 *

 * ROUTING NOTE: Frontend używa pustego prefixu ('') jako fallback dla NEXT_PUBLIC_API_URL.

 * Wywołania idą na /v1/generate, /v1/inject, /v1/users/me.

 * Nginx routuje location /v1/ → FastAPI :8085 (bez strippowania prefixu).

 * NIE używamy /api/v1/* — nginx /api/ nie strippuje /api i FastAPI zwraca 404.

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

  [key: string]: unknown

}



interface ChapterItem {

  name?: string

  startOffset?: number

  endOffset?: number

  // Backend format (generator.py output)

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

}



type CopiedKey = string | null

type TabKey = 'schema' | 'article' | 'chapters' | 'youtube' | 'shorts'



// ─── Helpers ────────────────────────────────────────────────────────────────



/**

 * Extract Clip chapters from JSON-LD @graph or top-level chapters array.

 *

 * CO: Normalizuje format rozdziałów do ChapterItem[].

 * PO CO: Backend (generator.py) zwraca chapters jako {time, label, matched, anchor_text}.

 *        Frontend oczekiwał {startOffset, name, endOffset} — powodowało "(bez tytułu)" i "?".

 * JAK: Sprawdza @graph (JSON-LD Clip), następnie normalizes top-level chapters

 *      mapując label→name i time→startOffset.

 */

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

    // Normalize backend format {time, label} → frontend format {startOffset, name}

    return schema.chapters.map((c: ChapterItem) => ({

      name: c.name ?? c.label,

      startOffset: c.startOffset ?? c.time,

      endOffset: c.endOffset,

    }))

  }

  return []

}



/** Extract FAQPage entries from JSON-LD @graph or top-level faq array. */

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



/** Convert seconds to MM:SS timestamp string. */

function secToTimestamp(sec?: number): string {

  if (sec == null) return '?'

  const m = Math.floor(sec / 60)

  const s = Math.floor(sec % 60)

  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`

}



/** Build copyable chapters text: "MM:SS — Tytuł" per line. */

function chaptersToText(chapters: ChapterItem[]): string {

  return chapters

    .map((c) => `${secToTimestamp(c.startOffset ?? c.time)} — ${c.name ?? c.label ?? '(bez tytułu)'}`)

    .join('\n')

}



/** Build copyable FAQ HTML block. */

function faqToHtml(faq: FaqItem[]): string {

  const items = faq

    .map(

      (f) =>

        `<details><summary>${f.question ?? ''}</summary>\n${f.answer ?? ''}\n</details>`

    )

    .join('\n')

  return `<h3>Często zadawane pytania</h3>\n${items}`

}



/** Build full schema script block for copy. */

function schemaToScriptTag(schema: SchemaData | null): string {

  return `<script type="application/ld+json">\n${JSON.stringify(schema ?? {}, null, 2)}\n</script>`

}



/** Build article text for copy (lead + body + faq). */

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



/** Load WP credentials from localStorage */

function loadWpCredentials(): { wpUrl: string; wpUser: string; wpPassword: string } {

  if (typeof window === 'undefined') return { wpUrl: 'https://', wpUser: '', wpPassword: '' }

  try {

    const saved = localStorage.getItem('vse_wp_credentials')

    if (saved) return JSON.parse(saved)

  } catch { /* ignore */ }

  return { wpUrl: 'https://', wpUser: '', wpPassword: '' }

}



/** Save WP credentials to localStorage */

function saveWpCredentials(creds: { wpUrl: string; wpUser: string; wpPassword: string }): void {

  if (typeof window === 'undefined') return

  try {

    localStorage.setItem('vse_wp_credentials', JSON.stringify(creds))

  } catch { /* ignore */ }

}



// ─── Subcomponents ──────────────────────────────────────────────────────────



/**

 * CO: CopyButton — przycisk kopiowania z feedbackiem

 * PO CO: Umożliwia szybkie skopiowanie dowolnego tekstu do schowka

 *        z wizualnym potwierdzeniem ("✔️ Skopiowano" przez 2s).

 * JAK: Używa navigator.clipboard.writeText, przekazuje copied-key do rodzica.

 */

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



/**

 * CO: ResultSection — pojedyncza sekcja wynikowa z nagłówkiem i przyciskiem Kopiuj

 * PO CO: Zapewnia spójny wygląd wszystkich pól wynikowych.

 * JAK: Opakowuje dowolny content children w ramkę z nagłówkiem i przyciskiem kopiowania.

 */

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

          {badge && (\n\n            <span className=\"px-2 py-0.5 text-xs bg-violet-500/15 text-violet-400 rounded-full border border-violet-500/20\">\n\n              {badge}\n\n            </span>\n\n          )}\n\n        </div>\n\n        <CopyButton text={copyText} id={copyId} copiedKey={copiedKey} onCopy={onCopy} />\n\n      </div>\n\n      <div className=\"p-4\">{children}</div>\n\n    </div>\n\n  )\n\n}\n\n\n\n/**\n\n * CO: TabBar — przełącznik zakładek Schemat/Artykuł/Rozdziały\n\n * PO CO: Pozwala użytkownikowi przełączać widok wyników bez przeładowania strony.\n\n * JAK: Proste przyciski z active state, kontrolowane przez parent.\n\n */\n\nfunction TabBar({\n\n  active,\n\n  onChange,\n\n  chaptersCount,\n\n  faqCount,\n\n}: {\n\n  active: TabKey\n\n  onChange: (tab: TabKey) => void\n\n  chaptersCount: number\n\n  faqCount: number\n\n}) {\n\n  const tabs: { key: TabKey; label: string; badge?: number }[] = [\n\n    { key: 'schema', label: 'Schemat' },\n\n    { key: 'article', label: 'Artykuł', badge: faqCount > 0 ? faqCount : undefined },\n\n    { key: 'chapters', label: 'Rozdziały', badge: chaptersCount > 0 ? chaptersCount : undefined },\n\n    { key: 'youtube', label: 'Opis YouTube' },\n\n    { key: 'shorts', label: '✂️ ShortMachine' },\n\n  ]\n\n\n\n  return (\n\n    <div className=\"flex gap-1 bg-gray-900 border border-gray-800 rounded-xl p-1 mb-5\">\n\n      {tabs.map((tab) => (\n\n        <button\n\n          key={tab.key}\n\n          onClick={() => onChange(tab.key)}\n\n          className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${\n\n            active === tab.key\n\n              ? 'bg-violet-600/20 text-violet-400 border border-violet-500/30'\n\n              : 'text-gray-400 hover:text-white hover:bg-gray-800/50 border border-transparent'\n\n          }`}\n\n        >\n\n          {tab.label}\n\n          {tab.badge != null && tab.badge > 0 && (\n\n            <span className={`px-1.5 py-0.5 text-xs rounded-full ${\n\n              active === tab.key\n\n                ? 'bg-violet-500/30 text-violet-300'\n\n                : 'bg-gray-700 text-gray-500'\n\n            }`}>\n\n              {tab.badge}\n\n            </span>\n\n          )}\n\n        </button>\n\n      ))}\n\n    </div>\n\n  )\n\n}\n\n\n\n/**\n\n * CO: InjectModal — modalny formularz publikacji na WordPress z dropdown portalów\n\n * PO CO: Umożliwia użytkownikom Pro/Agency wstrzyknięcie SEO na WordPress jednym klikiem.\n\n *        Portale zapisane w bazie danych (/v1/portals) — dropdown z auto-fill credentials.\n\n *        Fallback: ręczne wpisanie credentials (zapisywane w localStorage).\n\n * JAK: usePortals() → dropdown z listą portali → wybór portalu → getCredentials() → auto-fill.\n\n *      Po kliknięciu \"Opublikuj\" → POST /v1/inject → wyświetla wynik z linkiem do posta.\n\n */\n\nfunction InjectModal({\n\n  schemaData,\n\n  videoUrl,\n\n  selectedPortalId,\n\n  portalName,\n\n  portalUrl,\n\n  accessToken,\n\n  onClose,\n\n  ytChannels,\n\n}: {\n\n  schemaData: SchemaData\n\n  videoUrl: string\n\n  selectedPortalId: string\n\n  portalName?: string\n\n  portalUrl?: string\n\n  accessToken?: string\n\n  onClose: () => void\n\n  ytChannels?: any[]\n\n}) {\n\n  const initialCreds = loadWpCredentials()\n\n  const [wpUrl, setWpUrl] = useState(initialCreds.wpUrl)\n\n  const [wpUser, setWpUser] = useState(initialCreds.wpUser)\n\n  const [wpPassword, setWpPassword] = useState(initialCreds.wpPassword)\n\n  const [wpPostId, setWpPostId] = useState('')\n\n  const [postStatus, setPostStatus] = useState<'draft' | 'publish'>('draft')\n\n  const [postFormat, setPostFormat] = useState('video')\n\n  const [publishing, setPublishing] = useState(false)\n\n  const [publishResult, setPublishResult] = useState<InjectResult | null>(null)\n\n  const [selectedYtChannelIds, setSelectedYtChannelIds] = useState<string[]>([])\n\n  const [ytDescPreview, setYtDescPreview] = useState<string>('')\n\n  const [showYtPreview, setShowYtPreview] = useState<boolean>(false)\n\n\n\n  const modalRef = useRef<HTMLDivElement>(null)\n\n\n\n\n\n\n\n\n\n\n\n\n\n  // Close on Escape\n\n  useEffect(() => {\n\n    const handler = (e: KeyboardEvent) => {\n\n      if (e.key === 'Escape') onClose()\n\n    }\n\n    window.addEventListener('keydown', handler)\n\n    return () => window.removeEventListener('keydown', handler)\n\n  }, [onClose])\n\n\n\n\n\n\n\n  // Close on click outside\n\n  const handleBackdropClick = (e: React.MouseEvent) => {\n\n    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {\n\n      onClose()\n\n    }\n\n  }\n\n\n\n\n\n\n\n  const isManual = selectedPortalId === '__manual__' || !selectedPortalId\n\n\n\n  // Update YT preview\n\n  useEffect(() => {\n\n    if (selectedYtChannelIds.length === 0) { setYtDescPreview(''); return }\n\n    const parts = []\n\n    if (schemaData?.youtube_description_body) parts.push(schemaData.youtube_description_body)\n\n    if (schemaData?.youtube_mid_cta) parts.push(schemaData.youtube_mid_cta)\n\n    if (schemaData?.youtube_credits) parts.push(schemaData.youtube_credits)\n\n    if (schemaData?.youtube_hashtags) parts.push(schemaData.youtube_hashtags)\n\n    \n\n    // Stopka z pierwszego kanału\n\n    const firstCh = ytChannels?.find(ch => selectedYtChannelIds.includes(ch.channel_id))\n\n    if (firstCh?.footer_text) parts.push(firstCh.footer_text)\n\n    \n\n    setYtDescPreview(parts.join('\\n\\n') || '(brak wygenerowanego opisu)')\n\n  }, [selectedYtChannelIds, schemaData, ytChannels])\n\n\n\n\n\n\n\n  const handlePublish = async () => {\n\n    const isPublishingToWp = !isManual || (wpUser && wpPassword && wpUrl)\n\n    if (!isPublishingToWp && selectedYtChannelIds.length === 0) {\n\n      setPublishResult({ error: 'Uzupełnij URL portalu, użytkownika i Application Password lub wybierz kanał YouTube.' })\n\n      return\n\n    }\n\n\n\n\n\n\n\n    if (isPublishingToWp && isManual) {\n\n      saveWpCredentials({ wpUrl, wpUser, wpPassword })\n\n    }\n\n\n\n\n\n\n\n    setPublishing(true)\n\n    setPublishResult(null)\n\n    try {\n\n      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''\n\n      const body: Record<string, unknown> = {\n\n        video_url: videoUrl,\n\n        schema_data: schemaData,\n\n        post_status: postStatus,\n\n        post_format: postFormat,\n\n      }\n\n      \n\n      if (selectedYtChannelIds.length > 0) {\n\n        body.yt_channel_ids = selectedYtChannelIds\n\n        if (showYtPreview && ytDescPreview) {\n\n          body.yt_override_description = ytDescPreview\n\n        }\n\n      }\n\n\n\n\n\n\n\n      if (isPublishingToWp) {\n\n        if (isManual) {\n\n          body.site_config = {\n\n            wp_base_url: wpUrl,\n\n            wp_user: wpUser,\n\n            wp_app_password: wpPassword,\n\n          }\n\n        } else {\n\n          body.portal_id = selectedPortalId.trim()\n\n        }\n\n        if (wpPostId.trim()) {\n\n          body.wp_post_id = parseInt(wpPostId, 10)\n\n        }\n\n      }\n\n\n\n\n\n\n\n      const res = await fetch(`${apiUrl}/v1/inject`, {\n\n        method: 'POST',\n\n        headers: {\n\n        'Content-Type': 'application/json',\n\n        ...(accessToken && { Authorization: `Bearer ${accessToken}` }),\n\n      },\n\n        body: JSON.stringify(body),\n\n      })\n\n      let data: any\n\n      try { data = await res.json() } catch { data = { error: `HTTP ${res.status}` } }\n\n      \n\n      if (!res.ok) {\n\n        let errStr = data?.detail || data?.error || `Błąd serwera (HTTP ${res.status})`;\n\n        if (typeof errStr === 'object') {\n\n            errStr = JSON.stringify(errStr, null, 2);\n\n        }\n\n        throw new Error(errStr);\n\n      }\n\n      setPublishResult(data)\n\n      if (data?.yt_results) {\n\n        const errors: string[] = [];\n\n        Object.entries(data.yt_results).forEach(([chId, status]) => {\n\n          if (status !== \"ok\") errors.push(`Błąd YT: ${status}`);\n\n        });\n\n        if (errors.length > 0) {\n\n          setPublishResult(prev => ({\n\n            ...prev,\n\n            error: (prev?.error ? prev.error + \"\\n\" : \"\") + errors.join(\"\\n\")\n\n          }))\n\n        }\n\n      }\n\n    } catch (e: unknown) {\n\n      setPublishResult({ error: e instanceof Error ? e.message : 'Błąd połączenia' })\n\n    } finally {\n\n      setPublishing(false)\n\n    }\n\n  }\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n  return (\n\n    <div\n\n      className=\"fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm\"\n\n      onClick={handleBackdropClick}\n\n    >\n\n      <div\n\n        ref={modalRef}\n\n        className=\"w-full max-w-lg bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden animate-in\"\n\n        style={{ animation: 'fadeInUp 0.25s ease-out' }}\n\n      >\n\n        {/* Header */}\n\n        <div className=\"flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gradient-to-r from-violet-950/50 to-fuchsia-950/30\">\n\n          <div className=\"flex items-center gap-3\">\n\n            <div className=\"w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center text-sm\">\n\n              🚀\n\n            </div>\n\n            <div>\n\n              <h3 className=\"font-semibold text-white\">Publikuj na WordPress</h3>\n\n              <p className=\"text-xs text-gray-400\">Wyślij artykuł + SEO schema na portal</p>\n\n            </div>\n\n          </div>\n\n          <button\n\n            onClick={onClose}\n\n            className=\"text-gray-400 hover:text-white transition-colors p-1\"\n\n          >\n\n            <svg className=\"w-5 h-5\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\">\n\n              <path strokeLinecap=\"round\" strokeLinejoin=\"round\" strokeWidth={2} d=\"M6 18L18 6M6 6l12 12\" />\n\n            </svg>\n\n          </button>\n\n        </div>\n\n\n\n\n\n\n\n        {/* Body */}\n\n        <div className=\"px-6 py-5 space-y-4\">\n\n          {/* Article preview */}\n\n          <div className=\"bg-gray-800/50 border border-gray-700/50 rounded-xl p-4\">\n\n            <p className=\"text-xs text-gray-500 mb-1\">Artykuł do publikacji:</p>\n\n            <p className=\"text-sm font-medium text-white truncate\">\n\n              {schemaData.post_title ?? '(brak tytułu)'}\n\n            </p>\n\n            {schemaData.meta_description && (\n\n              <p className=\"text-xs text-gray-400 mt-1 line-clamp-2\">\n\n                {schemaData.meta_description}\n\n              </p>\n\n            )}\n\n          </div>\n\n\n\n\n\n\n\n          {/* Selected portal info — visible in portal mode */}\n\n          {!isManual && portalName && (\n\n            <div className=\"flex items-center gap-2 px-3 py-2 bg-violet-500/5 border border-violet-500/15 rounded-lg mb-4\">\n\n              <span className=\"text-xs text-violet-400\">🚀</span>\n\n              <span className=\"text-sm text-gray-200\">Publikujesz na: <span className=\"font-semibold\">{portalName}</span></span>\n\n              <span className=\"text-xs text-gray-500 ml-auto\">{portalUrl}</span>\n\n            </div>\n\n          )}\n\n\n\n\n\n\n\n          {/* Manual credentials — visible only when manual mode or no portals */}\n\n          {isManual && (\n\n            <>\n\n              {/* WP URL */}\n\n              <div>\n\n                <label className=\"block text-xs text-gray-400 mb-1.5\">URL portalu WordPress</label>\n\n                <input\n\n                  type=\"text\"\n\n                  value={wpUrl}\n\n                  onChange={(e) => setWpUrl(e.target.value)}\n\n                  placeholder=\"https://twojportal.pl\"\n\n                  className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors\"\n\n                />\n\n              </div>\n\n\n\n\n\n\n\n              {/* Credentials row */}\n\n              <div className=\"grid grid-cols-2 gap-3\">\n\n                <div>\n\n                  <label className=\"block text-xs text-gray-400 mb-1.5\">Użytkownik WP</label>\n\n                  <input\n\n                    type=\"text\"\n\n                    value={wpUser}\n\n                    onChange={(e) => setWpUser(e.target.value)}\n\n                    placeholder=\"admin\"\n\n                    className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors\"\n\n                  />\n\n                </div>\n\n                <div>\n\n                  <label className=\"block text-xs text-gray-400 mb-1.5\">Application Password</label>\n\n                  <input\n\n                    type=\"password\"\n\n                    value={wpPassword}\n\n                    onChange={(e) => setWpPassword(e.target.value)}\n\n                    placeholder=\"xxxx xxxx xxxx xxxx\"\n\n                    className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors\"\n\n                  />\n\n                </div>\n\n              </div>\n\n            </>\n\n          )}\n\n          {/* YouTube Channels */}\n\n          <div className=\"mb-4\">\n\n            <label className=\"block text-xs text-gray-400 mb-1.5\">Dodatkowo: Opublikuj opis na YouTube</label>\n\n            {ytChannels && ytChannels.length > 0 ? (\n\n              <div className=\"space-y-2 max-h-32 overflow-y-auto bg-gray-800/50 p-2 rounded-lg border border-gray-700\">\n\n                {ytChannels.map(ch => (\n\n                  <label key={ch.channel_id} className=\"flex items-center gap-2 cursor-pointer\">\n\n                    <input\n\n                      type=\"checkbox\"\n\n                      checked={selectedYtChannelIds.includes(ch.channel_id)}\n\n                      onChange={(e) => {\n\n                        if (e.target.checked) setSelectedYtChannelIds(p => [...p, ch.channel_id])\n\n                        else setSelectedYtChannelIds(p => p.filter(id => id !== ch.channel_id))\n\n                      }}\n\n                      className=\"accent-violet-500 rounded\"\n\n                    />\n\n                    <span className=\"text-sm text-gray-300\">{ch.channel_title}</span>\n\n                  </label>\n\n                ))}\n\n              </div>\n\n            ) : (\n\n              <div className=\"p-3 bg-gray-800/50 rounded-lg border border-gray-700\">\n\n                <p className=\"text-xs text-amber-500/90 flex items-center gap-1.5\">\n\n                  ⚠️ Brak podłączonych kanałów YouTube.\n\n                  <a href=\"/ustawienia\" target=\"_blank\" rel=\"noreferrer\" className=\"underline hover:text-amber-400 transition-colors ml-1\">\n\n                    Przejdź do ustawień\n\n                  </a>\n\n                </p>\n\n              </div>\n\n            )}\n\n            \n\n            {/* Podgląd opisu YT */}\n\n            {selectedYtChannelIds.length > 0 && ytChannels && ytChannels.length > 0 && (\n\n              <div className=\"mt-3\">\n\n                {!showYtPreview ? (\n\n                  <button\n\n                    onClick={() => setShowYtPreview(true)}\n\n                    className=\"text-xs text-violet-400 hover:text-violet-300 underline\"\n\n                  >\n\n                    Pokaż edytowalny podgląd opisu YT\n\n                  </button>\n\n                ) : (\n\n                  <div className=\"mt-2 animate-in slide-in-from-top-2\">\n\n                    <label className=\"block text-xs text-gray-400 mb-1\">\n\n                      Podgląd opisu YouTube <span className=\"text-gray-600\">(edytowalny)</span>\n\n                    </label>\n\n                    <textarea\n\n                      value={ytDescPreview}\n\n                      onChange={(e) => setYtDescPreview(e.target.value)}\n\n                      rows={6}\n\n                      className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-violet-500 resize-y font-mono\"\n\n                    />\n\n                    <button\n\n                      onClick={() => setShowYtPreview(false)}\n\n                      className=\"mt-1 text-xs text-gray-500 hover:text-gray-400\"\n\n                    >\n\n                      Ukryj podgląd\n\n                    </button>\n\n                  </div>\n\n                )}\n\n              </div>\n\n            )}\n\n\n\n          </div>\n\n\n\n\n\n\n\n          {/* Post ID + Status + Format */}\n\n          <div className=\"grid grid-cols-2 gap-3\">\n\n            <div>\n\n              <label className=\"block text-xs text-gray-400 mb-1.5\">\n\n                ID posta WP <span className=\"text-gray-600\">(puste = nowy post)</span>\n\n              </label>\n\n              <input\n\n                type=\"number\"\n\n                value={wpPostId}\n\n                onChange={(e) => setWpPostId(e.target.value)}\n\n                placeholder=\"Puste = nowy artykuł\"\n\n                className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors\"\n\n              />\n\n            </div>\n\n            <div>\n\n              <label className=\"block text-xs text-gray-400 mb-1.5\">Status publikacji</label>\n\n              <div className=\"flex gap-4 h-[42px] items-center\">\n\n                <label className=\"flex items-center gap-2 cursor-pointer\">\n\n                  <input\n\n                    type=\"radio\"\n\n                    name=\"modal_post_status\"\n\n                    value=\"draft\"\n\n                    checked={postStatus === 'draft'}\n\n                    onChange={() => setPostStatus('draft')}\n\n                    className=\"accent-violet-500\"\n\n                  />\n\n                  <span className=\"text-sm text-gray-300\">Szkic</span>\n\n                </label>\n\n                <label className=\"flex items-center gap-2 cursor-pointer\">\n\n                  <input\n\n                    type=\"radio\"\n\n                    name=\"modal_post_status\"\n\n                    value=\"publish\"\n\n                    checked={postStatus === 'publish'}\n\n                    onChange={() => setPostStatus('publish')}\n\n                    className=\"accent-violet-500\"\n\n                  />\n\n                  <span className=\"text-sm text-gray-300\">Publikuj</span>\n\n                </label>\n\n              </div>\n\n            </div>\n\n          </div>\n\n\n\n\n\n\n\n          {/* Format wpisu */}\n\n          <div>\n\n            <label className=\"block text-xs text-gray-400 mb-1.5\">Format wpisu WordPress</label>\n\n            <select\n\n              value={postFormat}\n\n              onChange={(e) => setPostFormat(e.target.value)}\n\n              className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer\"\n\n              style={{ backgroundImage: 'url(\"data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' fill=\\'none\\' viewBox=\\'0 0 20 20\\'%3E%3Cpath stroke=\\'%236b7280\\' stroke-linecap=\\'round\\' stroke-linejoin=\\'round\\' stroke-width=\\'1.5\\' d=\\'M6 8l4 4 4-4\\'/%3E%3C/svg%3E\")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.5rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }}\n\n            >\n\n              <option value=\"video\">🎬 Film (video)</option>\n\n              <option value=\"standard\">📄 Standard</option>\n\n              <option value=\"gallery\">🖼️ Galeria (gallery)</option>\n\n              <option value=\"quote\">💬 Cytat (quote)</option>\n\n            </select>\n\n            <p className=\"text-xs text-gray-600 mt-1\">Domyślnie: Film — optymalny dla treści video SEO</p>\n\n          </div>\n\n\n\n\n\n\n\n          {/* Publish button */}\n\n          <button\n\n            onClick={handlePublish}\n\n            disabled={publishing || (!isManual && !selectedPortalId && selectedYtChannelIds.length === 0) || (isManual && !wpUrl && selectedYtChannelIds.length === 0)}\n\n            className=\"w-full py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-xl font-semibold text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2\"\n\n          >\n\n            {publishing ? (\n\n              <><span className=\"animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full\" /> Publikowanie...</>\n\n            ) : (\n\n              <>🚀 Opublikuj na portalu</>\n\n            )}\n\n          </button>\n\n\n\n\n\n\n\n          {/* Result */}\n\n          {publishResult && (\n\n            <div\n\n              className={`p-4 rounded-xl text-sm ${\n\n                publishResult.error\n\n                  ? 'bg-red-500/10 border border-red-500/20 text-red-400'\n\n                  : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'\n\n              }`}\n\n            >\n\n              {publishResult.error ? (\n\n                <><span className=\"font-medium\">⚠️ Błąd:</span> {publishResult.error}</>\n\n              ) : (\n\n                <div className=\"space-y-1\">\n\n                  <p><span className=\"font-medium\">✔️ Sukces!</span>\n\n                    {publishResult.created ? ' Utworzono nowy artykuł' : ' Zaktualizowano artykuł'}\n\n                    {publishResult.wp_post_id && ` (ID: ${publishResult.wp_post_id})`}\n\n                  </p>\n\n                  {publishResult.post_url && (\n\n                    <a\n\n                      href={publishResult.post_url}\n\n                      target=\"_blank\"\n\n                      rel=\"noopener noreferrer\"\n\n                      className=\"inline-flex items-center gap-1 text-emerald-300 hover:text-emerald-200 underline underline-offset-2\"\n\n                    >\n\n                      Otwórz artykuł na portalu →\n\n                    </a>\n\n                  )}\n\n                </div>\n\n              )}\n\n            </div>\n\n          )}\n\n\n\n\n\n\n\n          <p className=\"text-xs text-gray-600 text-center\">\n\n            {isManual ? 'Dane logowania zapamiętane w przeglądarce (localStorage)' : 'Credentials pobrane z zapisanego portalu'}\n\n          </p>\n\n        </div>\n\n      </div>\n\n\n\n\n\n\n\n      {/* Animation keyframe */}\n\n      <style jsx>{`\n\n        @keyframes fadeInUp {\n\n          from { opacity: 0; transform: translateY(20px); }\n\n          to { opacity: 1; transform: translateY(0); }\n\n        }\n\n      `}</style>\n\n    </div>\n\n  )\n\n}\n\n\n\n\n\n\n\n\n\n\n\n// ─── AddPortalModal ─────────────────────────────────────────────────────────\n\n// D35 (2026-06-30, vse-dev-01): Dynamic profile dropdown + inline profile creation\n\n\n\n\n\n\n\nfunction AddPortalModal({\n\n  onClose,\n\n  onSuccess\n\n}: {\n\n  onClose: () => void\n\n  onSuccess: (portalId: string) => void\n\n}) {\n\n  const { createPortal } = usePortals()\n\n  const { profiles, loading: profilesLoading, createProfile } = useProfiles()\n\n\n\n\n\n\n\n  // Portal fields\n\n  const [name, setName] = useState('')\n\n  const [url, setUrl] = useState('https://')\n\n  const [wpUser, setWpUser] = useState('')\n\n  const [wpPassword, setWpPassword] = useState('')\n\n  const [profileId, setProfileId] = useState('')\n\n  const [saving, setSaving] = useState(false)\n\n  const [error, setError] = useState('')\n\n\n\n\n\n\n\n  // Inline profile creation fields\n\n  const [showNewProfileForm, setShowNewProfileForm] = useState(false)\n\n  const [newProfileBrand, setNewProfileBrand] = useState('')\n\n  const [newProfileType, setNewProfileType] = useState('analiza')\n\n  const [newProfileLang, setNewProfileLang] = useState('pl')\n\n  const [newProfileExtUrl, setNewProfileExtUrl] = useState('')\n\n  const [newProfileExtAnchor, setNewProfileExtAnchor] = useState('')\n\n\n\n\n\n\n\n  const modalRef = useRef<HTMLDivElement>(null)\n\n\n\n\n\n\n\n  // Set default profile when profiles load\n\n  useEffect(() => {\n\n    if (profiles.length > 0 && !profileId) {\n\n      setProfileId(profiles[0].id)\n\n    }\n\n  }, [profiles, profileId])\n\n\n\n\n\n\n\n  // Close on Escape\n\n  useEffect(() => {\n\n    const handler = (e: KeyboardEvent) => {\n\n      if (e.key === 'Escape') onClose()\n\n    }\n\n    window.addEventListener('keydown', handler)\n\n    return () => window.removeEventListener('keydown', handler)\n\n  }, [onClose])\n\n\n\n\n\n\n\n  const handleBackdropClick = (e: React.MouseEvent) => {\n\n    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {\n\n      onClose()\n\n    }\n\n  }\n\n\n\n\n\n\n\n  /** Slugify portal name to create a valid portal_id */\n\n  const slugify = (text: string): string =>\n\n    text.toLowerCase()\n\n      .replace(/[ąàáâãäå]/g, 'a').replace(/[ćčç]/g, 'c')\n\n      .replace(/[ęèéêë]/g, 'e').replace(/[ìíîï]/g, 'i')\n\n      .replace(/[łľ]/g, 'l').replace(/[ńñň]/g, 'n')\n\n      .replace(/[óòôõöő]/g, 'o').replace(/[śšş]/g, 's')\n\n      .replace(/[ùúûüű]/g, 'u').replace(/[ýÿ]/g, 'y')\n\n      .replace(/[źżž]/g, 'z').replace(/[đð]/g, 'd')\n\n      .replace(/[^\\w-]/g, '-').replace(/-+/g, '-')\n\n      .replace(/^-|-$/g, '')\n\n\n\n\n\n\n\n  const handleProfileDropdownChange = (value: string) => {\n\n    if (value === '__new__') {\n\n      setShowNewProfileForm(true)\n\n      setProfileId('__new__')\n\n    } else {\n\n      setShowNewProfileForm(false)\n\n      setProfileId(value)\n\n    }\n\n  }\n\n\n\n\n\n\n\n  const handleSave = async () => {\n\n    if (!name || !url || !wpUser || !wpPassword) {\n\n      setError('Uzupełnij wszystkie pola.')\n\n      return\n\n    }\n\n\n\n\n\n\n\n    // Validate new profile fields if creating inline\n\n    if (showNewProfileForm) {\n\n      if (!newProfileBrand.trim()) {\n\n        setError('Podaj nazwę brandu dla nowego profilu.')\n\n        return\n\n      }\n\n    }\n\n\n\n\n\n\n\n    setSaving(true)\n\n    setError('')\n\n\n\n\n\n\n\n    try {\n\n      let finalProfileId: string | null = null\n\n\n\n\n\n\n\n      if (showNewProfileForm) {\n\n        // Step 1: Create profile first\n\n        const portalSlug = slugify(name)\n\n        if (!portalSlug || portalSlug.length < 3) {\n\n          setError('Nazwa portalu jest za krótka (min. 3 znaki).')\n\n          setSaving(false)\n\n          return\n\n        }\n\n\n\n\n\n\n\n        const newProfile = await createProfile({\n\n          portal_id: portalSlug,\n\n          display_name: name.trim(),\n\n          site_brand: newProfileBrand.trim(),\n\n          wp_base_url: url.trim(),\n\n          default_type: newProfileType,\n\n          seo_language: newProfileLang,\n\n          seo_external_link_url: newProfileExtUrl.trim() || undefined,\n\n          seo_external_link_anchor: newProfileExtAnchor.trim() || undefined,\n\n        })\n\n\n\n\n\n\n\n        if (!newProfile) {\n\n          setError('Nie udało się utworzyć profilu. Sprawdź dane.')\n\n          setSaving(false)\n\n          return\n\n        }\n\n\n\n\n\n\n\n        finalProfileId = newProfile.id\n\n      } else {\n\n        finalProfileId = profileId === 'none' ? null : profileId\n\n      }\n\n\n\n\n\n\n\n      // Step 2: Create portal with profile\n\n      const created = await createPortal({\n\n        name,\n\n        url,\n\n        wp_username: wpUser,\n\n        wp_app_password: wpPassword,\n\n        profile_id: finalProfileId,\n\n      })\n\n\n\n\n\n\n\n      if (created) {\n\n        onSuccess(created.id)\n\n      } else {\n\n        setError('Nie udało się utworzyć portalu.')\n\n      }\n\n    } catch (e: unknown) {\n\n      setError(e instanceof Error ? e.message : 'Błąd podczas zapisu')\n\n    } finally {\n\n      setSaving(false)\n\n    }\n\n  }\n\n\n\n\n\n\n\n  const selectClass = \"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-violet-500 focus:outline-none cursor-pointer appearance-none\"\n\n  const selectStyle = { backgroundImage: 'url(\"data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' fill=\\'none\\' viewBox=\\'0 0 20 20\\'%3E%3Cpath stroke=\\'%236b7280\\' stroke-linecap=\\'round\\' stroke-linejoin=\\'round\\' stroke-width=\\'1.5\\' d=\\'M6 8l4 4 4-4\\'/%3E%3C/svg%3E\")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.5rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }\n\n  const inputClass = \"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-violet-500 focus:outline-none\"\n\n\n\n\n\n\n\n  return (\n\n    <div\n\n      className=\"fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm\"\n\n      onClick={handleBackdropClick}\n\n    >\n\n      <div\n\n        ref={modalRef}\n\n        className=\"w-full max-w-md bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden animate-in\"\n\n        style={{ animation: 'fadeInUp 0.25s ease-out', maxHeight: '90vh', overflowY: 'auto' }}\n\n      >\n\n        <div className=\"flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gradient-to-r from-violet-950/50 to-fuchsia-950/30\">\n\n          <h3 className=\"font-semibold text-white\">Dodaj nowy portal</h3>\n\n          <button onClick={onClose} className=\"text-gray-400 hover:text-white transition-colors p-1\">\n\n            <svg className=\"w-5 h-5\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\">\n\n              <path strokeLinecap=\"round\" strokeLinejoin=\"round\" strokeWidth={2} d=\"M6 18L18 6M6 6l12 12\" />\n\n            </svg>\n\n          </button>\n\n        </div>\n\n\n\n\n\n\n\n        <div className=\"px-6 py-5 space-y-4\">\n\n          {/* Portal name */}\n\n          <div>\n\n            <label className=\"block text-xs text-gray-400 mb-1.5\">Nazwa portalu</label>\n\n            <input\n\n              type=\"text\"\n\n              value={name}\n\n              onChange={(e) => setName(e.target.value)}\n\n              placeholder=\"np. BiznesCiti.com\"\n\n              className={inputClass}\n\n            />\n\n          </div>\n\n\n\n\n\n\n\n          {/* WordPress URL */}\n\n          <div>\n\n            <label className=\"block text-xs text-gray-400 mb-1.5\">URL WordPress</label>\n\n            <input\n\n              type=\"url\"\n\n              value={url}\n\n              onChange={(e) => setUrl(e.target.value)}\n\n              placeholder=\"https://twojportal.pl\"\n\n              className={inputClass}\n\n            />\n\n          </div>\n\n\n\n\n\n\n\n          {/* WP Username */}\n\n          <div>\n\n            <label className=\"block text-xs text-gray-400 mb-1.5\">Użytkownik WordPress</label>\n\n            <input\n\n              type=\"text\"\n\n              value={wpUser}\n\n              onChange={(e) => setWpUser(e.target.value)}\n\n              placeholder=\"admin\"\n\n              className={inputClass}\n\n            />\n\n          </div>\n\n\n\n\n\n\n\n          {/* Application Password */}\n\n          <div>\n\n            <label className=\"block text-xs text-gray-400 mb-1.5\">Application Password</label>\n\n            <input\n\n              type=\"password\"\n\n              value={wpPassword}\n\n              onChange={(e) => setWpPassword(e.target.value)}\n\n              placeholder=\"xxxx xxxx xxxx xxxx\"\n\n              className={inputClass}\n\n            />\n\n          </div>\n\n\n\n\n\n\n\n          {/* Profile Assignment Section */}\n\n          <div className=\"pt-2 border-t border-gray-800\">\n\n            <label className=\"block text-xs text-gray-400 mb-1.5\">\n\n              Profil SEO\n\n              <span className=\"text-gray-500 font-normal ml-1\">(opcjonalnie)</span>\n\n            </label>\n\n\n\n\n\n\n\n            <select\n\n              value={showNewProfileForm ? '__new__' : profileId}\n\n              onChange={(e) => handleProfileDropdownChange(e.target.value)}\n\n              disabled={profilesLoading}\n\n              className={selectClass}\n\n              style={selectStyle}\n\n            >\n\n              <option value=\"none\">Brak profilu</option>\n\n              {profiles.map((p) => (\n\n                <option key={p.id} value={p.id}>\n\n                  {p.display_name} ({p.portal_id})\n\n                </option>\n\n              ))}\n\n              <option value=\"__new__\">+ Utwórz nowy profil dla tego portalu</option>\n\n            </select>\n\n            <p className=\"text-xs text-gray-600 mt-1\">\n\n              Profil definiuje styl SEO (język, link zewnętrzny, brand).\n\n            </p>\n\n          </div>\n\n\n\n\n\n\n\n          {/* Inline Profile Creation Fields */}\n\n          {showNewProfileForm && (\n\n            <div className=\"space-y-3 p-3 bg-violet-950/20 border border-violet-800/30 rounded-xl animate-in\" style={{ animation: 'fadeInUp 0.2s ease-out' }}>\n\n              <p className=\"text-xs font-medium text-violet-300\">Konfiguracja nowego profilu:</p>\n\n\n\n\n\n\n\n              <div>\n\n                <label className=\"block text-xs text-gray-400 mb-1\">Nazwa brandu *</label>\n\n                <input\n\n                  type=\"text\"\n\n                  value={newProfileBrand}\n\n                  onChange={(e) => setNewProfileBrand(e.target.value)}\n\n                  placeholder=\"np. BiznesCiti\"\n\n                  className={inputClass}\n\n                />\n\n              </div>\n\n\n\n\n\n\n\n              <div className=\"grid grid-cols-2 gap-2\">\n\n                <div>\n\n                  <label className=\"block text-xs text-gray-400 mb-1\">Domyślny typ</label>\n\n                  <select\n\n                    value={newProfileType}\n\n                    onChange={(e) => setNewProfileType(e.target.value)}\n\n                    className={selectClass}\n\n                    style={selectStyle}\n\n                  >\n\n                    <option value=\"analiza\">Analiza</option>\n\n                    <option value=\"felieton\">Felieton</option>\n\n                    <option value=\"wywiad\">Wywiad</option>\n\n                    <option value=\"news\">News</option>\n\n                  </select>\n\n                </div>\n\n                <div>\n\n                  <label className=\"block text-xs text-gray-400 mb-1\">Język SEO</label>\n\n                  <select\n\n                    value={newProfileLang}\n\n                    onChange={(e) => setNewProfileLang(e.target.value)}\n\n                    className={selectClass}\n\n                    style={selectStyle}\n\n                  >\n\n                    <option value=\"pl\">Polski (PL)</option>\n\n                    <option value=\"en\">English (EN)</option>\n\n                    <option value=\"de\">Deutsch (DE)</option>\n\n                    <option value=\"es\">Español (ES)</option>\n\n                  </select>\n\n                </div>\n\n              </div>\n\n\n\n\n\n\n\n              <div>\n\n                <label className=\"block text-xs text-gray-400 mb-1\">Link zewnętrzny (URL)</label>\n\n                <input\n\n                  type=\"url\"\n\n                  value={newProfileExtUrl}\n\n                  onChange={(e) => setNewProfileExtUrl(e.target.value)}\n\n                  placeholder=\"https://partner.com\"\n\n                  className={inputClass}\n\n                />\n\n              </div>\n\n\n\n\n\n\n\n              <div>\n\n                <label className=\"block text-xs text-gray-400 mb-1\">Anchor linku zewnętrznego</label>\n\n                <input\n\n                  type=\"text\"\n\n                  value={newProfileExtAnchor}\n\n                  onChange={(e) => setNewProfileExtAnchor(e.target.value)}\n\n                  placeholder=\"np. Dowiedz się więcej\"\n\n                  className={inputClass}\n\n                />\n\n              </div>\n\n            </div>\n\n          )}\n\n\n\n\n\n\n\n          {/* Error display */}\n\n          {error && (\n\n            <p className=\"text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-2.5\">\n\n              {error}\n\n            </p>\n\n          )}\n\n\n\n\n\n\n\n          {/* Action buttons */}\n\n          <div className=\"flex gap-2 pt-2\">\n\n            <button\n\n              type=\"button\"\n\n              onClick={onClose}\n\n              className=\"flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 text-sm font-medium rounded-xl transition-colors\"\n\n            >\n\n              Anuluj\n\n            </button>\n\n            <button\n\n              type=\"button\"\n\n              onClick={handleSave}\n\n              disabled={saving}\n\n              className=\"flex-1 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:opacity-90 disabled:opacity-50 text-white text-sm font-medium rounded-xl transition-all flex items-center justify-center gap-2\"\n\n            >\n\n              {saving ? (\n\n                <><span className=\"animate-spin inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full\" /> Zapisywanie...</>\n\n              ) : (\n\n                'Zapisz portal'\n\n              )}\n\n            </button>\n\n          </div>\n\n        </div>\n\n      </div>\n\n    </div>\n\n  )\n\n}\n\n\n\n\n\n\n\n/**\n\n * CO: ManageSubscriptionLink — link do Stripe Customer Portal\n\n * PO CO: Umożliwia użytkownikom z płatnym planem zarządzanie subskrypcją\n\n *        (zmiana karty, anulowanie, historia faktur).\n\n * JAK: POST /v1/stripe/customer-portal → zwraca URL portalu Stripe → redirect.\n\n */\n\nfunction ManageSubscriptionLink({ accessToken }: { accessToken?: string }) {\n\n  const [loading, setLoading] = useState(false)\n\n  const [error, setError] = useState<string | null>(null)\n\n\n\n\n\n\n\n  const handleClick = async () => {\n\n    setLoading(true)\n\n    setError(null)\n\n    try {\n\n      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''\n\n      const res = await fetch(`${apiUrl}/v1/stripe/customer-portal`, {\n\n        method: 'POST',\n\n        headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },\n\n      })\n\n      const data = await res.json()\n\n      if (data.portal_url) {\n\n        window.location.href = data.portal_url\n\n      } else {\n\n        setError(data.error || 'Nie udało się otworzyć portalu subskrypcji')\n\n      }\n\n    } catch {\n\n      setError('Błąd połączenia z portalem subskrypcji')\n\n    } finally {\n\n      setLoading(false)\n\n    }\n\n  }\n\n\n\n\n\n\n\n  return (\n\n    <div className=\"mt-2\">\n\n      <button\n\n        onClick={handleClick}\n\n        disabled={loading}\n\n        className=\"text-xs text-violet-400 hover:text-violet-300 underline underline-offset-2 transition-colors disabled:opacity-50\"\n\n      >\n\n        {loading ? 'Ładowanie portalu...' : '⚙️ Zarządzaj subskrypcją'}\n\n      </button>\n\n      {error && <p className=\"text-xs text-red-400 mt-1\">{error}</p>}\n\n    </div>\n\n  )\n\n}\n\n\n\n\n\n\n\n// ─── Main Component ─────────────────────────────────────────────────────────\n\n\n\nfunction buildYtDescription(schema: SchemaData | null): string {\n  if (!schema) return ''\n  const parts: string[] = []\n\n  // 1. Hook / lead\n  if (schema.lead) {\n    parts.push(schema.lead.trim())\n  } else if (schema.meta_description) {\n    parts.push(schema.meta_description.trim())\n  }\n\n  // 2. Chapters / timestamps\n  const chapters = extractChapters(schema)\n  if (chapters.length > 0) {\n    const chapLines = chapters\n      .map(c => `${secToTimestamp(c.startOffset ?? c.time)} ${c.name ?? c.label ?? ''}`.trim())\n      .filter(l => l.length > 5)\n    if (chapLines.length > 0) {\n      parts.push('Rozdziały:\\n' + chapLines.join('\\n'))\n    }\n  }\n\n  // 3. Quotes / highlights\n  if (Array.isArray(schema.quotes) && schema.quotes.length > 0) {\n    const quoteLines = schema.quotes\n      .slice(0, 3)\n      .map(q => `💬 \"${q.text}\"${q.author ? ` — ${q.author}` : ''}`)\n    parts.push(quoteLines.join('\\n'))\n  }\n\n  // 4. FAQ / key points\n  const faq = extractFaq(schema)\n  if (faq.length > 0) {\n    const faqLines = faq\n      .slice(0, 3)\n      .map(f => `❓ ${f.question}\\n${f.answer}`)\n    parts.push(faqLines.join('\\n\\n'))\n  }\n\n  // 5. Hashtags\n  if (schema.focus_keyphrase) {\n    const tags = schema.focus_keyphrase\n      .split(',')\n      .map(t => '#' + t.trim().replace(/\\s+/g, ''))\n      .filter(t => t.length > 1)\n      .slice(0, 5)\n    if (tags.length > 0) parts.push(tags.join(' '))\n  }\n\n  return parts.join('\\n\\n')\n}\n\n\n\n\n\n\n\nexport default function DashboardInner() {\n\n  const router = useRouter()\n\n  /**\n\n   * CO: Auth guard i dane sesji\n\n   * PO CO: Zapewnia dostęp tylko zalogowanym użytkownikom.\n\n   * JAK: useSession z NextAuth → auth guard. Stan lokalny dla URL, wyników, plan usera.\n\n   */\n\n  const { data: session, status } = useSession()\n\n  const accessToken = (session as any)?.accessToken\n\n  // Global loader z informacjami o aktywnym jobie w Redis (job-08)\n\n  const { activeJob, dismissBanner } = useJobLoader()\n\n\n\n\n\n\n\n  // Portals hook (D34, vse-dev-01)\n\n  const { portals, loading: portalsLoading, refresh: refreshPortals } = usePortals()\n\n\n\n\n\n\n\n  const [url, setUrl] = useState('')\n\n  const [loading, setLoading] = useState(false)\n\n  const [error, setError] = useState<string | null>(null)\n\n  const [result, setResult] = useState<GenerateResponse | null>(null)\n\n  const [activeTab, setActiveTab] = useState<TabKey>('schema')\n\n  const [copiedKey, setCopiedKey] = useState<CopiedKey>(null)\n\n  const [userProfile, setUserProfile] = useState<UserProfile | null>(null)\n\n\n\n\n\n\n\n  // D34 (2026-06-30): Portal selector state\n\n  const [selectedPortalId, setSelectedPortalId] = useState<string>('')\n\n  const [showAddPortalModal, setShowAddPortalModal] = useState(false)\n\n\n\n  // ShortMachine — stan UI (2026-08-20, shadow-dev-01)\n  const [smYoutubeId, setSmYoutubeId] = useState<string>('')\n  const [smCustomQuery, setSmCustomQuery] = useState<string>('')\n  const [smCountEmotional, setSmCountEmotional] = useState<number>(3)\n  const [smCountProfessional, setSmCountProfessional] = useState<number>(3)\n  const [smCountCustom, setSmCountCustom] = useState<number>(0)\n  const [smCandidates, setSmCandidates] = useState<any[]>([])\n  const [smPreviewIdx, setSmPreviewIdx] = useState<number | null>(null)\n  const [smTitles, setSmTitles] = useState<Record<number, string>>({})\n  const [smTags, setSmTags] = useState<Record<number, string[]>>({})\n  const [smTitleLoading, setSmTitleLoading] = useState<Record<number, boolean>>({})\n\n  // ShortMachine state restoration (2026-08-20, shadow-dev-01)\n  useEffect(() => {\n    if (!smYoutubeId) return;\n    const apiBase = process.env.NEXT_PUBLIC_API_URL || '';\n    fetch(`${apiBase}/v1/shorts/candidates?youtube_id=${encodeURIComponent(smYoutubeId)}`)\n      .then(r => r.json())\n      .then(data => {\n        if (data.candidates && data.candidates.length > 0) {\n          setSmCandidates(data.candidates);\n        }\n        if (data.jobs && data.jobs.length > 0 && data.candidates) {\n          const restoredStatus: Record<number, any> = {};\n          data.jobs.forEach((job: any) => {\n            const idx = data.candidates.findIndex(\n              (c: any) => Math.abs(c.start_sec - job.start_sec) < 1 &&\n                          Math.abs(c.end_sec - job.end_sec) < 1\n            );\n            if (idx >= 0) {\n              restoredStatus[idx] = {\n                status: job.status,\n                result_paths: job.result_paths,\n                job_id: job.id,\n                error: job.error,\n              };\n            }\n          });\n          if (Object.keys(restoredStatus).length > 0) {\n            setSmJobStatus(prev => ({ ...restoredStatus, ...prev }));\n          }\n        }\n      })\n      .catch(err => console.warn('Failed to restore ShortMachine state:', err));\n  }, [smYoutubeId]); // NIE dodawaj smCandidates do deps - petla re-fetch\n  const [smLoading, setSmLoading] = useState(false);\n  const [smError, setSmError] = useState<string | null>(null);\n  const [smRenderConfig, setSmRenderConfig] = useState<Record<number, {format: string, subtitles: string}>>({});\n  const [smJobStatus, setSmJobStatus] = useState<Record<number, any>>({});\n  const [smTrimAdj, setSmTrimAdj] = useState<Record<number, {startDelta: number; endDelta: number}>>({});\n  const [smExpandedIdx, setSmExpandedIdx] = useState<number | null>(null);\n  const [smTrimMode, setSmTrimMode] = useState<'start' | 'end'>('start');\n  const [smSelected, setSmSelected] = useState<Set<number>>(new Set());\n  const [smFormat, setSmFormat] = useState<'raw' | 'short'>('raw');\n\n  const toggleSmSelected = (idx: number) => setSmSelected(prev => {\n    const next = new Set(prev);\n    if (next.has(idx)) next.delete(idx); else next.add(idx);\n    return next;\n  });\n\n  const [smTargetYtId, setSmTargetYtId] = useState<Record<number, string>>({});\n  const [smPublishAt, setSmPublishAt] = useState<Record<number, string>>({});\n  const [smPrivacyStatus, setSmPrivacyStatus] = useState<Record<number, string>>({});\n  const [smSelectedPlaylist, setSmSelectedPlaylist] = useState<Record<number, string>>({});\n  const [smPlaylists, setSmPlaylists] = useState<{id: string, title: string}[]>([]);\n  const [smModalOpenFor, setSmModalOpenFor] = useState<number | null>(null);\n\n  const [ytChannels, setYtChannels] = useState<any[]>([])\n\n  useEffect(() => {\n    const channelId = ytChannels[0]?.channel_id;\n    if (!channelId) {\n      setSmPlaylists([]);\n      return;\n    }\n    const apiBase = process.env.NEXT_PUBLIC_API_URL || '';\n    fetch(`${apiBase}/v1/youtube/channels/${channelId}/playlists`)\n      .then(r => r.json())\n      .then(data => { if (Array.isArray(data)) setSmPlaylists(data); })\n      .catch(err => console.warn('Failed to load playlists:', err));\n  }, [ytChannels]);\n\n\n  const fmtSec = (sec: number) => `${Math.floor(sec/60)}:${String(Math.floor(sec%60)).padStart(2,'0')}`;\n  const getAdj = (idx: number, c: any) => ({ start: (c.start_sec??0)+(smTrimAdj[idx]?.startDelta??0), end: (c.end_sec??0)+(smTrimAdj[idx]?.endDelta??0) });\n\n  const handleRegenerateTitle = async (i: number, c: any) => {\n    const adj = getAdj(i, c)\n    const apiBase = process.env.NEXT_PUBLIC_API_URL || ''\n    setSmTitleLoading(p => ({...p, [i]: true}))\n    try {\n      const res = await fetch(`${apiBase}/v1/shorts/title`, {\n        method: 'POST',\n        headers: {'Content-Type': 'application/json'},\n        body: JSON.stringify({youtube_id: smYoutubeId, start_sec: adj.start, end_sec: adj.end})\n      })\n      const data = await res.json()\n      if (data.title) setSmTitles(p => ({...p, [i]: data.title}))\n      if (data.tags?.length) setSmTags(p => ({...p, [i]: data.tags}))\n    } finally {\n      setSmTitleLoading(p => ({...p, [i]: false}))\n    }\n  }\n\n  useEffect(() => {\n    if (typeof window === 'undefined') return\n    if ((window as any).YT) return\n    const tag = document.createElement('script')\n    tag.src = 'https://www.youtube.com/iframe_api'\n    document.head.appendChild(tag)\n  }, [])\n\n\n\n  const [showInjectModal, setShowInjectModal] = useState(false)\n\n\n\n  const [ytModalOpen, setYtModalOpen] = useState(false)\n\n\n\n  useEffect(() => {\n\n\n\n    if (!session?.accessToken) return\n\n\n\n    fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/v1/youtube/channels`, {\n\n\n\n      headers: { Authorization: `Bearer ${session.accessToken}` }\n\n\n\n    })\n\n\n\n      .then((r) => r.ok ? r.json() : [])\n\n\n\n      .then((data) => setYtChannels(Array.isArray(data) ? data : []))\n\n\n\n      .catch(() => setYtChannels([]))\n\n\n\n  }, [session?.accessToken])\n\n\n\n  // Portal selector + publication type\n\n  const [publicationType, setPublicationType] = useState<string>('analiza')\n\n  const [focusKeywordOverride, setFocusKeywordOverride] = useState<string>('')\n\n  const [isRefreshingUsage, setIsRefreshingUsage] = useState<boolean>(false)\n\n\n\n\n\n\n\n  // Set default portal when portals load\n\n  useEffect(() => {\n\n    if (portals.length > 0 && !selectedPortalId) {\n\n      setSelectedPortalId(portals[0].id)\n\n    }\n\n  }, [portals, selectedPortalId])\n\n\n\n\n\n\n\n  // Update publicationType when selected portal changes\n\n  useEffect(() => {\n\n    if (selectedPortalId && selectedPortalId !== '__manual__') {\n\n      const portal = portals.find((p) => p.id === selectedPortalId)\n\n      if (portal?.profile?.default_type) {\n\n        setPublicationType(portal.profile.default_type)\n\n      }\n\n    }\n\n  }, [selectedPortalId, portals])\n\n\n\n\n\n\n\n  /**\n\n   * Fetch user profile (plan info + usage quota)\n\n   * PO CO: Wyświetla nazwę planu (np. \"Free Tier\", \"Pro\") i stan limitu miesięcznego\n\n   *        z informacją ile wygenerowań zostało.\n\n   */\n\n  const fetchUserProfile = useCallback(async () => {\n\n    try {\n\n      setIsRefreshingUsage(true)\n\n      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''\n\n      const res = await fetch(`${apiUrl}/v1/users/me`, {\n\n        headers: {\n\n          ...(accessToken && { Authorization: `Bearer ${accessToken}` }),\n\n        },\n\n      })\n\n      if (res.ok) {\n\n        const data: UserProfile = await res.json()\n\n        setUserProfile(data)\n\n      }\n\n    } catch {\n\n      // Silently fail — profile badge will just not show\n\n    } finally {\n\n      setIsRefreshingUsage(false)\n\n    }\n\n  }, [accessToken])\n\n\n\n\n\n\n\n  useEffect(() => {\n\n    if (status === 'authenticated') {\n\n      fetchUserProfile()\n\n    }\n\n  }, [status, fetchUserProfile])\n\n\n\n\n\n\n\n  /**\n\n   * Kopiowanie do schowka z feedbackiem\n\n   */\n\n  const handleCopy = (text: string, id: string) => {\n\n    navigator.clipboard.writeText(text).then(() => {\n\n      setCopiedKey(id)\n\n      setTimeout(() => setCopiedKey(null), 2000)\n\n    })\n\n  }\n\n\n\n\n\n\n\n  /**\n\n   * Submit formularza — POST /v1/generate\n\n   * D34: Przekazuje portal_id, publication_type, focus_keyword do backendu\n\n   */\n\n  const handleSubmit = async (e: React.FormEvent) => {\n\n    e.preventDefault()\n\n    if (!url.trim()) return\n\n\n\n    setLoading(true)\n\n    setError(null)\n\n    setResult(null)\n\n\n\n    try {\n\n      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''\n\n      const body: Record<string, unknown> = { video_url: url.trim() }\n\n\n\n      // Pass portal_id if a saved portal is selected\n\n      if (selectedPortalId && selectedPortalId !== '__manual__') {\n\n        body.portal_id = selectedPortalId\n\n      }\n\n\n\n      // Pass publication_type if set\n\n      if (publicationType) {\n\n        body.publication_type = publicationType\n\n      }\n\n\n\n      // Pass focus_keyword if user entered an override\n\n      if (focusKeywordOverride.trim()) {\n\n        body.focus_keyword = focusKeywordOverride.trim()\n\n      }\n\n\n\n      const res = await fetch(`${apiUrl}/v1/generate`, {\n\n        method: 'POST',\n\n        headers: {\n\n          'Content-Type': 'application/json',\n\n          ...(accessToken && { Authorization: `Bearer ${accessToken}` }),\n\n        },\n\n        body: JSON.stringify(body),\n\n      })\n\n\n\n      let data: GenerateResponse\n\n      try {\n\n        data = await res.json()\n\n      } catch {\n\n        throw new Error(`Błąd serwera: HTTP ${res.status}`)\n\n      }\n\n\n\n      if (!res.ok) {\n\n        throw new Error(data.error || `HTTP ${res.status}: ${res.statusText}`)\n\n      }\n\n\n\n      if (data.status === 'error') {\n\n        throw new Error(data.error || 'Nieznany błąd generatora')\n\n      }\n\n\n\n      setResult(data)\n\n      setActiveTab('schema')\n\n      // Refresh usage quota after successful generation\n\n      fetchUserProfile()\n\n    } catch (err: unknown) {\n\n      setError(err instanceof Error ? err.message : 'Wystąpił błąd połączenia z API')\n\n    } finally {\n\n      setLoading(false)\n\n    }\n\n  }\n\n\n\n\n\n\n\n  // Auth redirect\n\n  if (status === 'unauthenticated') {\n\n    router.push('/login')\n\n    return null\n\n  }\n\n\n\n\n\n\n\n  if (status === 'loading') {\n\n    return (\n\n      <div className=\"min-h-screen bg-black flex items-center justify-center\">\n\n        <div className=\"animate-spin rounded-full h-8 w-8 border-b-2 border-violet-500\" />\n\n      </div>\n\n    )\n\n  }\n\n\n\n\n\n\n\n  const schema = result?.schema_data\n\n  const chapters = extractChapters(schema)\n\n  const faq = extractFaq(schema)\n\n  const schemaJsonString = schema ? JSON.stringify(schema, null, 2) : ''\n\n  const schemaScriptTag = schemaToScriptTag(schema ?? null)\n\n  const usageUsed = userProfile?.usage?.used_this_month ?? 0
  const usageQuota = userProfile?.usage?.quota ?? 0
  const planLabel = userProfile?.plan?.display_name ?? 'Plan Free'

  const isProOrAgency =

    userProfile?.plan?.id === 'pro' || userProfile?.plan?.id === 'agency'



  return (

    <ErrorBoundary>

    <div className="min-h-screen bg-black text-gray-100 flex">

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
          {/* Usage bar */}
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
          {/* Plan actions — Stripe integration */}
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

      {/* Main content area */}
      <div className="ml-64 flex-1 min-h-screen flex flex-col">
        {/* D32: Email verification banner for unverified accounts */}

        {userProfile && userProfile.is_verified === false && (

          <EmailVerificationBanner email={userProfile.email} />

        )}







        {/* Active Job Alert Banner (job-08) */}

        {activeJob && (

          <div className="bg-gradient-to-r from-violet-950/80 via-purple-900/60 to-violet-950/80 border-b border-violet-500/30 px-4 py-2.5">

            <div className="max-w-6xl mx-auto flex items-center justify-between gap-3">

              <div className="flex items-center gap-2.5 min-w-0">

                <span className="inline-block w-2 h-2 rounded-full bg-violet-400 animate-pulse shrink-0" />

                <p className="text-xs text-violet-200 truncate">

                  <span className="font-semibold text-violet-100">Przetwarzanie w toku:</span>{' '}

                  {activeJob.current_step || 'Analiza wideo...'} ({activeJob.progress}%)

                  {activeJob.video_id && (

                    <span className="text-violet-400 ml-1 font-mono">[{activeJob.video_id}]</span>

                  )}

                </p>

              </div>

              <div className="flex items-center gap-2 shrink-0">

                <div className="w-24 bg-violet-950 rounded-full h-1.5 border border-violet-800/50 overflow-hidden">

                  <div

                    className="bg-gradient-to-r from-violet-500 to-fuchsia-500 h-full transition-all duration-300"

                    style={{ width: `${activeJob.progress}%` }}

                  />

                </div>

                <button

                  onClick={dismissBanner}

                  className="text-violet-400 hover:text-violet-200 text-xs px-1"

                  title="Zamknij powiadomienie"

                >

                  ✕

                </button>

              </div>

            </div>

          </div>

        )}

        {/* Main content */}

        <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-8">

        {/* Hero / Input Section */}

        <div className="mb-8">

          <div className="mb-6">

            <h1 className="text-2xl font-bold text-white tracking-tight">

              Generuj Video SEO

            </h1>

            <p className="text-sm text-gray-400 mt-1">

              Wklej link do filmu YouTube — otrzymasz zoptymalizowany schemat JSON-LD, artykuł SEO i znaczniki czasu.

            </p>

          </div>







          {/* Form */}

          <form onSubmit={handleSubmit} className="space-y-3">

            <div className="flex gap-2">

              <input

                type="url"

                value={url}

                onChange={(e) => setUrl(e.target.value)}

                placeholder="https://www.youtube.com/watch?v=... lub https://youtu.be/..."

                required

                disabled={loading}

                className="flex-1 bg-gray-900 border border-gray-800 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors disabled:opacity-50"

              />

              <button

                type="submit"

                disabled={loading || !url.trim()}

                className="px-6 py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm rounded-xl transition-all shadow-lg shadow-violet-500/20 flex items-center gap-2 shrink-0"

              >

                {loading ? (

                  <>

                    <span className="animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" />

                    <span>Generuję...</span>

                  </>

                ) : (

                  <>

                    <span>⚡</span>

                    <span>Generuj SEO</span>

                  </>

                )}

              </button>

            </div>







            {/* D34: Portal selector bar */}

            <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">

              {/* Portal dropdown */}

              <div className="flex items-center gap-1.5 bg-gray-900/80 border border-gray-800 rounded-lg px-2.5 py-1.5">

                <span className="text-gray-400">Portal:</span>

                <select

                  value={selectedPortalId}

                  onChange={(e) => {

                    if (e.target.value === '__add_new__') {

                      setShowAddPortalModal(true)

                    } else {

                      setSelectedPortalId(e.target.value)

                    }

                  }}

                  disabled={portalsLoading || loading}

                  className="bg-transparent text-white font-medium focus:outline-none cursor-pointer pr-1"

                >

                  {portals.length === 0 && (

                    <option value="" className="bg-gray-900 text-gray-400">Brak portali (tryb ręczny)</option>

                  )}

                  {portals.map((portal) => (

                    <option key={portal.id} value={portal.id} className="bg-gray-900 text-white">

                      {portal.name} {portal.profile ? `[${portal.profile.portal_id}]` : ''}

                    </option>

                  ))}

                  <option value="__manual__" className="bg-gray-900 text-gray-400">Tryb ręczny (bez portalu)</option>

                  <option value="__add_new__" className="bg-gray-900 text-violet-400">+ Dodaj portal...</option>

                </select>

              </div>







              {/* Publication type dropdown */}

              <div className="flex items-center gap-1.5 bg-gray-900/80 border border-gray-800 rounded-lg px-2.5 py-1.5">

                <span className="text-gray-400">Format:</span>

                <select

                  value={publicationType}

                  onChange={(e) => setPublicationType(e.target.value)}

                  disabled={loading}

                  className="bg-transparent text-white font-medium focus:outline-none cursor-pointer"

                >

                  <option value="analiza" className="bg-gray-900 text-white">Analiza</option>

                  <option value="felieton" className="bg-gray-900 text-white">Felieton</option>

                  <option value="wywiad" className="bg-gray-900 text-white">Wywiad</option>

                  <option value="news" className="bg-gray-900 text-white">News</option>

                </select>

              </div>







              {/* Focus keyword override input */}

              <div className="flex items-center gap-1.5 bg-gray-900/80 border border-gray-800 rounded-lg px-2.5 py-1.5 flex-1 min-w-[180px]">

                <span className="text-gray-400 shrink-0">Fraza kluczowa:</span>

                <input

                  type="text"

                  value={focusKeywordOverride}

                  onChange={(e) => setFocusKeywordOverride(e.target.value)}

                  placeholder="opcjonalnie (auto jeśli puste)"

                  disabled={loading}

                  className="bg-transparent text-white placeholder-gray-600 focus:outline-none w-full text-xs"

                />

              </div>

            </div>

          </form>







          {/* Loading indicator */}

          {loading && (

            <div className="mt-4 p-4 bg-gray-900/50 border border-gray-800 rounded-xl">

              <div className="flex items-center gap-3">

                <span className="animate-spin inline-block w-4 h-4 border-2 border-violet-500/30 border-t-violet-500 rounded-full" />

                <div className="text-xs text-gray-400">

                  <span className="text-white font-medium">Pobieranie transkrypcji i generowanie SEO...</span>

                  <span className="ml-2 text-gray-500">Zwykle trwa 15-30 sekund.</span>

                </div>

              </div>

            </div>

          )}







          {/* Error display */}

          {error && (

            <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-start gap-2">

              <span className="text-base shrink-0">⚠️</span>

              <div>

                <p className="font-medium">Błąd generowania</p>

                <p className="text-xs text-red-400/80 mt-0.5">{error}</p>

              </div>

            </div>

          )}

        </div>







        {/* Results Section */}

        {result && schema && (

          <div>

            {/* Result Meta Bar */}

            <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-800">

              <div className="flex items-center gap-3">

                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full">

                  ✓ Wygenerowano

                </span>

                {result.video_id && (

                  <span className="text-xs text-gray-500 font-mono">

                    ID: {result.video_id}

                  </span>

                )}

                {result.processing_time_s != null && (

                  <span className="text-xs text-gray-500">

                    ⏱️ {result.processing_time_s.toFixed(1)}s

                  </span>

                )}

              </div>







              {/* WordPress inject button — always visible for Pro/Agency */}

              <button

                onClick={() => setShowInjectModal(true)}

                className="px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 text-white text-xs font-semibold rounded-xl transition-all shadow-lg shadow-violet-500/15 flex items-center gap-1.5"

              >

                <span>🚀</span>

                <span>Publikuj na WordPress</span>

              </button>

            </div>







            {/* Tab Bar */}

            <TabBar

              active={activeTab}

              onChange={setActiveTab}

              chaptersCount={chapters.length}

              faqCount={faq.length}

            />







            {/* Tab: Schemat */}

            {activeTab === 'schema' && (

              <div className="space-y-4">

                {/* Focus keyphrase */}

                {schema.focus_keyphrase && (

                  <ResultSection

                    title="Fraza kluczowa (Focus Keyphrase)"

                    copyText={schema.focus_keyphrase}

                    copyId="focus_keyphrase"

                    copiedKey={copiedKey}

                    onCopy={handleCopy}

                  >

                    <p className="text-sm font-mono text-violet-300 font-semibold">

                      {schema.focus_keyphrase}

                    </p>

                  </ResultSection>

                )}







                {/* Post title */}

                {schema.post_title && (

                  <ResultSection

                    title="Tytuł posta (SEO Title)"

                    copyText={schema.post_title}

                    copyId="post_title"

                    copiedKey={copiedKey}

                    onCopy={handleCopy}

                  >

                    <p className="text-sm text-gray-100 font-medium">{schema.post_title}</p>

                  </ResultSection>

                )}







                {/* Meta description */}

                {schema.meta_description && (

                  <ResultSection

                    title="Meta Description"

                    copyText={schema.meta_description}

                    copyId="meta_description"

                    copiedKey={copiedKey}

                    onCopy={handleCopy}

                    badge={`${schema.meta_description.length} zn.`}

                  >

                    <p className="text-sm text-gray-300 leading-relaxed">

                      {schema.meta_description}

                    </p>

                  </ResultSection>

                )}







                {/* WP slug */}

                {schema.wp_slug && (

                  <ResultSection

                    title="Uproszczona nazwa (Slug URL)"

                    copyText={schema.wp_slug}

                    copyId="wp_slug"

                    copiedKey={copiedKey}

                    onCopy={handleCopy}

                  >

                    <p className="text-sm font-mono text-gray-400">/{schema.wp_slug}</p>

                  </ResultSection>

                )}







                {/* Full Schema Script Tag */}

                <ResultSection

                  title="Kod skryptu Schema JSON-LD (<script> tag)"

                  copyText={schemaScriptTag}

                  copyId="schema_script_tag"

                  copiedKey={copiedKey}

                  onCopy={handleCopy}

                  badge="Gotowy do wklejenia w <head>"

                >

                  <pre className="text-xs font-mono text-gray-300 bg-gray-950 p-3 rounded-lg overflow-x-auto max-h-60 border border-gray-800">

                    {schemaScriptTag}

                  </pre>

                </ResultSection>







                {/* Raw JSON */}

                <ResultSection

                  title="Czysty JSON Schema (bez tagu <script>)"

                  copyText={schemaJsonString}

                  copyId="schema_raw_json"

                  copiedKey={copiedKey}

                  onCopy={handleCopy}

                >

                  <pre className="text-xs font-mono text-gray-300 bg-gray-950 p-3 rounded-lg overflow-x-auto max-h-60 border border-gray-800">

                    {schemaJsonString}

                  </pre>

                </ResultSection>

              </div>

            )}







            {/* Tab: Artykuł */}

            {activeTab === 'article' && (

              <div className="space-y-4">

                {/* Copy full article button banner */}

                <div className="flex justify-end mb-2">

                  <CopyButton

                    text={articleToText(schema, faq)}

                    id="full_article"

                    copiedKey={copiedKey}

                    onCopy={handleCopy}

                    label="📋 Kopiuj cały artykuł"

                  />

                </div>







                {/* Lead */}

                {schema.lead && (

                  <ResultSection

                    title="Lead / Wprowadzenie"

                    copyText={schema.lead}

                    copyId="lead"

                    copiedKey={copiedKey}

                    onCopy={handleCopy}

                  >

                    <p className="text-sm text-gray-200 leading-relaxed italic border-l-2 border-violet-500 pl-3">

                      {schema.lead}

                    </p>

                  </ResultSection>

                )}







                {/* Article body */}

                {schema.article_body && (

                  <ResultSection

                    title="Treść artykułu"

                    copyText={schema.article_body}

                    copyId="article_body"

                    copiedKey={copiedKey}

                    onCopy={handleCopy}

                  >

                    <div className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap font-sans">

                      {schema.article_body}

                    </div>

                  </ResultSection>

                )}







                {/* Quotes */}

                {schema.quotes && schema.quotes.length > 0 && (

                  <ResultSection

                    title="Cytaty z filmu"

                    copyText={schema.quotes.map((q) => `"${q.text}" — ${q.author ?? ''}`).join('\n')}

                    copyId="quotes"

                    copiedKey={copiedKey}

                    onCopy={handleCopy}

                    badge={`${schema.quotes.length}`}

                  >

                    <div className="space-y-2">

                      {schema.quotes.map((q, idx) => (\n\n                        <blockquote\n\n                          key={idx}\n\n                          className=\"border-l-2 border-fuchsia-500/50 pl-3 py-1 text-sm text-gray-300 italic\"\n\n                        >\n\n                          &ldquo;{q.text}&rdquo;\n\n                          {q.author && (\n\n                            <span className=\"not-italic text-xs text-gray-500 ml-2\">— {q.author}</span>\n\n                          )}\n\n                        </blockquote>\n\n                      ))}\n\n                    </div>\n\n                  </ResultSection>\n\n                )}\n\n\n\n\n\n\n\n                {/* FAQ */}\n\n                {faq.length > 0 && (\n\n                  <ResultSection\n\n                    title=\"Najczęściej zadawane pytania (FAQ)\"\n\n                    copyText={faqToHtml(faq)}\n\n                    copyId=\"faq_html\"\n\n                    copiedKey={copiedKey}\n\n                    onCopy={handleCopy}\n\n                    badge={`${faq.length} pytań`}\n\n                  >\n\n                    <div className=\"space-y-3\">\n\n                      {faq.map((f, idx) => (\n\n                        <div key={idx} className=\"bg-gray-950 p-3 rounded-lg border border-gray-800\">\n\n                          <p className=\"text-xs font-semibold text-violet-300 mb-1\">\n\n                            P: {f.question}\n\n                          </p>\n\n                          <p className=\"text-xs text-gray-300 leading-relaxed\">\n\n                            O: {f.answer}\n\n                          </p>\n\n                        </div>\n\n                      ))}\n\n                    </div>\n\n                  </ResultSection>\n\n                )}\n\n              </div>\n\n            )}\n\n\n\n\n\n\n\n            {/* Tab: Rozdziały */}\n\n            {activeTab === 'chapters' && (\n\n              <div>\n\n                <ResultSection\n\n                  title=\"Znaczniki czasu YouTube (Timestamps)\"\n\n                  copyText={chaptersToText(chapters)}\n\n                  copyId=\"chapters_text\"\n\n                  copiedKey={copiedKey}\n\n                  onCopy={handleCopy}\n\n                  badge={`${chapters.length} rozdziałów`}\n\n                >\n\n                  {chapters.length > 0 ? (\n\n                    <div className=\"space-y-1.5\">\n\n                      <p className=\"text-xs text-gray-500 mb-3\">\n\n                        Format gotowy do wklejenia w opisie filmu YouTube:\n\n                      </p>\n\n                      <div className=\"bg-gray-950 p-3 rounded-lg border border-gray-800 font-mono text-xs space-y-1\">\n\n                        {chapters.map((c, idx) => (\n\n                          <div key={idx} className=\"flex items-center gap-2\">\n\n                            <span className=\"text-violet-400 font-semibold shrink-0\">\n\n                              {secToTimestamp(c.startOffset ?? c.time)}\n\n                            </span>\n\n                            <span className=\"text-gray-500\">—</span>\n\n                            <span className=\"text-gray-300\">{c.name ?? c.label ?? '(bez tytułu)'}</span>\n\n                          </div>\n\n                        ))}\n\n                      </div>\n\n                    </div>\n\n                  ) : (\n\n                    <p className=\"text-xs text-gray-500 italic\">\n\n                      Brak wygenerowanych rozdziałów dla tego filmu.\n\n                    </p>\n\n                  )}\n\n                </ResultSection>\n\n              </div>\n\n            )}\n\n            {/* Tab: Opis YouTube */}\n            {activeTab === 'youtube' && (\n              <div>\n                <div className=\"flex items-center justify-between mb-4\">\n                  <span className=\"text-xs text-gray-500\">\n                    Gotowy opis do wklejenia na YouTube lub bezpośredniej publikacji przez API\n                  </span>\n                  {ytChannels.length > 0 && (\n                    <button\n                      onClick={() => setYtModalOpen(true)}\n                      className=\"px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow\"\n                    >\n                      <span>▶️</span>\n                      <span>Publikuj na YouTube</span>\n                    </button>\n                  )}\n                </div>\n\n                <ResultSection\n                  title=\"Pełny opis filmu YouTube\"\n                  copyText={buildYtDescription(schema)}\n                  copyId=\"yt_desc_full\"\n                  copiedKey={copiedKey}\n                  onCopy={handleCopy}\n                  badge=\"YouTube Ready\"\n                >\n                  <pre className=\"text-xs font-mono text-gray-300 bg-gray-950 p-4 rounded-lg overflow-x-auto whitespace-pre-wrap border border-gray-800 leading-relaxed\">\n                    {buildYtDescription(schema) || '(Brak danych do wygenerowania opisu)'}\n                  </pre>\n                </ResultSection>\n              </div>\n            )}\n\n            {/* Tab: ShortMachine (2026-08-20, shadow-dev-01) */}\n            {activeTab === 'shorts' && (\n              <div className=\"space-y-6\">\n                {/* Formularz analizy */}\n                <div className=\"bg-gray-900 border border-gray-800 rounded-xl p-5\">\n                  <h3 className=\"text-sm font-semibold text-white mb-3\">✂️ ShortMachine — Generator Shorts</h3>\n                  <div className=\"grid grid-cols-1 md:grid-cols-2 gap-4 mb-4\">\n                    <div>\n                      <label className=\"block text-xs text-gray-400 mb-1\">ID lub URL filmu YouTube</label>\n                      <input\n                        type=\"text\"\n                        placeholder=\"np. dQw4w9WgXcQ lub pełny URL\"\n                        value={smYoutubeId}\n                        onChange={(e) => {\n                          const val = e.target.value;\n                          const m = val.match(/(?:v=|youtu\\.be\\/|\\/shorts\\/)([A-Za-z0-9_-]{11})/);\n                          setSmYoutubeId(m ? m[1] : val);\n                        }}\n                        className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 font-mono\"\n                      />\n                    </div>\n                    <div>\n                      <label className=\"block text-xs text-gray-400 mb-1\">Zapytanie niestandardowe (opcjonalne)</label>\n                      <input\n                        type=\"text\"\n                        placeholder=\"np. moment o inwestowaniu w nieruchomości\"\n                        value={smCustomQuery}\n                        onChange={(e) => setSmCustomQuery(e.target.value)}\n                        className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-violet-500\"\n                      />\n                    </div>\n                  </div>\n\n                  {/* Suwaki liczby kandydatów */}\n                  <div className=\"grid grid-cols-3 gap-4 mb-4 p-3 bg-gray-950 rounded-lg border border-gray-800\">\n                    <div>\n                      <div className=\"flex justify-between text-xs text-gray-400 mb-1\">\n                        <span>🔥 Emocjonalne</span>\n                        <span className=\"text-violet-400 font-mono font-semibold\">{smCountEmotional}</span>\n                      </div>\n                      <input\n                        type=\"range\" min=\"0\" max=\"10\" value={smCountEmotional}\n                        onChange={(e) => setSmCountEmotional(Number(e.target.value))}\n                        className=\"w-full accent-violet-500\"\n                      />\n                    </div>\n                    <div>\n                      <div className=\"flex justify-between text-xs text-gray-400 mb-1\">\n                        <span>👔 Profesjonalne</span>\n                        <span className=\"text-violet-400 font-mono font-semibold\">{smCountProfessional}</span>\n                      </div>\n                      <input\n                        type=\"range\" min=\"0\" max=\"10\" value={smCountProfessional}\n                        onChange={(e) => setSmCountProfessional(Number(e.target.value))}\n                        className=\"w-full accent-violet-500\"\n                      />\n                    </div>\n                    <div>\n                      <div className=\"flex justify-between text-xs text-gray-400 mb-1\">\n                        <span>🎯 Custom Query</span>\n                        <span className=\"text-violet-400 font-mono font-semibold\">{smCountCustom}</span>\n                      </div>\n                      <input\n                        type=\"range\" min=\"0\" max=\"10\" value={smCountCustom}\n                        onChange={(e) => setSmCountCustom(Number(e.target.value))}\n                        disabled={!smCustomQuery.trim()}\n                        className=\"w-full accent-violet-500 disabled:opacity-30\"\n                      />\n                    </div>\n                  </div>\n\n                  <button\n                    onClick={async () => {\n                      if (!smYoutubeId.trim()) return\n                      setSmLoading(true)\n                      setSmError(null)\n                      try {\n                        const apiBase = process.env.NEXT_PUBLIC_API_URL || ''\n                        const res = await fetch(`${apiBase}/v1/shorts/candidates`, {\n                          method: 'POST',\n                          headers: { 'Content-Type': 'application/json' },\n                          body: JSON.stringify({\n                            youtube_id: smYoutubeId,\n                            count_emotional: smCountEmotional,\n                            count_professional: smCountProfessional,\n                            count_custom: smCountCustom,\n                            custom_query: smCustomQuery || undefined,\n                          })\n                        })\n                        if (!res.ok) throw new Error(`Błąd API: ${res.status}`)\n                        const data = await res.json()\n                        setSmCandidates(data.candidates || [])\n                        if (!data.candidates?.length) setSmError('Nie znaleziono kandydatów na Shorty dla tego filmu.')\n                      } catch (err: any) {\n                        setSmError(err.message || 'Wystąpił błąd')\n                      } finally {\n                        setSmLoading(false)\n                      }\n                    }}\n                    disabled={smLoading || !smYoutubeId.trim()}\n                    className=\"w-full py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:opacity-90 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-2 shadow-lg shadow-violet-500/20\"\n                  >\n                    {smLoading ? (\n                      <><span className=\"animate-spin inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full\" /> Szukam najlepszych momentów...</>\n                    ) : (\n                      '🔍 Znajdź kandydatów na Shorts'\n                    )}\n                  </button>\n\n                  {smError && (\n                    <p className=\"text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-2.5 mt-3\">{smError}</p>\n                  )}\n                </div>\n\n                {/* Lista kandydatów */}\n                {smCandidates.length > 0 && (\n                  <div className=\"space-y-4\">\n                    <div className=\"flex items-center justify-between\">\n                      <span className=\"text-xs font-semibold text-gray-300\">\n                        Znaleziono {smCandidates.length} kandydatów\n                      </span>\n                      <span className=\"text-xs text-gray-500\">Kliknij ▶️ aby podglądnąć fragment</span>\n                    </div>\n\n                    <div className=\"flex items-center justify-between bg-gray-900 border border-gray-800 rounded-xl px-4 py-3 mb-2\">\n                      <div className=\"flex items-center gap-3\">\n                        <label className=\"flex items-center gap-2 cursor-pointer\">\n                          <input\n                            type=\"checkbox\"\n                            checked={smSelected.size === smCandidates.length && smCandidates.length > 0}\n                            onChange={() => {\n                              if (smSelected.size === smCandidates.length) setSmSelected(new Set());\n                              else setSmSelected(new Set(smCandidates.map((_, i) => i)));\n                            }}\n                            className=\"accent-violet-500 rounded\"\n                          />\n                          <span className=\"text-xs text-gray-400\">\n                            {smSelected.size > 0 ? `Zaznaczono: ${smSelected.size}/${smCandidates.length}` : 'Zaznacz wszystkie'}\n                          </span>\n                        </label>\n                        <div className=\"flex items-center gap-2 ml-4\">\n                          <span className=\"text-xs text-gray-400\">Format masowy:</span>\n                          <select\n                            value={smFormat}\n                            onChange={(e) => setSmFormat(e.target.value as 'raw' | 'short')}\n                            className=\"bg-gray-800 text-xs text-white border border-gray-700 rounded px-2 py-1\"\n                          >\n                            <option value=\"raw\">🎬 Oryginał (16:9)</option>\n                            <option value=\"short\">📱 Pionowy (9:16 + napisy)</option>\n                          </select>\n                        </div>\n                      </div>\n                      <button\n                        onClick={async () => {\n                          const indices = Array.from(smSelected);\n                          for (const idx of indices) {\n                            const c = smCandidates[idx];\n                            const adj = getAdj(idx, c);\n                            setSmJobStatus(prev => ({...prev, [idx]: {status: 'queued'}}));\n                            try {\n                              const apiBase = process.env.NEXT_PUBLIC_API_URL || '';\n                              const res = await fetch(`${apiBase}/v1/shorts/render`, {\n                                method: 'POST',\n                                headers: {'Content-Type': 'application/json'},\n                                body: JSON.stringify({\n                                  youtube_id: smYoutubeId,\n                                  start_sec: adj.start,\n                                  end_sec: adj.end,\n                                  format: smFormat,\n                                  subtitles: smFormat === 'short' ? 'burn' : 'none'\n                                })\n                              });\n                              const data = await res.json();\n                              if (data.job_id) {\n                                setSmJobStatus(prev => ({...prev, [idx]: {status: 'queued', job_id: data.job_id}}));\n                                const poll = setInterval(async () => {\n                                  const sRes = await fetch(`${apiBase}/v1/shorts/status/${data.job_id}`);\n                                  const sData = await sRes.json();\n                                  setSmJobStatus(prev => ({...prev, [idx]: sData}));\n                                  if (sData.status === 'done' || sData.status === 'error') clearInterval(poll);\n                                }, 3000);\n                              }\n                            } catch (e: any) {\n                              setSmJobStatus(prev => ({...prev, [idx]: {status: 'error', error: e.message}}));\n                            }\n                          }\n                        }}\n                        disabled={smSelected.size === 0}\n                        className=\"px-4 py-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:opacity-90 disabled:opacity-40 text-white text-xs font-semibold rounded-lg transition-all\"\n                      >\n                        🚀 Renderuj zaznaczone ({smSelected.size})\n                      </button>\n                    </div>\n\n                    {smCandidates.map((c: any, i: number) => (\n                      <div key={i} className=\"bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3\">\n                        <div className=\"flex items-start justify-between gap-3\">\n                          <div className=\"flex items-center gap-2\">\n                            <input\n                              type=\"checkbox\"\n                              checked={smSelected.has(i)}\n                              onChange={() => toggleSmSelected(i)}\n                              className=\"accent-violet-500 rounded mt-0.5\"\n                            />\n                            <span className=\"text-xs font-mono font-semibold px-2 py-0.5 rounded bg-violet-500/20 text-violet-300 border border-violet-500/30\">\n                              #{i + 1} [{c.candidate_type || 'clip'}]\n                            </span>\n                            <span className=\"text-xs font-mono text-gray-400\">\n                              {fmtSec((c.start_sec??0)+(smTrimAdj[i]?.startDelta??0))} – {fmtSec((c.end_sec??0)+(smTrimAdj[i]?.endDelta??0))}\n                            </span>\n                            <span className=\"text-xs text-gray-500\">({Math.round((c.duration_sec ?? ((c.end_sec??0) - (c.start_sec??0))) + (smTrimAdj[i]?.endDelta??0) - (smTrimAdj[i]?.startDelta??0))}s)</span>\n                          </div>\n                          <div className=\"flex items-center gap-2\">\n                            <span className=\"text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded\">\n                              Wynik: {Math.round((c.score || 0) * 100)}%\n                            </span>\n                            <button\n                              onClick={() => setSmPreviewIdx(smPreviewIdx === i ? null : i)}\n                              className=\"text-xs px-2.5 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg border border-gray-700 transition-colors\"\n                            >\n                              {smPreviewIdx === i ? '⏹️ Zamknij' : '▶️ Podgląd'}\n                            </button>\n                          </div>\n                        </div>\n\n                        {c.hook && (\n                          <p className=\"text-xs text-gray-300 italic bg-gray-950 p-2.5 rounded-lg border border-gray-800/60\">\n                            💡 <span className=\"font-semibold text-violet-300\">Hook:</span> &ldquo;{c.hook}&rdquo;\n                          </p>\n                        )}\n\n                        {c.reason && (\n                          <p className=\"text-xs text-gray-400\">\n                            <span className=\"text-gray-500\">Dlaczego warto:</span> {c.reason}\n                          </p>\n                        )}\n\n                        {/* Player podglądu iframe YouTube */}\n                        {smPreviewIdx === i && (\n                          <div className=\"mt-2 rounded-lg overflow-hidden border border-violet-500/40 bg-black p-2\">\n                            <iframe\n                              width=\"100%\"\n                              height=\"220\"\n                              src={`https://www.youtube.com/embed/${smYoutubeId}?start=${Math.floor((c.start_sec??0)+(smTrimAdj[i]?.startDelta??0))}&end=${Math.ceil((c.end_sec??0)+(smTrimAdj[i]?.endDelta??0))}&autoplay=1`}\n                              title={`Podgląd #${i+1}`}\n                              allow=\"accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture\"\n                              allowFullScreen\n                              className=\"rounded\"\n                            />\n                          </div>\n                        )}\n\n                        {/* Tytuł & Tagi — Sekcja AI */}\n                        <div className=\"border-t border-gray-800/60 pt-3 space-y-2\">\n                          <div className=\"flex items-center justify-between gap-2\">\n                            <label className=\"text-xs font-semibold text-gray-400\">💡 Sugerowany tytuł Shorta</label>\n                            <button\n                              onClick={() => handleRegenerateTitle(i, c)}\n                              disabled={smTitleLoading[i]}\n                              className=\"text-xs text-violet-400 hover:text-violet-300 disabled:opacity-50 flex items-center gap-1\"\n                            >\n                              {smTitleLoading[i] ? '⏳ Generuję...' : '🔄 Wygeneruj nowy'}\n                            </button>\n                          </div>\n                          <input\n                            type=\"text\"\n                            value={smTitles[i] ?? c.suggested_title ?? ''}\n                            onChange={(e) => setSmTitles(prev => ({...prev, [i]: e.target.value}))}\n                            placeholder=\"Wpisz lub wygeneruj chwytliwy tytuł...\"\n                            className=\"w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-violet-500\"\n                          />\n\n                          {/* Tagi */}\n                          {(smTags[i] || c.tags) && (\n                            <div className=\"flex flex-wrap gap-1.5 pt-1\">\n                              {(smTags[i] || c.tags || []).map((tag: string, tIdx: number) => (\n                                <span key={tIdx} className=\"text-xs px-2 py-0.5 rounded-full bg-violet-950/60 border border-violet-800/40 text-violet-300 font-mono\">\n                                  #{tag.replace(/^#/, '')}\n                                </span>\n                              ))}\n                            </div>\n                          )}\n                        </div>\n\n                        {/* Docięcie / Trim kandydata (2026-08-20, shadow-dev-01) */}\n                        <div className=\"border-t border-gray-800/60 pt-3\">\n                          <button\n                            onClick={() => setSmExpandedIdx(smExpandedIdx === i ? null : i)}\n                            className=\"text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1 font-medium\"\n                          >\n                            ✂️ {smExpandedIdx === i ? 'Ukryj docięcie fragmentu' : 'Dopasuj czas (docięcie)'}\n                          </button>\n                          {smExpandedIdx === i && (\n                            <div className=\"mt-3 p-3 bg-gray-950 rounded-lg border border-gray-800 space-y-3\">\n                              <div className=\"flex gap-2\">\n                                <button\n                                  onClick={() => setSmTrimMode('start')}\n                                  className={`flex-1 text-xs py-1 rounded ${smTrimMode === 'start' ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400'}`}\n                                >\n                                  Dostosuj początek ({fmtSec((c.start_sec??0) + (smTrimAdj[i]?.startDelta??0))})\n                                </button>\n                                <button\n                                  onClick={() => setSmTrimMode('end')}\n                                  className={`flex-1 text-xs py-1 rounded ${smTrimMode === 'end' ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400'}`}\n                                >\n                                  Dostosuj koniec ({fmtSec((c.end_sec??0) + (smTrimAdj[i]?.endDelta??0))})\n                                </button>\n                              </div>\n\n                              <div className=\"flex items-center gap-2\">\n                                <span className=\"text-xs text-gray-400 w-16\">\n                                  {smTrimMode === 'start' ? 'Start delta:' : 'Koniec delta:'}\n                                </span>\n                                <input\n                                  type=\"range\"\n                                  min=\"-10\"\n                                  max=\"10\"\n                                  step=\"0.5\"\n                                  value={smTrimMode === 'start' ? (smTrimAdj[i]?.startDelta ?? 0) : (smTrimAdj[i]?.endDelta ?? 0)}\n                                  onChange={(e) => {\n                                    const val = parseFloat(e.target.value)\n                                    setSmTrimAdj(prev => ({\n                                      ...prev,\n                                      [i]: {\n                                        startDelta: smTrimMode === 'start' ? val : (prev[i]?.startDelta ?? 0),\n                                        endDelta: smTrimMode === 'end' ? val : (prev[i]?.endDelta ?? 0)\n                                      }\n                                    }))\n                                  }}\n                                  className=\"flex-1 accent-violet-500\"\n                                />\n                                <span className=\"text-xs font-mono text-violet-300 w-12 text-right\">\n                                  {smTrimMode === 'start' ? `${(smTrimAdj[i]?.startDelta ?? 0) > 0 ? '+' : ''}${smTrimAdj[i]?.startDelta ?? 0}s` : `${(smTrimAdj[i]?.endDelta ?? 0) > 0 ? '+' : ''}${smTrimAdj[i]?.endDelta ?? 0}s`}\n                                </span>\n                              </div>\n\n                              <div className=\"flex justify-between text-xs text-gray-500 pt-1\">\n                                <span>Efektywny czas: <span className=\"font-mono text-gray-300\">{fmtSec((c.start_sec??0)+(smTrimAdj[i]?.startDelta??0))} – {fmtSec((c.end_sec??0)+(smTrimAdj[i]?.endDelta??0))}</span></span>\n                                <span>Długość: <span className=\"font-mono text-gray-300\">{Math.round((c.duration_sec ?? ((c.end_sec??0) - (c.start_sec??0))) + (smTrimAdj[i]?.endDelta??0) - (smTrimAdj[i]?.startDelta??0))}s</span></span>\n                              </div>\n                            </div>\n                          )}\n                        </div>\n\n                        {/* Sekcja renderowania (2026-08-20, shadow-dev-01) */}\n                        <div className=\"border-t border-gray-800/60 pt-3 space-y-3\">\n                          <div className=\"flex flex-wrap items-center justify-between gap-2\">\n                            <div className=\"flex items-center gap-3\">\n                              {/* Format select */}\n                              <div className=\"flex items-center gap-1.5\">\n                                <label className=\"text-xs text-gray-400\">Format:</label>\n                                <select\n                                  value={smRenderConfig[i]?.format || 'raw'}\n                                  onChange={(e) => setSmRenderConfig(prev => ({\n                                    ...prev,\n                                    [i]: { ...prev[i], format: e.target.value, subtitles: prev[i]?.subtitles || 'none' }\n                                  }))}\n                                  className=\"bg-gray-800 border border-gray-700 text-xs text-gray-200 rounded px-2 py-1 focus:outline-none focus:border-violet-500\"\n                                >\n                                  <option value=\"raw\">🎬 Oryginał (16:9)</option>\n                                  <option value=\"short\">📱 Pionowy (9:16)</option>\n                                </select>\n                              </div>\n\n                              {/* Subtitles select */}\n                              <div className=\"flex items-center gap-1.5\">\n                                <label className=\"text-xs text-gray-400\">Napisy:</label>\n                                <select\n                                  value={smRenderConfig[i]?.subtitles || 'none'}\n                                  onChange={(e) => setSmRenderConfig(prev => ({\n                                    ...prev,\n                                    [i]: { ...prev[i], subtitles: e.target.value, format: prev[i]?.format || 'raw' }\n                                  }))}\n                                  className=\"bg-gray-800 border border-gray-700 text-xs text-gray-200 rounded px-2 py-1 focus:outline-none focus:border-violet-500\"\n                                >\n                                  <option value=\"none\">Brak</option>\n                                  <option value=\"burn\">Wtopione w wideo (Burn-in)</option>\n                                </select>\n                              </div>\n                            </div>\n\n                            {/* Render Button */}\n                            <button\n                              onClick={async () => {\n                                const adj = getAdj(i, c)\n                                const fmt = smRenderConfig[i]?.format || 'raw'\n                                const subs = smRenderConfig[i]?.subtitles || 'none'\n                                setSmJobStatus(prev => ({ ...prev, [i]: { status: 'queued' } }))\n                                try {\n                                  const apiBase = process.env.NEXT_PUBLIC_API_URL || ''\n                                  const res = await fetch(`${apiBase}/v1/shorts/render`, {\n                                    method: 'POST',\n                                    headers: { 'Content-Type': 'application/json' },\n                                    body: JSON.stringify({\n                                      youtube_id: smYoutubeId,\n                                      start_sec: adj.start,\n                                      end_sec: adj.end,\n                                      format: fmt,\n                                      subtitles: subs,\n                                    })\n                                  })\n                                  if (!res.ok) throw new Error(`Błąd API: ${res.status}`)\n                                  const data = await res.json()\n                                  if (data.job_id) {\n                                    setSmJobStatus(prev => ({ ...prev, [i]: { status: 'queued', job_id: data.job_id } }))\n                                    // Polling\n                                    const poll = setInterval(async () => {\n                                      try {\n                                        const sRes = await fetch(`${apiBase}/v1/shorts/status/${data.job_id}`)\n                                        const sData = await sRes.json()\n                                        setSmJobStatus(prev => ({ ...prev, [i]: sData }))\n                                        if (sData.status === 'done' || sData.status === 'error') {\n                                          clearInterval(poll)\n                                        }\n                                      } catch {\n                                        clearInterval(poll)\n                                      }\n                                    }, 2000)\n                                  }\n                                } catch (err: any) {\n                                  setSmJobStatus(prev => ({ ...prev, [i]: { status: 'error', error: err.message } }))\n                                }\n                              }}\n                              disabled={smJobStatus[i]?.status === 'queued' || smJobStatus[i]?.status === 'processing'}\n                              className=\"px-3 py-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:opacity-90 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-all flex items-center gap-1.5 shadow\"\n                            >\n                              {smJobStatus[i]?.status === 'queued' || smJobStatus[i]?.status === 'processing' ? (\n                                <><span className=\"animate-spin inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full\" /> Renderowanie...</>\n                              ) : (\n                                '🎬 Renderuj ten fragment'\n                              )}\n                            </button>\n                          </div>\n\n                          {/* Status joba & Pobieranie */}\n                          {smJobStatus[i] && (\n                            <div className=\"bg-gray-950 p-2.5 rounded-lg border border-gray-800 text-xs\">\n                              {smJobStatus[i].status === 'queued' && (\n                                <span className=\"text-amber-400\">⏳ Oczekuje w kolejce...</span>\n                              )}\n                              {smJobStatus[i].status === 'processing' && (\n                                <span className=\"text-violet-400\">⚙️ Renderowanie wideo przez FFmpeg...</span>\n                              )}\n                              {smJobStatus[i].status === 'error' && (\n                                <span className=\"text-red-400\">⚠️ Błąd: {smJobStatus[i].error || 'Nieznany'}</span>\n                              )}\n                              {smJobStatus[i].status === 'done' && (\n                                <div className=\"space-y-1.5\">\n                                  <div className=\"flex items-center gap-2 text-emerald-400 font-semibold\">\n                                    <span>✔️ Gotowe do pobrania!</span>\n                                  </div>\n                                  <div className=\"flex flex-wrap gap-2 pt-1\">\n                                    {smJobStatus[i].result_paths?.raw_clip && (\n                                      <a\n                                        href={`${process.env.NEXT_PUBLIC_API_URL || ''}/v1/shorts/download/${smJobStatus[i].job_id || ''}?type=raw`}\n                                        target=\"_blank\"\n                                        rel=\"noreferrer\"\n                                        className=\"px-2.5 py-1 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded border border-gray-700 flex items-center gap-1\"\n                                      >\n                                        📥 Pobierz 16:9 (MP4)\n                                      </a>\n                                    )}\n                                    {smJobStatus[i].result_paths?.short_clip && (\n                                      <a\n                                        href={`${process.env.NEXT_PUBLIC_API_URL || ''}/v1/shorts/download/${smJobStatus[i].job_id || ''}?type=short`}\n                                        target=\"_blank\"\n                                        rel=\"noreferrer\"\n                                        className=\"px-2.5 py-1 bg-violet-600/30 hover:bg-violet-600/50 text-violet-200 rounded border border-violet-500/40 flex items-center gap-1 font-medium\"\n                                      >\n                                        📱 Pobierz 9:16 Short (MP4)\n                                      </a>\n                                    )}\n                                  </div>\n                                </div>\n                              )}\n                            </div>\n                          )}\n                        </div>\n                        \n                        {/* YouTube Inject Block */}\n                        <div className=\"border-t border-gray-600 pt-3 mt-1\">\n                          <p className=\"text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2\">► Wstrzyknij metadane na YouTube</p>\n                          <input\n                            type=\"text\"\n                            placeholder=\"URL lub ID YouTube (wgrany z Premiere Pro)\"\n                            className=\"w-full bg-gray-700 text-white text-sm rounded px-3 py-2 border border-gray-600 focus:border-blue-500 focus:outline-none mb-2\"\n                            value={smTargetYtId[i] || ''}\n                            onChange={e => setSmTargetYtId(prev => ({...prev, [i]: e.target.value}))}\n                          />\n                          <div className=\"grid grid-cols-3 gap-2 mb-2\">\n                            <select\n                              className=\"bg-gray-700 text-white text-sm rounded px-2 py-2 border border-gray-600\"\n                              value={smSelectedPlaylist[i] || ''}\n                              onChange={e => setSmSelectedPlaylist(prev => ({...prev, [i]: e.target.value}))}\n                            >\n                              <option value=\"\">Playlista (opcj.)</option>\n                              {smPlaylists.map(pl => <option key={pl.id} value={pl.id}>{pl.title}</option>)}\n                            </select>\n                            <input\n                              type=\"datetime-local\"\n                              className=\"bg-gray-700 text-white text-sm rounded px-2 py-2 border border-gray-600\"\n                              value={smPublishAt[i] || ''}\n                              onChange={e => setSmPublishAt(prev => ({...prev, [i]: e.target.value}))}\n                            />\n                            <select\n                              className=\"bg-gray-700 text-white text-sm rounded px-2 py-2 border border-gray-600\"\n                              value={smPrivacyStatus[i] || 'private'}\n                              onChange={e => setSmPrivacyStatus(prev => ({...prev, [i]: e.target.value}))}\n                            >\n                              <option value=\"private\">Prywatny</option>\n                              <option value=\"unlisted\">Niepubliczny</option>\n                              <option value=\"public\">Publiczny</option>\n                            </select>\n                          </div>\n                          <div className=\"flex items-center gap-3\">\n                            <button\n                              onClick={() => setSmModalOpenFor(i)}\n                              disabled={!smTargetYtId[i]}\n                              className=\"bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded transition-colors\"\n                            >\n                              ► Podgląd i publikacja\n                            </button>\n                          </div>\n                        </div>\n                      </div>\n                    ))}\n                    {smSelected.size > 0 && (\n                      <div className=\"sticky bottom-4 bg-gray-900/90 backdrop-blur border border-violet-500/40 rounded-xl p-3 flex items-center justify-between shadow-2xl\">\n                        <span className=\"text-xs text-violet-300 font-medium\">\n                          Zaznaczono: {smSelected.size} / {smCandidates.length} klipów\n                        </span>\n                        <button\n                          onClick={() => {}}\n                          className=\"px-4 py-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white text-xs font-semibold rounded-lg shadow\"\n                        >\n                          🚀 Renderuj zaznaczone ({smSelected.size})\n                        </button>\n                      </div>\n                    )}\n                  </div>\n                )}\n              </div>\n            )}\n          </div>\n        )}\n\n        {/* Empty state when no result */}\n\n        {!result && !loading && (\n\n          <div className=\"text-center py-16 border border-dashed border-gray-800 rounded-2xl\">\n\n            <div className=\"w-12 h-12 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-xl mx-auto mb-3\">\n\n              🎬\n\n            </div>\n\n            <h3 className=\"text-sm font-medium text-gray-300\">Brak wygenerowanego SEO</h3>\n\n            <p className=\"text-xs text-gray-600 mt-1 max-w-sm mx-auto\">\n\n              Wklej URL filmu YouTube powyżej i kliknij &ldquo;Generuj SEO&rdquo;, aby rozpocząć analizę.\n\n            </p>\n\n          </div>\n\n        )}\n\n      </main>\n\n      {/* ShortMachine YouTube Inject Modal */}\n      {smModalOpenFor !== null && smCandidates[smModalOpenFor] && (() => {\n        const i = smModalOpenFor;\n        const c = smCandidates[i];\n        \n        // Mock schema data for short\n        const smSchemaData = {\n          youtube_description_hook: smTitles[i] || c.suggested_title || c.title || '',\n          video_description: c.hook || '',\n          youtube_hashtags: smTags[i] || c.tags || []\n        };\n        const rawInput = smTargetYtId[i] || '';\n        const smVideoId = rawInput.match(/(?:v=|youtu\\.be\\/|\\/shorts\\/)([A-Za-z0-9_-]{11})/)?.[1] || rawInput;\n\n        return (\n          <YouTubePublishModal\n            isOpen={true}\n            onClose={() => setSmModalOpenFor(null)}\n            videoId={smVideoId}\n            schemaData={smSchemaData}\n            wpUrl=\"\"\n            channels={ytChannels}\n            accessToken={accessToken || \"\"}\n            apiUrl={process.env.NEXT_PUBLIC_API_URL || ''}\n            publishAt={smPublishAt[i]}\n            privacyStatus={smPrivacyStatus[i]}\n            playlistId={smSelectedPlaylist[i]}\n          />\n        );\n      })()}\n\n      {/* Inject Modal — pass selected portal so isManual=false for Pro/Agency users [vse-dev-37 fix] */}\n\n      {showInjectModal && result && (() => {\n\n        const selectedPortal = portals.find((p) => p.id === selectedPortalId)\n\n        return (\n\n          <InjectModal\n\n            schemaData={result.schema_data as SchemaData}\n\n            videoUrl={url}\n\n            selectedPortalId={selectedPortalId}\n\n            portalName={selectedPortal?.name}\n\n            portalUrl={selectedPortal?.url}\n\n            accessToken={accessToken}\n\n            onClose={() => setShowInjectModal(false)}\n\n            ytChannels={ytChannels}\n\n          />\n\n        )\n\n      })()}\n\n\n\n      {/* D34: Add Portal Modal */}\n\n      {showAddPortalModal && (\n\n        <AddPortalModal\n\n          onClose={() => setShowAddPortalModal(false)}\n\n          onSuccess={(newPortalId) => {\n\n            setShowAddPortalModal(false)\n\n            refreshPortals().then(() => {\n\n              setSelectedPortalId(newPortalId)\n\n            })\n\n          }}\n\n        />\n\n      )}\n\n\n\n      {/* YouTube Publish Modal */}\n\n      {result && schema && (\n\n        <YouTubePublishModal\n\n          isOpen={ytModalOpen}\n\n          onClose={() => setYtModalOpen(false)}\n\n          videoId={result.video_id}\n\n          schemaData={schema}\n\n          wpUrl={\n\n            selectedPortalId && selectedPortalId !== '__manual__'\n\n              ? (portals.find((p) => p.id === selectedPortalId)?.url || '')\n\n              : ''\n\n          }\n\n          channels={ytChannels}\n\n          accessToken={accessToken || ''}\n\n          apiUrl={process.env.NEXT_PUBLIC_API_URL || ''}\n\n        />\n\n      )}\n\n      {/* Quick WP Configuration Floating Panel (localStorage helper) */}\n\n      <WpQuickPanel />\n\n      </div>\n\n    </div>\n\n    </ErrorBoundary>\n\n  )\n\n}\n\n\n\n// ─── Sub-components ──────────────────────────────────────────────────────────\n\n\n\nfunction NavItem({\n\n  icon,\n\n  label,\n\n  href,\n\n  active,\n\n}: {\n\n  icon: string\n\n  label: string\n\n  href: string\n\n  active?: boolean\n\n}) {\n\n  const iconPath: Record<string, string> = {\n\n    grid: 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z',\n\n    clock: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',\n\n    settings: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z',\n\n  }\n\n\n\n  return (\n\n    <Link\n\n      href={href}\n\n      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${\n\n        active\n\n          ? 'bg-violet-600/10 text-violet-400'\n\n          : 'text-gray-400 hover:text-white hover:bg-gray-800'\n\n      }`}\n\n    >\n\n      <svg className=\"w-4 h-4\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\">\n\n        <path strokeLinecap=\"round\" strokeLinejoin=\"round\" strokeWidth={2} d={iconPath[icon] ?? ''} />\n\n      </svg>\n\n      {label}\n\n    </Link>\n\n  )\n\n}\n\n\n\n/**\n\n * CO: WpQuickPanel — pływający widget szybkiej konfiguracji WP\n\n * PO CO: Umożliwia podejrzenie i edycję zapamiętanych danych WordPress\n\n *        bez konieczności otwierania modala.\n\n * JAK: Czyta i zapisuje dane z localStorage ('vse_wp_credentials').\n\n */\n\nfunction WpQuickPanel() {\n\n  const [open, setOpen] = useState(false)\n\n  const [saved, setSaved] = useState(false)\n\n  const [creds, setCreds] = useState({ wpUrl: '', wpUser: '', wpPassword: '' })\n\n\n\n  useEffect(() => {\n\n    setCreds(loadWpCredentials())\n\n  }, [open])\n\n\n\n  const handleSave = (e: React.FormEvent) => {\n\n    e.preventDefault()\n\n    saveWpCredentials(creds)\n\n    setSaved(true)\n\n    setTimeout(() => setSaved(false), 2000)\n\n  }\n\n\n\n  const isConfigured = Boolean(creds.wpUrl && creds.wpUrl !== 'https://' && creds.wpUser)\n\n\n\n  return (\n\n    <div className=\"fixed bottom-4 right-4 z-30\">\n\n      {open ? (\n\n        <div className=\"bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl p-4 w-80 animate-in\">\n\n          <div className=\"flex items-center justify-between mb-3\">\n\n            <div className=\"flex items-center gap-2\">\n\n              <span className=\"text-xs\">⚙️</span>\n\n              <span className=\"text-xs font-semibold text-white\">Domyślny WordPress</span>\n\n            </div>\n\n            <button\n\n              onClick={() => setOpen(false)}\n\n              className=\"text-gray-400 hover:text-white text-xs p-1\"\n\n            >\n\n              ✕\n\n            </button>\n\n          </div>\n\n\n\n          <form onSubmit={handleSave} className=\"space-y-2.5\">\n\n            <div>\n\n              <label className=\"block text-xs text-gray-400 mb-1\">URL portalu</label>\n\n              <input\n\n                type=\"text\"\n\n                value={creds.wpUrl}\n\n                onChange={(e) => setCreds({ ...creds, wpUrl: e.target.value })}\n\n                placeholder=\"https://twojportal.pl\"\n\n                className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-violet-500\"\n\n              />\n\n            </div>\n\n            <div>\n\n              <label className=\"block text-xs text-gray-400 mb-1\">Użytkownik WP</label>\n\n              <input\n\n                type=\"text\"\n\n                value={creds.wpUser}\n\n                onChange={(e) => setCreds({ ...creds, wpUser: e.target.value })}\n\n                placeholder=\"admin\"\n\n                className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-violet-500\"\n\n              />\n\n            </div>\n\n            <div>\n\n              <label className=\"block text-xs text-gray-400 mb-1\">Application Password</label>\n\n              <input\n\n                type=\"password\"\n\n                value={creds.wpPassword}\n\n                onChange={(e) => setCreds({ ...creds, wpPassword: e.target.value })}\n\n                placeholder=\"xxxx xxxx xxxx xxxx\"\n\n                className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-violet-500\"\n\n              />\n\n            </div>\n\n            <button\n\n              type=\"submit\"\n\n              className=\"w-full py-2 bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold rounded-lg transition-colors\"\n\n            >\n\n              {saved ? '✔️ Zapisano!' : 'Zapisz dane'}\n\n            </button>\n\n          </form>\n\n        </div>\n\n      ) : (\n\n        <button\n\n          onClick={() => setOpen(true)}\n\n          className=\"flex items-center gap-1.5 px-3 py-2 bg-gray-900/90 hover:bg-gray-800 border border-gray-700 text-gray-300 hover:text-white text-xs font-medium rounded-xl shadow-lg backdrop-blur transition-all\"\n\n        >\n\n          <span>⚙️</span>\n\n          <span>WordPress</span>\n\n          {isConfigured && (\n\n            <span className=\"w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0\" />\n\n          )}\n\n        </button>\n\n      )}\n\n    </div>\n\n  )\n\n}\n