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



/**

 * CO: TabBar — przełącznik zakładek Schemat/Artykuł/Rozdziały

 * PO CO: Pozwala użytkownikowi przełączać widok wyników bez przeładowania strony.

 * JAK: Proste przyciski z active state, kontrolowane przez parent.

 */

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



/**

 * CO: InjectModal — modalny formularz publikacji na WordPress z dropdown portalów

 * PO CO: Umożliwia użytkownikom Pro/Agency wstrzyknięcie SEO na WordPress jednym klikiem.

 *        Portale zapisane w bazie danych (/v1/portals) — dropdown z auto-fill credentials.

 *        Fallback: ręczne wpisanie credentials (zapisywane w localStorage).

 * JAK: usePortals() → dropdown z listą portali → wybór portalu → getCredentials() → auto-fill.

 *      Po kliknięciu "Opublikuj" → POST /v1/inject → wyświetla wynik z linkiem do posta.

 */

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













  // Close on Escape

  useEffect(() => {

    const handler = (e: KeyboardEvent) => {

      if (e.key === 'Escape') onClose()

    }

    window.addEventListener('keydown', handler)

    return () => window.removeEventListener('keydown', handler)

  }, [onClose])







  // Close on click outside

  const handleBackdropClick = (e: React.MouseEvent) => {

    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {

      onClose()

    }

  }







  const isManual = selectedPortalId === '__manual__' || !selectedPortalId



  // Update YT preview

  useEffect(() => {

    if (selectedYtChannelIds.length === 0) { setYtDescPreview(''); return }

    const parts = []

    if (schemaData?.youtube_description_body) parts.push(schemaData.youtube_description_body)

    if (schemaData?.youtube_mid_cta) parts.push(schemaData.youtube_mid_cta)

    if (schemaData?.youtube_credits) parts.push(schemaData.youtube_credits)

    if (schemaData?.youtube_hashtags) parts.push(schemaData.youtube_hashtags)

    

    // Stopka z pierwszego kanału

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

        let errStr = data?.detail || data?.error || `Błąd serwera (HTTP ${res.status})`;

        if (typeof errStr === 'object') {

            errStr = JSON.stringify(errStr, null, 2);

        }

        throw new Error(errStr);

      }

      setPublishResult(data)

      if (data?.yt_results) {

        const errors: string[] = [];

        Object.entries(data.yt_results).forEach(([chId, status]) => {

          if (status !== "ok") errors.push(`Błąd YT: ${status}`);

        });

        if (errors.length > 0) {

          setPublishResult(prev => ({

            ...prev,

            error: (prev?.error ? prev.error + "\n" : "") + errors.join("\n")

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

        {/* Header */}

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

          <button

            onClick={onClose}

            className="text-gray-400 hover:text-white transition-colors p-1"

          >

            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">

              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />

            </svg>

          </button>

        </div>







        {/* Body */}

        <div className="px-6 py-5 space-y-4">

          {/* Article preview */}

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







          {/* Selected portal info — visible in portal mode */}

          {!isManual && portalName && (

            <div className="flex items-center gap-2 px-3 py-2 bg-violet-500/5 border border-violet-500/15 rounded-lg mb-4">

              <span className="text-xs text-violet-400">🚀</span>

              <span className="text-sm text-gray-200">Publikujesz na: <span className="font-semibold">{portalName}</span></span>

              <span className="text-xs text-gray-500 ml-auto">{portalUrl}</span>

            </div>

          )}







          {/* Manual credentials — visible only when manual mode or no portals */}

          {isManual && (

            <>

              {/* WP URL */}

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







              {/* Credentials row */}

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

          {/* YouTube Channels */}

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

            

            {/* Podgląd opisu YT */}

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







          {/* Post ID + Status + Format */}

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







          {/* Format wpisu */}

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







          {/* Publish button */}

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







          {/* Result */}

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







      {/* Animation keyframe */}

      <style jsx>{`

        @keyframes fadeInUp {

          from { opacity: 0; transform: translateY(20px); }

          to { opacity: 1; transform: translateY(0); }

        }

      `}</style>

    </div>

  )

}











// ─── AddPortalModal ─────────────────────────────────────────────────────────

// D35 (2026-06-30, vse-dev-01): Dynamic profile dropdown + inline profile creation







function AddPortalModal({

  onClose,

  onSuccess

}: {

  onClose: () => void

  onSuccess: (portalId: string) => void

}) {

  const { createPortal } = usePortals()

  const { profiles, loading: profilesLoading, createProfile } = useProfiles()







  // Portal fields

  const [name, setName] = useState('')

  const [url, setUrl] = useState('https://')

  const [wpUser, setWpUser] = useState('')

  const [wpPassword, setWpPassword] = useState('')

  const [profileId, setProfileId] = useState('')

  const [saving, setSaving] = useState(false)

  const [error, setError] = useState('')







  // Inline profile creation fields

  const [showNewProfileForm, setShowNewProfileForm] = useState(false)

  const [newProfileBrand, setNewProfileBrand] = useState('')

  const [newProfileType, setNewProfileType] = useState('analiza')

  const [newProfileLang, setNewProfileLang] = useState('pl')

  const [newProfileExtUrl, setNewProfileExtUrl] = useState('')

  const [newProfileExtAnchor, setNewProfileExtAnchor] = useState('')







  const modalRef = useRef<HTMLDivElement>(null)







  // Set default profile when profiles load

  useEffect(() => {

    if (profiles.length > 0 && !profileId) {

      setProfileId(profiles[0].id)

    }

  }, [profiles, profileId])







  // Close on Escape

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







  /** Slugify portal name to create a valid portal_id */

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







    // Validate new profile fields if creating inline

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

        // Step 1: Create profile first

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







      // Step 2: Create portal with profile

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

          {/* Portal name */}

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







          {/* WordPress URL */}

          <div>

            <label className="block text-xs text-gray-400 mb-1.5">URL WordPress</label>

            <input

              type="url"

              value={url}

              onChange={(e) => setUrl(e.target.value)}

              placeholder="https://twojportal.pl"

              className={inputClass}

            />

          </div>







          {/* WP Username */}

          <div>

            <label className="block text-xs text-gray-400 mb-1.5">Użytkownik WordPress</label>

            <input

              type="text"

              value={wpUser}

              onChange={(e) => setWpUser(e.target.value)}

              placeholder="admin"

              className={inputClass}

            />

          </div>







          {/* Application Password */}

          <div>

            <label className="block text-xs text-gray-400 mb-1.5">Application Password</label>

            <input

              type="password"

              value={wpPassword}

              onChange={(e) => setWpPassword(e.target.value)}

              placeholder="xxxx xxxx xxxx xxxx"

              className={inputClass}

            />

          </div>







          {/* Profile Assignment Section */}

          <div className="pt-2 border-t border-gray-800">

            <label className="block text-xs text-gray-400 mb-1.5">

              Profil SEO

              <span className="text-gray-500 font-normal ml-1">(opcjonalnie)</span>

            </label>







            <select

              value={showNewProfileForm ? '__new__' : profileId}

              onChange={(e) => handleProfileDropdownChange(e.target.value)}

              disabled={profilesLoading}

              className={selectClass}

              style={selectStyle}

            >

              <option value="none">Brak profilu</option>

              {profiles.map((p) => (

                <option key={p.id} value={p.id}>

                  {p.display_name} ({p.portal_id})

                </option>

              ))}

              <option value="__new__">+ Utwórz nowy profil dla tego portalu</option>

            </select>

            <p className="text-xs text-gray-600 mt-1">

              Profil definiuje styl SEO (język, link zewnętrzny, brand).

            </p>

          </div>







          {/* Inline Profile Creation Fields */}

          {showNewProfileForm && (

            <div className="space-y-3 p-3 bg-violet-950/20 border border-violet-800/30 rounded-xl animate-in" style={{ animation: 'fadeInUp 0.2s ease-out' }}>

              <p className="text-xs font-medium text-violet-300">Konfiguracja nowego profilu:</p>







              <div>

                <label className="block text-xs text-gray-400 mb-1">Nazwa brandu *</label>

                <input

                  type="text"

                  value={newProfileBrand}

                  onChange={(e) => setNewProfileBrand(e.target.value)}

                  placeholder="np. BiznesCiti"

                  className={inputClass}

                />

              </div>







              <div className="grid grid-cols-2 gap-2">

                <div>

                  <label className="block text-xs text-gray-400 mb-1">Domyślny typ</label>

                  <select

                    value={newProfileType}

                    onChange={(e) => setNewProfileType(e.target.value)}

                    className={selectClass}

                    style={selectStyle}

                  >

                    <option value="analiza">Analiza</option>

                    <option value="felieton">Felieton</option>

                    <option value="wywiad">Wywiad</option>

                    <option value="news">News</option>

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

                    <option value="pl">Polski (PL)</option>

                    <option value="en">English (EN)</option>

                    <option value="de">Deutsch (DE)</option>

                    <option value="es">Español (ES)</option>

                  </select>

                </div>

              </div>







              <div>

                <label className="block text-xs text-gray-400 mb-1">Link zewnętrzny (URL)</label>

                <input

                  type="url"

                  value={newProfileExtUrl}

                  onChange={(e) => setNewProfileExtUrl(e.target.value)}

                  placeholder="https://partner.com"

                  className={inputClass}

                />

              </div>







              <div>

                <label className="block text-xs text-gray-400 mb-1">Anchor linku zewnętrznego</label>

                <input

                  type="text"

                  value={newProfileExtAnchor}

                  onChange={(e) => setNewProfileExtAnchor(e.target.value)}

                  placeholder="np. Dowiedz się więcej"

                  className={inputClass}

                />

              </div>

            </div>

          )}







          {/* Error display */}

          {error && (

            <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-2.5">

              {error}

            </p>

          )}







          {/* Action buttons */}

          <div className="flex gap-2 pt-2">

            <button

              type="button"

              onClick={onClose}

              className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 text-sm font-medium rounded-xl transition-colors"

            >

              Anuluj

            </button>

            <button

              type="button"

              onClick={handleSave}

              disabled={saving}

              className="flex-1 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:opacity-90 disabled:opacity-50 text-white text-sm font-medium rounded-xl transition-all flex items-center justify-center gap-2"

            >

              {saving ? (

                <><span className="animate-spin inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full" /> Zapisywanie...</>

              ) : (

                'Zapisz portal'

              )}

            </button>

          </div>

        </div>

      </div>

    </div>

  )

}







/**

 * CO: ManageSubscriptionLink — link do Stripe Customer Portal

 * PO CO: Umożliwia użytkownikom z płatnym planem zarządzanie subskrypcją

 *        (zmiana karty, anulowanie, historia faktur).

 * JAK: POST /v1/stripe/customer-portal → zwraca URL portalu Stripe → redirect.

 */

function ManageSubscriptionLink() {

  const [loading, setLoading] = useState(false)

  const [error, setError] = useState<string | null>(null)







  const handleClick = async () => {

    setLoading(true)

    setError(null)

    try {

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''

      const res = await fetch(`${apiUrl}/v1/stripe/customer-portal`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

      })

      const data = await res.json()

      if (data.portal_url) {

        window.location.href = data.portal_url

      } else {

        setError(data.error || 'Nie udało się otworzyć portalu subskrypcji')

      }

    } catch {

      setError('Błąd połączenia z portalem subskrypcji')

    } finally {

      setLoading(false)

    }

  }







  return (

    <div className="mt-2">

      <button

        onClick={handleClick}

        disabled={loading}

        className="text-xs text-violet-400 hover:text-violet-300 underline underline-offset-2 transition-colors disabled:opacity-50"

      >

        {loading ? 'Ładowanie portalu...' : '⚙️ Zarządzaj subskrypcją'}

      </button>

      {error && <p className="text-xs text-red-400 mt-1">{error}</p>}

    </div>

  )

}







// ─── Main Component ─────────────────────────────────────────────────────────



function buildYtDescription(schema: SchemaData | null): string {
  if (!schema) return ''
  const parts: string[] = []

  // 1. Hook / lead
  if (schema.lead) {
    parts.push(schema.lead.trim())
  } else if (schema.meta_description) {
    parts.push(schema.meta_description.trim())
  }

  // 2. Chapters / timestamps
  const chapters = extractChapters(schema)
  if (chapters.length > 0) {
    const chapLines = chapters
      .map(c => `${secToTimestamp(c.startOffset ?? c.time)} ${c.name ?? c.label ?? ''}`.trim())
      .filter(l => l.length > 5)
    if (chapLines.length > 0) {
      parts.push('Rozdziały:\n' + chapLines.join('\n'))
    }
  }

  // 3. Quotes / highlights
  if (Array.isArray(schema.quotes) && schema.quotes.length > 0) {
    const quoteLines = schema.quotes
      .slice(0, 3)
      .map(q => `💬 "${q.text}"${q.author ? ` — ${q.author}` : ''}`)
    parts.push(quoteLines.join('\n'))
  }

  // 4. FAQ / key points
  const faq = extractFaq(schema)
  if (faq.length > 0) {
    const faqLines = faq
      .slice(0, 3)
      .map(f => `❓ ${f.question}\n${f.answer}`)
    parts.push(faqLines.join('\n\n'))
  }

  // 5. Hashtags
  if (schema.focus_keyphrase) {
    const tags = schema.focus_keyphrase
      .split(',')
      .map(t => '#' + t.trim().replace(/\s+/g, ''))
      .filter(t => t.length > 1)
      .slice(0, 5)
    if (tags.length > 0) parts.push(tags.join(' '))
  }

  return parts.join('\n\n')
}







export default function DashboardInner() {

  const router = useRouter()

  /**

   * CO: Auth guard i dane sesji

   * PO CO: Zapewnia dostęp tylko zalogowanym użytkownikom.

   * JAK: useSession z NextAuth → auth guard. Stan lokalny dla URL, wyników, plan usera.

   */

  const { data: session, status } = useSession()

  const accessToken = (session as any)?.accessToken

  // Global loader z informacjami o aktywnym jobie w Redis (job-08)

  const { activeJob, dismissBanner } = useJobLoader()







  // Portals hook (D34, vse-dev-01)

  const { portals, loading: portalsLoading, refresh: refreshPortals } = usePortals()







  const [url, setUrl] = useState('')

  const [loading, setLoading] = useState(false)

  const [error, setError] = useState<string | null>(null)

  const [result, setResult] = useState<GenerateResponse | null>(null)

  const [activeTab, setActiveTab] = useState<TabKey>('schema')

  const [copiedKey, setCopiedKey] = useState<CopiedKey>(null)

  const [userProfile, setUserProfile] = useState<UserProfile | null>(null)







  // D34 (2026-06-30): Portal selector state

  const [selectedPortalId, setSelectedPortalId] = useState<string>('')

  const [showAddPortalModal, setShowAddPortalModal] = useState(false)



  // ShortMachine — stan UI (2026-08-20, shadow-dev-01)
  const [smYoutubeId, setSmYoutubeId] = useState<string>('')
  const [smCustomQuery, setSmCustomQuery] = useState<string>('')
  const [smCountEmotional, setSmCountEmotional] = useState<number>(3)
  const [smCountProfessional, setSmCountProfessional] = useState<number>(3)
  const [smCountCustom, setSmCountCustom] = useState<number>(0)
  const [smCandidates, setSmCandidates] = useState<any[]>([])
  const [smPreviewIdx, setSmPreviewIdx] = useState<number | null>(null)
  const [smTitles, setSmTitles] = useState<Record<number, string>>({})
  const [smTags, setSmTags] = useState<Record<number, string[]>>({})
  const [smTitleLoading, setSmTitleLoading] = useState<Record<number, boolean>>({})

  // ShortMachine state restoration (2026-08-20, shadow-dev-01)
  useEffect(() => {
    if (!smYoutubeId) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || '';
    fetch(`${apiBase}/v1/shorts/candidates?youtube_id=${encodeURIComponent(smYoutubeId)}`)
      .then(r => r.json())
      .then(data => {
        if (data.candidates && data.candidates.length > 0) {
          setSmCandidates(data.candidates);
        }
        if (data.jobs && data.jobs.length > 0 && data.candidates) {
          const restoredStatus: Record<number, any> = {};
          data.jobs.forEach((job: any) => {
            const idx = data.candidates.findIndex(
              (c: any) => Math.abs(c.start_sec - job.start_sec) < 1 &&
                          Math.abs(c.end_sec - job.end_sec) < 1
            );
            if (idx >= 0) {
              restoredStatus[idx] = {
                status: job.status,
                result_paths: job.result_paths,
                job_id: job.id,
                error: job.error,
              };
            }
          });
          if (Object.keys(restoredStatus).length > 0) {
            setSmJobStatus(prev => ({ ...restoredStatus, ...prev }));
          }
        }
      })
      .catch(err => console.warn('Failed to restore ShortMachine state:', err));
  }, [smYoutubeId]); // NIE dodawaj smCandidates do deps - petla re-fetch
  const [smLoading, setSmLoading] = useState(false);
  const [smError, setSmError] = useState<string | null>(null);
  const [smRenderConfig, setSmRenderConfig] = useState<Record<number, {format: string, subtitles: string}>>({});
  const [smJobStatus, setSmJobStatus] = useState<Record<number, any>>({});
  const [smTrimAdj, setSmTrimAdj] = useState<Record<number, {startDelta: number; endDelta: number}>>({});
  const [smExpandedIdx, setSmExpandedIdx] = useState<number | null>(null);
  const [smTrimMode, setSmTrimMode] = useState<'start' | 'end'>('start');
  const [smSelected, setSmSelected] = useState<Set<number>>(new Set());
  const [smFormat, setSmFormat] = useState<'raw' | 'short'>('raw');

  const toggleSmSelected = (idx: number) => setSmSelected(prev => {
    const next = new Set(prev);
    if (next.has(idx)) next.delete(idx); else next.add(idx);
    return next;
  });

  const [smTargetYtId, setSmTargetYtId] = useState<Record<number, string>>({});
  const [smPublishAt, setSmPublishAt] = useState<Record<number, string>>({});
  const [smPrivacyStatus, setSmPrivacyStatus] = useState<Record<number, string>>({});
  const [smSelectedPlaylist, setSmSelectedPlaylist] = useState<Record<number, string>>({});
  const [smPlaylists, setSmPlaylists] = useState<{id: string, title: string}[]>([]);
  const [smModalOpenFor, setSmModalOpenFor] = useState<number | null>(null);

  const [ytChannels, setYtChannels] = useState<any[]>([])

  useEffect(() => {
    const channelId = ytChannels[0]?.channel_id;
    if (!channelId) {
      setSmPlaylists([]);
      return;
    }
    const apiBase = process.env.NEXT_PUBLIC_API_URL || '';
    fetch(`${apiBase}/v1/youtube/channels/${channelId}/playlists`)
      .then(r => r.json())
      .then(data => { if (Array.isArray(data)) setSmPlaylists(data); })
      .catch(err => console.warn('Failed to load playlists:', err));
  }, [ytChannels]);


  const fmtSec = (sec: number) => `${Math.floor(sec/60)}:${String(Math.floor(sec%60)).padStart(2,'0')}`;
  const getAdj = (idx: number, c: any) => ({ start: (c.start_sec??0)+(smTrimAdj[idx]?.startDelta??0), end: (c.end_sec??0)+(smTrimAdj[idx]?.endDelta??0) });

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



  const [showInjectModal, setShowInjectModal] = useState(false)



  const [ytModalOpen, setYtModalOpen] = useState(false)



  useEffect(() => {



    if (!session?.accessToken) return



    fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/v1/youtube/channels`, {



      headers: { Authorization: `Bearer ${session.accessToken}` }



    })



      .then((r) => r.ok ? r.json() : [])



      .then((data) => setYtChannels(Array.isArray(data) ? data : []))



      .catch(() => setYtChannels([]))



  }, [session?.accessToken])



  // Portal selector + publication type

  const [publicationType, setPublicationType] = useState<string>('analiza')

  const [focusKeywordOverride, setFocusKeywordOverride] = useState<string>('')

  const [isRefreshingUsage, setIsRefreshingUsage] = useState<boolean>(false)







  // Set default portal when portals load

  useEffect(() => {

    if (portals.length > 0 && !selectedPortalId) {

      setSelectedPortalId(portals[0].id)

    }

  }, [portals, selectedPortalId])







  // Update publicationType when selected portal changes

  useEffect(() => {

    if (selectedPortalId && selectedPortalId !== '__manual__') {

      const portal = portals.find((p) => p.id === selectedPortalId)

      if (portal?.profile?.default_type) {

        setPublicationType(portal.profile.default_type)

      }

    }

  }, [selectedPortalId, portals])







  /**

   * Fetch user profile (plan info + usage quota)

   * PO CO: Wyświetla nazwę planu (np. "Free Tier", "Pro") i stan limitu miesięcznego

   *        z informacją ile wygenerowań zostało.

   */

  const fetchUserProfile = useCallback(async () => {

    try {

      setIsRefreshingUsage(true)

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''

      const res = await fetch(`${apiUrl}/v1/users/me`, {

        headers: {

          ...(accessToken && { Authorization: `Bearer ${accessToken}` }),

        },

      })

      if (res.ok) {

        const data: UserProfile = await res.json()

        setUserProfile(data)

      }

    } catch {

      // Silently fail — profile badge will just not show

    } finally {

      setIsRefreshingUsage(false)

    }

  }, [accessToken])







  useEffect(() => {

    if (status === 'authenticated') {

      fetchUserProfile()

    }

  }, [status, fetchUserProfile])







  /**

   * Kopiowanie do schowka z feedbackiem

   */

  const handleCopy = (text: string, id: string) => {

    navigator.clipboard.writeText(text).then(() => {

      setCopiedKey(id)

      setTimeout(() => setCopiedKey(null), 2000)

    })

  }







  /**

   * Submit formularza — POST /v1/generate

   * D34: Przekazuje portal_id, publication_type, focus_keyword do backendu

   */

  const handleSubmit = async (e: React.FormEvent) => {

    e.preventDefault()

    if (!url.trim()) return



    setLoading(true)

    setError(null)

    setResult(null)



    try {

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''

      const body: Record<string, unknown> = { video_url: url.trim() }



      // Pass portal_id if a saved portal is selected

      if (selectedPortalId && selectedPortalId !== '__manual__') {

        body.portal_id = selectedPortalId

      }



      // Pass publication_type if set

      if (publicationType) {

        body.publication_type = publicationType

      }



      // Pass focus_keyword if user entered an override

      if (focusKeywordOverride.trim()) {

        body.focus_keyword = focusKeywordOverride.trim()

      }



      const res = await fetch(`${apiUrl}/v1/generate`, {

        method: 'POST',

        headers: {

          'Content-Type': 'application/json',

          ...(accessToken && { Authorization: `Bearer ${accessToken}` }),

        },

        body: JSON.stringify(body),

      })



      let data: GenerateResponse

      try {

        data = await res.json()

      } catch {

        throw new Error(`Błąd serwera: HTTP ${res.status}`)

      }



      if (!res.ok) {

        throw new Error(data.error || `HTTP ${res.status}: ${res.statusText}`)

      }



      if (data.status === 'error') {

        throw new Error(data.error || 'Nieznany błąd generatora')

      }



      setResult(data)

      setActiveTab('schema')

      // Refresh usage quota after successful generation

      fetchUserProfile()

    } catch (err: unknown) {

      setError(err instanceof Error ? err.message : 'Wystąpił błąd połączenia z API')

    } finally {

      setLoading(false)

    }

  }







  // Auth redirect

  if (status === 'unauthenticated') {

    router.push('/login')

    return null

  }







  if (status === 'loading') {

    return (

      <div className="min-h-screen bg-black flex items-center justify-center">

        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-500" />

      </div>

    )

  }







  const schema = result?.schema_data

  const chapters = extractChapters(schema)

  const faq = extractFaq(schema)

  const schemaJsonString = schema ? JSON.stringify(schema, null, 2) : ''

  const schemaScriptTag = schemaToScriptTag(schema ?? null)

  const isProOrAgency =

    userProfile?.plan?.id === 'pro' || userProfile?.plan?.id === 'agency'







  return (

    <ErrorBoundary>

    <div className="min-h-screen bg-black text-gray-100 flex flex-col">

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







      {/* Header */}

      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-40">

        <div className="max-w-6xl mx-auto px-4 py-3.5 flex items-center justify-between">

          {/* Logo */}

          <div className="flex items-center gap-3">

            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center font-bold text-white text-sm shadow-lg shadow-violet-500/20">

              V

            </div>

            <div>

              <span className="font-bold text-white tracking-tight">Video SEO Engine</span>

              <span className="text-xs text-gray-500 ml-2 font-mono">v1.0</span>

            </div>

          </div>







          {/* Center Navigation Links (desktop) */}

          <nav className="hidden md:flex items-center gap-1 bg-gray-900/60 border border-gray-800 rounded-xl px-2 py-1">

            <NavItem href="/dashboard" label="Dashboard" active />

            <NavItem href="/historia" label="Historia" />

            <NavItem href="/portale" label="Portale" />

            <NavItem href="/profile" label="Profile SEO" />

            <NavItem href="/ustawienia" label="Ustawienia" />

          </nav>







          {/* User info + Plan badge + Logout */}

          <div className="flex items-center gap-3">

            {userProfile && (

              <div className="flex items-center gap-2 bg-gray-900 border border-gray-800 rounded-xl px-3 py-1.5">

                <div className="text-right">

                  <div className="flex items-center gap-1.5 justify-end">

                    <span className="text-xs font-semibold text-violet-400">

                      {userProfile.plan.display_name}

                    </span>

                    {/* D32: Verified email checkmark */}

                    {userProfile.is_verified && (

                      <span

                        className="text-xs text-emerald-400 cursor-default"

                        title="Adres email zweryfikowany"

                      >

                        ✓

                      </span>

                    )}

                  </div>

                  <p className="text-xs text-gray-400 flex items-center gap-1">

                    {isRefreshingUsage ? (

                      <span className="inline-block w-2.5 h-2.5 border border-violet-400 border-t-transparent rounded-full animate-spin" />

                    ) : (

                      <span>{userProfile.usage.used_this_month} / {userProfile.usage.quota}</span>

                    )}

                    <span className="text-gray-600">użyto</span>

                  </p>

                </div>

                <div className="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center text-xs font-bold text-gray-300">

                  {userProfile.email[0].toUpperCase()}

                </div>

              </div>

            )}







            <button

              onClick={() => signOut({ callbackUrl: '/login' })}

              className="px-3 py-1.5 text-xs text-gray-400 hover:text-white bg-gray-900 hover:bg-gray-800 border border-gray-800 hover:border-gray-700 rounded-xl transition-all"

            >

              Wyloguj

            </button>

          </div>

        </div>

      </header>







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

                      {schema.quotes.map((q, idx) => (

                        <blockquote

                          key={idx}

                          className="border-l-2 border-fuchsia-500/50 pl-3 py-1 text-sm text-gray-300 italic"

                        >

                          &ldquo;{q.text}&rdquo;

                          {q.author && (

                            <span className="not-italic text-xs text-gray-500 ml-2">— {q.author}</span>

                          )}

                        </blockquote>

                      ))}

                    </div>

                  </ResultSection>

                )}







                {/* FAQ */}

                {faq.length > 0 && (

                  <ResultSection

                    title="Najczęściej zadawane pytania (FAQ)"

                    copyText={faqToHtml(faq)}

                    copyId="faq_html"

                    copiedKey={copiedKey}

                    onCopy={handleCopy}

                    badge={`${faq.length} pytań`}

                  >

                    <div className="space-y-3">

                      {faq.map((f, idx) => (

                        <div key={idx} className="bg-gray-950 p-3 rounded-lg border border-gray-800">

                          <p className="text-xs font-semibold text-violet-300 mb-1">

                            P: {f.question}

                          </p>

                          <p className="text-xs text-gray-300 leading-relaxed">

                            O: {f.answer}

                          </p>

                        </div>

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

                  title="Znaczniki czasu YouTube (Timestamps)"

                  copyText={chaptersToText(chapters)}

                  copyId="chapters_text"

                  copiedKey={copiedKey}

                  onCopy={handleCopy}

                  badge={`${chapters.length} rozdziałów`}

                >

                  {chapters.length > 0 ? (

                    <div className="space-y-1.5">

                      <p className="text-xs text-gray-500 mb-3">

                        Format gotowy do wklejenia w opisie filmu YouTube:

                      </p>

                      <div className="bg-gray-950 p-3 rounded-lg border border-gray-800 font-mono text-xs space-y-1">

                        {chapters.map((c, idx) => (

                          <div key={idx} className="flex items-center gap-2">

                            <span className="text-violet-400 font-semibold shrink-0">

                              {secToTimestamp(c.startOffset ?? c.time)}

                            </span>

                            <span className="text-gray-500">—</span>

                            <span className="text-gray-300">{c.name ?? c.label ?? '(bez tytułu)'}</span>

                          </div>

                        ))}

                      </div>

                    </div>

                  ) : (

                    <p className="text-xs text-gray-500 italic">

                      Brak wygenerowanych rozdziałów dla tego filmu.

                    </p>

                  )}

                </ResultSection>

              </div>

            )}

            {/* Tab: Opis YouTube */}
            {activeTab === 'youtube' && (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs text-gray-500">
                    Gotowy opis do wklejenia na YouTube lub bezpośredniej publikacji przez API
                  </span>
                  {ytChannels.length > 0 && (
                    <button
                      onClick={() => setYtModalOpen(true)}
                      className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow"
                    >
                      <span>▶️</span>
                      <span>Publikuj na YouTube</span>
                    </button>
                  )}
                </div>

                <ResultSection
                  title="Pełny opis filmu YouTube"
                  copyText={buildYtDescription(schema)}
                  copyId="yt_desc_full"
                  copiedKey={copiedKey}
                  onCopy={handleCopy}
                  badge="YouTube Ready"
                >
                  <pre className="text-xs font-mono text-gray-300 bg-gray-950 p-4 rounded-lg overflow-x-auto whitespace-pre-wrap border border-gray-800 leading-relaxed">
                    {buildYtDescription(schema) || '(Brak danych do wygenerowania opisu)'}
                  </pre>
                </ResultSection>
              </div>
            )}

            {/* Tab: ShortMachine (2026-08-20, shadow-dev-01) */}
            {activeTab === 'shorts' && (
              <div className="space-y-6">
                {/* Formularz analizy */}
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-white mb-3">✂️ ShortMachine — Generator Shorts</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">ID lub URL filmu YouTube</label>
                      <input
                        type="text"
                        placeholder="np. dQw4w9WgXcQ lub pełny URL"
                        value={smYoutubeId}
                        onChange={(e) => {
                          const val = e.target.value;
                          const m = val.match(/(?:v=|youtu\.be\/|\/shorts\/)([A-Za-z0-9_-]{11})/);
                          setSmYoutubeId(m ? m[1] : val);
                        }}
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Zapytanie niestandardowe (opcjonalne)</label>
                      <input
                        type="text"
                        placeholder="np. moment o inwestowaniu w nieruchomości"
                        value={smCustomQuery}
                        onChange={(e) => setSmCustomQuery(e.target.value)}
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-violet-500"
                      />
                    </div>
                  </div>

                  {/* Suwaki liczby kandydatów */}
                  <div className="grid grid-cols-3 gap-4 mb-4 p-3 bg-gray-950 rounded-lg border border-gray-800">
                    <div>
                      <div className="flex justify-between text-xs text-gray-400 mb-1">
                        <span>🔥 Emocjonalne</span>
                        <span className="text-violet-400 font-mono font-semibold">{smCountEmotional}</span>
                      </div>
                      <input
                        type="range" min="0" max="10" value={smCountEmotional}
                        onChange={(e) => setSmCountEmotional(Number(e.target.value))}
                        className="w-full accent-violet-500"
                      />
                    </div>
                    <div>
                      <div className="flex justify-between text-xs text-gray-400 mb-1">
                        <span>👔 Profesjonalne</span>
                        <span className="text-violet-400 font-mono font-semibold">{smCountProfessional}</span>
                      </div>
                      <input
                        type="range" min="0" max="10" value={smCountProfessional}
                        onChange={(e) => setSmCountProfessional(Number(e.target.value))}
                        className="w-full accent-violet-500"
                      />
                    </div>
                    <div>
                      <div className="flex justify-between text-xs text-gray-400 mb-1">
                        <span>🎯 Custom Query</span>
                        <span className="text-violet-400 font-mono font-semibold">{smCountCustom}</span>
                      </div>
                      <input
                        type="range" min="0" max="10" value={smCountCustom}
                        onChange={(e) => setSmCountCustom(Number(e.target.value))}
                        disabled={!smCustomQuery.trim()}
                        className="w-full accent-violet-500 disabled:opacity-30"
                      />
                    </div>
                  </div>

                  <button
                    onClick={async () => {
                      if (!smYoutubeId.trim()) return
                      setSmLoading(true)
                      setSmError(null)
                      try {
                        const apiBase = process.env.NEXT_PUBLIC_API_URL || ''
                        const res = await fetch(`${apiBase}/v1/shorts/candidates`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            youtube_id: smYoutubeId,
                            count_emotional: smCountEmotional,
                            count_professional: smCountProfessional,
                            count_custom: smCountCustom,
                            custom_query: smCustomQuery || undefined,
                          })
                        })
                        if (!res.ok) throw new Error(`Błąd API: ${res.status}`)
                        const data = await res.json()
                        setSmCandidates(data.candidates || [])
                        if (!data.candidates?.length) setSmError('Nie znaleziono kandydatów na Shorty dla tego filmu.')
                      } catch (err: any) {
                        setSmError(err.message || 'Wystąpił błąd')
                      } finally {
                        setSmLoading(false)
                      }
                    }}
                    disabled={smLoading || !smYoutubeId.trim()}
                    className="w-full py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:opacity-90 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-2 shadow-lg shadow-violet-500/20"
                  >
                    {smLoading ? (
                      <><span className="animate-spin inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full" /> Szukam najlepszych momentów...</>
                    ) : (
                      '🔍 Znajdź kandydatów na Shorts'
                    )}
                  </button>

                  {smError && (
                    <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-2.5 mt-3">{smError}</p>
                  )}
                </div>

                {/* Lista kandydatów */}
                {smCandidates.length > 0 && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-gray-300">
                        Znaleziono {smCandidates.length} kandydatów
                      </span>
                      <span className="text-xs text-gray-500">Kliknij ▶️ aby podglądnąć fragment</span>
                    </div>

                    <div className="flex items-center justify-between bg-gray-900 border border-gray-800 rounded-xl px-4 py-3 mb-2">
                      <div className="flex items-center gap-3">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={smSelected.size === smCandidates.length && smCandidates.length > 0}
                            onChange={() => {
                              if (smSelected.size === smCandidates.length) setSmSelected(new Set());
                              else setSmSelected(new Set(smCandidates.map((_, i) => i)));
                            }}
                            className="accent-violet-500 rounded"
                          />
                          <span className="text-xs text-gray-400">
                            {smSelected.size > 0 ? `Zaznaczono: ${smSelected.size}/${smCandidates.length}` : 'Zaznacz wszystkie'}
                          </span>
                        </label>
                        <div className="flex items-center gap-2 ml-4">
                          <span className="text-xs text-gray-400">Format masowy:</span>
                          <select
                            value={smFormat}
                            onChange={(e) => setSmFormat(e.target.value as 'raw' | 'short')}
                            className="bg-gray-800 text-xs text-white border border-gray-700 rounded px-2 py-1"
                          >
                            <option value="raw">🎬 Oryginał (16:9)</option>
                            <option value="short">📱 Pionowy (9:16 + napisy)</option>
                          </select>
                        </div>
                      </div>
                      <button
                        onClick={async () => {
                          const indices = Array.from(smSelected);
                          for (const idx of indices) {
                            const c = smCandidates[idx];
                            const adj = getAdj(idx, c);
                            setSmJobStatus(prev => ({...prev, [idx]: {status: 'queued'}}));
                            try {
                              const apiBase = process.env.NEXT_PUBLIC_API_URL || '';
                              const res = await fetch(`${apiBase}/v1/shorts/render`, {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({
                                  youtube_id: smYoutubeId,
                                  start_sec: adj.start,
                                  end_sec: adj.end,
                                  format: smFormat,
                                  subtitles: smFormat === 'short' ? 'burn' : 'none'
                                })
                              });
                              const data = await res.json();
                              if (data.job_id) {
                                setSmJobStatus(prev => ({...prev, [idx]: {status: 'queued', job_id: data.job_id}}));
                                const poll = setInterval(async () => {
                                  const sRes = await fetch(`${apiBase}/v1/shorts/status/${data.job_id}`);
                                  const sData = await sRes.json();
                                  setSmJobStatus(prev => ({...prev, [idx]: sData}));
                                  if (sData.status === 'done' || sData.status === 'error') clearInterval(poll);
                                }, 3000);
                              }
                            } catch (e: any) {
                              setSmJobStatus(prev => ({...prev, [idx]: {status: 'error', error: e.message}}));
                            }
                          }
                        }}
                        disabled={smSelected.size === 0}
                        className="px-4 py-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:opacity-90 disabled:opacity-40 text-white text-xs font-semibold rounded-lg transition-all"
                      >
                        🚀 Renderuj zaznaczone ({smSelected.size})
                      </button>
                    </div>

                    {smCandidates.map((c: any, i: number) => (
                      <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={smSelected.has(i)}
                              onChange={() => toggleSmSelected(i)}
                              className="accent-violet-500 rounded mt-0.5"
                            />
                            <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-violet-500/20 text-violet-300 border border-violet-500/30">
                              #{i + 1} [{c.candidate_type || 'clip'}]
                            </span>
                            <span className="text-xs font-mono text-gray-400">
                              {fmtSec((c.start_sec??0)+(smTrimAdj[i]?.startDelta??0))} – {fmtSec((c.end_sec??0)+(smTrimAdj[i]?.endDelta??0))}
                            </span>
                            <span className="text-xs text-gray-500">({Math.round((c.duration_sec ?? ((c.end_sec??0) - (c.start_sec??0))) + (smTrimAdj[i]?.endDelta??0) - (smTrimAdj[i]?.startDelta??0))}s)</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                              Wynik: {Math.round((c.score || 0) * 100)}%
                            </span>
                            <button
                              onClick={() => setSmPreviewIdx(smPreviewIdx === i ? null : i)}
                              className="text-xs px-2.5 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg border border-gray-700 transition-colors"
                            >
                              {smPreviewIdx === i ? '⏹️ Zamknij' : '▶️ Podgląd'}
                            </button>
                          </div>
                        </div>

                        {c.hook && (
                          <p className="text-xs text-gray-300 italic bg-gray-950 p-2.5 rounded-lg border border-gray-800/60">
                            💡 <span className="font-semibold text-violet-300">Hook:</span> &ldquo;{c.hook}&rdquo;
                          </p>
                        )}

                        {c.reason && (
                          <p className="text-xs text-gray-400">
                            <span className="text-gray-500">Dlaczego warto:</span> {c.reason}
                          </p>
                        )}

                        {/* Player podglądu iframe YouTube */}
                        {smPreviewIdx === i && (
                          <div className="mt-2 rounded-lg overflow-hidden border border-violet-500/40 bg-black p-2">
                            <iframe
                              width="100%"
                              height="220"
                              src={`https://www.youtube.com/embed/${smYoutubeId}?start=${Math.floor((c.start_sec??0)+(smTrimAdj[i]?.startDelta??0))}&end=${Math.ceil((c.end_sec??0)+(smTrimAdj[i]?.endDelta??0))}&autoplay=1`}
                              title={`Podgląd #${i+1}`}
                              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                              allowFullScreen
                              className="rounded"
                            />
                          </div>
                        )}

                        {/* Tytuł & Tagi — Sekcja AI */}
                        <div className="border-t border-gray-800/60 pt-3 space-y-2">
                          <div className="flex items-center justify-between gap-2">
                            <label className="text-xs font-semibold text-gray-400">💡 Sugerowany tytuł Shorta</label>
                            <button
                              onClick={() => handleRegenerateTitle(i, c)}
                              disabled={smTitleLoading[i]}
                              className="text-xs text-violet-400 hover:text-violet-300 disabled:opacity-50 flex items-center gap-1"
                            >
                              {smTitleLoading[i] ? '⏳ Generuję...' : '🔄 Wygeneruj nowy'}
                            </button>
                          </div>
                          <input
                            type="text"
                            value={smTitles[i] ?? c.suggested_title ?? ''}
                            onChange={(e) => setSmTitles(prev => ({...prev, [i]: e.target.value}))}
                            placeholder="Wpisz lub wygeneruj chwytliwy tytuł..."
                            className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-violet-500"
                          />

                          {/* Tagi */}
                          {(smTags[i] || c.tags) && (
                            <div className="flex flex-wrap gap-1.5 pt-1">
                              {(smTags[i] || c.tags || []).map((tag: string, tIdx: number) => (
                                <span key={tIdx} className="text-xs px-2 py-0.5 rounded-full bg-violet-950/60 border border-violet-800/40 text-violet-300 font-mono">
                                  #{tag.replace(/^#/, '')}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Docięcie / Trim kandydata (2026-08-20, shadow-dev-01) */}
                        <div className="border-t border-gray-800/60 pt-3">
                          <button
                            onClick={() => setSmExpandedIdx(smExpandedIdx === i ? null : i)}
                            className="text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1 font-medium"
                          >
                            ✂️ {smExpandedIdx === i ? 'Ukryj docięcie fragmentu' : 'Dopasuj czas (docięcie)'}
                          </button>
                          {smExpandedIdx === i && (
                            <div className="mt-3 p-3 bg-gray-950 rounded-lg border border-gray-800 space-y-3">
                              <div className="flex gap-2">
                                <button
                                  onClick={() => setSmTrimMode('start')}
                                  className={`flex-1 text-xs py-1 rounded ${smTrimMode === 'start' ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400'}`}
                                >
                                  Dostosuj początek ({fmtSec((c.start_sec??0) + (smTrimAdj[i]?.startDelta??0))})
                                </button>
                                <button
                                  onClick={() => setSmTrimMode('end')}
                                  className={`flex-1 text-xs py-1 rounded ${smTrimMode === 'end' ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400'}`}
                                >
                                  Dostosuj koniec ({fmtSec((c.end_sec??0) + (smTrimAdj[i]?.endDelta??0))})
                                </button>
                              </div>

                              <div className="flex items-center gap-2">
                                <span className="text-xs text-gray-400 w-16">
                                  {smTrimMode === 'start' ? 'Start delta:' : 'Koniec delta:'}
                                </span>
                                <input
                                  type="range"
                                  min="-10"
                                  max="10"
                                  step="0.5"
                                  value={smTrimMode === 'start' ? (smTrimAdj[i]?.startDelta ?? 0) : (smTrimAdj[i]?.endDelta ?? 0)}
                                  onChange={(e) => {
                                    const val = parseFloat(e.target.value)
                                    setSmTrimAdj(prev => ({
                                      ...prev,
                                      [i]: {
                                        startDelta: smTrimMode === 'start' ? val : (prev[i]?.startDelta ?? 0),
                                        endDelta: smTrimMode === 'end' ? val : (prev[i]?.endDelta ?? 0)
                                      }
                                    }))
                                  }}
                                  className="flex-1 accent-violet-500"
                                />
                                <span className="text-xs font-mono text-violet-300 w-12 text-right">
                                  {smTrimMode === 'start' ? `${(smTrimAdj[i]?.startDelta ?? 0) > 0 ? '+' : ''}${smTrimAdj[i]?.startDelta ?? 0}s` : `${(smTrimAdj[i]?.endDelta ?? 0) > 0 ? '+' : ''}${smTrimAdj[i]?.endDelta ?? 0}s`}
                                </span>
                              </div>

                              <div className="flex justify-between text-xs text-gray-500 pt-1">
                                <span>Efektywny czas: <span className="font-mono text-gray-300">{fmtSec((c.start_sec??0)+(smTrimAdj[i]?.startDelta??0))} – {fmtSec((c.end_sec??0)+(smTrimAdj[i]?.endDelta??0))}</span></span>
                                <span>Długość: <span className="font-mono text-gray-300">{Math.round((c.duration_sec ?? ((c.end_sec??0) - (c.start_sec??0))) + (smTrimAdj[i]?.endDelta??0) - (smTrimAdj[i]?.startDelta??0))}s</span></span>
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Sekcja renderowania (2026-08-20, shadow-dev-01) */}
                        <div className="border-t border-gray-800/60 pt-3 space-y-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-3">
                              {/* Format select */}
                              <div className="flex items-center gap-1.5">
                                <label className="text-xs text-gray-400">Format:</label>
                                <select
                                  value={smRenderConfig[i]?.format || 'raw'}
                                  onChange={(e) => setSmRenderConfig(prev => ({
                                    ...prev,
                                    [i]: { ...prev[i], format: e.target.value, subtitles: prev[i]?.subtitles || 'none' }
                                  }))}
                                  className="bg-gray-800 border border-gray-700 text-xs text-gray-200 rounded px-2 py-1 focus:outline-none focus:border-violet-500"
                                >
                                  <option value="raw">🎬 Oryginał (16:9)</option>
                                  <option value="short">📱 Pionowy (9:16)</option>
                                </select>
                              </div>

                              {/* Subtitles select */}
                              <div className="flex items-center gap-1.5">
                                <label className="text-xs text-gray-400">Napisy:</label>
                                <select
                                  value={smRenderConfig[i]?.subtitles || 'none'}
                                  onChange={(e) => setSmRenderConfig(prev => ({
                                    ...prev,
                                    [i]: { ...prev[i], subtitles: e.target.value, format: prev[i]?.format || 'raw' }
                                  }))}
                                  className="bg-gray-800 border border-gray-700 text-xs text-gray-200 rounded px-2 py-1 focus:outline-none focus:border-violet-500"
                                >
                                  <option value="none">Brak</option>
                                  <option value="burn">Wtopione w wideo (Burn-in)</option>
                                </select>
                              </div>
                            </div>

                            {/* Render Button */}
                            <button
                              onClick={async () => {
                                const adj = getAdj(i, c)
                                const fmt = smRenderConfig[i]?.format || 'raw'
                                const subs = smRenderConfig[i]?.subtitles || 'none'
                                setSmJobStatus(prev => ({ ...prev, [i]: { status: 'queued' } }))
                                try {
                                  const apiBase = process.env.NEXT_PUBLIC_API_URL || ''
                                  const res = await fetch(`${apiBase}/v1/shorts/render`, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                      youtube_id: smYoutubeId,
                                      start_sec: adj.start,
                                      end_sec: adj.end,
                                      format: fmt,
                                      subtitles: subs,
                                    })
                                  })
                                  if (!res.ok) throw new Error(`Błąd API: ${res.status}`)
                                  const data = await res.json()
                                  if (data.job_id) {
                                    setSmJobStatus(prev => ({ ...prev, [i]: { status: 'queued', job_id: data.job_id } }))
                                    // Polling
                                    const poll = setInterval(async () => {
                                      try {
                                        const sRes = await fetch(`${apiBase}/v1/shorts/status/${data.job_id}`)
                                        const sData = await sRes.json()
                                        setSmJobStatus(prev => ({ ...prev, [i]: sData }))
                                        if (sData.status === 'done' || sData.status === 'error') {
                                          clearInterval(poll)
                                        }
                                      } catch {
                                        clearInterval(poll)
                                      }
                                    }, 2000)
                                  }
                                } catch (err: any) {
                                  setSmJobStatus(prev => ({ ...prev, [i]: { status: 'error', error: err.message } }))
                                }
                              }}
                              disabled={smJobStatus[i]?.status === 'queued' || smJobStatus[i]?.status === 'processing'}
                              className="px-3 py-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:opacity-90 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-all flex items-center gap-1.5 shadow"
                            >
                              {smJobStatus[i]?.status === 'queued' || smJobStatus[i]?.status === 'processing' ? (
                                <><span className="animate-spin inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full" /> Renderowanie...</>
                              ) : (
                                '🎬 Renderuj ten fragment'
                              )}
                            </button>
                          </div>

                          {/* Status joba & Pobieranie */}
                          {smJobStatus[i] && (
                            <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800 text-xs">
                              {smJobStatus[i].status === 'queued' && (
                                <span className="text-amber-400">⏳ Oczekuje w kolejce...</span>
                              )}
                              {smJobStatus[i].status === 'processing' && (
                                <span className="text-violet-400">⚙️ Renderowanie wideo przez FFmpeg...</span>
                              )}
                              {smJobStatus[i].status === 'error' && (
                                <span className="text-red-400">⚠️ Błąd: {smJobStatus[i].error || 'Nieznany'}</span>
                              )}
                              {smJobStatus[i].status === 'done' && (
                                <div className="space-y-1.5">
                                  <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                                    <span>✔️ Gotowe do pobrania!</span>
                                  </div>
                                  <div className="flex flex-wrap gap-2 pt-1">
                                    {smJobStatus[i].result_paths?.raw_clip && (
                                      <a
                                        href={`${process.env.NEXT_PUBLIC_API_URL || ''}/v1/shorts/download/${smJobStatus[i].job_id || ''}?type=raw`}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="px-2.5 py-1 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded border border-gray-700 flex items-center gap-1"
                                      >
                                        📥 Pobierz 16:9 (MP4)
                                      </a>
                                    )}
                                    {smJobStatus[i].result_paths?.short_clip && (
                                      <a
                                        href={`${process.env.NEXT_PUBLIC_API_URL || ''}/v1/shorts/download/${smJobStatus[i].job_id || ''}?type=short`}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="px-2.5 py-1 bg-violet-600/30 hover:bg-violet-600/50 text-violet-200 rounded border border-violet-500/40 flex items-center gap-1 font-medium"
                                      >
                                        📱 Pobierz 9:16 Short (MP4)
                                      </a>
                                    )}
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                        
                        {/* YouTube Inject Block */}
                        <div className="border-t border-gray-600 pt-3 mt-1">
                          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">► Wstrzyknij metadane na YouTube</p>
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
                      <div className="sticky bottom-4 bg-gray-900/90 backdrop-blur border border-violet-500/40 rounded-xl p-3 flex items-center justify-between shadow-2xl">
                        <span className="text-xs text-violet-300 font-medium">
                          Zaznaczono: {smSelected.size} / {smCandidates.length} klipów
                        </span>
                        <button
                          onClick={() => {}}
                          className="px-4 py-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white text-xs font-semibold rounded-lg shadow"
                        >
                          🚀 Renderuj zaznaczone ({smSelected.size})
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Empty state when no result */}

        {!result && !loading && (

          <div className="text-center py-16 border border-dashed border-gray-800 rounded-2xl">

            <div className="w-12 h-12 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-xl mx-auto mb-3">

              🎬

            </div>

            <h3 className="text-sm font-medium text-gray-300">Brak wygenerowanego SEO</h3>

            <p className="text-xs text-gray-600 mt-1 max-w-sm mx-auto">

              Wklej URL filmu YouTube powyżej i kliknij &ldquo;Generuj SEO&rdquo;, aby rozpocząć analizę.

            </p>

          </div>

        )}

      </main>

      {/* ShortMachine YouTube Inject Modal */}
      {smModalOpenFor !== null && smCandidates[smModalOpenFor] && (() => {
        const i = smModalOpenFor;
        const c = smCandidates[i];
        
        // Mock schema data for short
        const smSchemaData = {
          youtube_description_hook: smTitles[i] || c.suggested_title || c.title || '',
          video_description: c.hook || '',
          youtube_hashtags: smTags[i] || c.tags || []
        };
        const rawInput = smTargetYtId[i] || '';
        const smVideoId = rawInput.match(/(?:v=|youtu\.be\/|\/shorts\/)([A-Za-z0-9_-]{11})/)?.[1] || rawInput;

        return (
          <YouTubePublishModal
            isOpen={true}
            onClose={() => setSmModalOpenFor(null)}
            videoId={smVideoId}
            schemaData={smSchemaData}
            wpUrl=""
            channels={ytChannels}
            accessToken={accessToken || ""}
            apiUrl={process.env.NEXT_PUBLIC_API_URL || ''}
            publishAt={smPublishAt[i]}
            privacyStatus={smPrivacyStatus[i]}
            playlistId={smSelectedPlaylist[i]}
          />
        );
      })()}

      {/* Inject Modal — pass selected portal so isManual=false for Pro/Agency users [vse-dev-37 fix] */}

      {showInjectModal && result && (() => {

        const selectedPortal = portals.find((p) => p.id === selectedPortalId)

        return (

          <InjectModal

            schemaData={result.schema_data as SchemaData}

            videoUrl={url}

            selectedPortalId={selectedPortalId}

            portalName={selectedPortal?.name}

            portalUrl={selectedPortal?.url}

            accessToken={accessToken}

            onClose={() => setShowInjectModal(false)}

            ytChannels={ytChannels}

          />

        )

      })()}



      {/* D34: Add Portal Modal */}

      {showAddPortalModal && (

        <AddPortalModal

          onClose={() => setShowAddPortalModal(false)}

          onSuccess={(newPortalId) => {

            setShowAddPortalModal(false)

            refreshPortals().then(() => {

              setSelectedPortalId(newPortalId)

            })

          }}

        />

      )}



      {/* YouTube Publish Modal */}

      {result && schema && (

        <YouTubePublishModal

          isOpen={ytModalOpen}

          onClose={() => setYtModalOpen(false)}

          videoId={result.video_id}

          schemaData={schema}

          wpUrl={

            selectedPortalId && selectedPortalId !== '__manual__'

              ? (portals.find((p) => p.id === selectedPortalId)?.url || '')

              : ''

          }

          channels={ytChannels}

          accessToken={accessToken || ''}

          apiUrl={process.env.NEXT_PUBLIC_API_URL || ''}

        />

      )}

      {/* Quick WP Configuration Floating Panel (localStorage helper) */}

      <WpQuickPanel />

    </div>

    </ErrorBoundary>

  )

}



// ─── Sub-components ──────────────────────────────────────────────────────────



function NavItem({

  href,

  label,

  active = false,

}: {

  href: string

  label: string

  active?: boolean

}) {

  return (

    <Link

      href={href}

      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${

        active

          ? 'bg-violet-600/20 text-violet-300 border border-violet-500/30'

          : 'text-gray-400 hover:text-white hover:bg-gray-800/50'

      }`}

    >

      {label}

    </Link>

  )

}



/**

 * CO: WpQuickPanel — pływający widget szybkiej konfiguracji WP

 * PO CO: Umożliwia podejrzenie i edycję zapamiętanych danych WordPress

 *        bez konieczności otwierania modala.

 * JAK: Czyta i zapisuje dane z localStorage ('vse_wp_credentials').

 */

function WpQuickPanel() {

  const [open, setOpen] = useState(false)

  const [saved, setSaved] = useState(false)

  const [creds, setCreds] = useState({ wpUrl: '', wpUser: '', wpPassword: '' })



  useEffect(() => {

    setCreds(loadWpCredentials())

  }, [open])



  const handleSave = (e: React.FormEvent) => {

    e.preventDefault()

    saveWpCredentials(creds)

    setSaved(true)

    setTimeout(() => setSaved(false), 2000)

  }



  const isConfigured = Boolean(creds.wpUrl && creds.wpUrl !== 'https://' && creds.wpUser)



  return (

    <div className="fixed bottom-4 right-4 z-30">

      {open ? (

        <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl p-4 w-80 animate-in">

          <div className="flex items-center justify-between mb-3">

            <div className="flex items-center gap-2">

              <span className="text-xs">⚙️</span>

              <span className="text-xs font-semibold text-white">Domyślny WordPress</span>

            </div>

            <button

              onClick={() => setOpen(false)}

              className="text-gray-400 hover:text-white text-xs p-1"

            >

              ✕

            </button>

          </div>



          <form onSubmit={handleSave} className="space-y-2.5">

            <div>

              <label className="block text-xs text-gray-400 mb-1">URL portalu</label>

              <input

                type="text"

                value={creds.wpUrl}

                onChange={(e) => setCreds({ ...creds, wpUrl: e.target.value })}

                placeholder="https://twojportal.pl"

                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-violet-500"

              />

            </div>

            <div>

              <label className="block text-xs text-gray-400 mb-1">Użytkownik WP</label>

              <input

                type="text"

                value={creds.wpUser}

                onChange={(e) => setCreds({ ...creds, wpUser: e.target.value })}

                placeholder="admin"

                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-violet-500"

              />

            </div>

            <div>

              <label className="block text-xs text-gray-400 mb-1">Application Password</label>

              <input

                type="password"

                value={creds.wpPassword}

                onChange={(e) => setCreds({ ...creds, wpPassword: e.target.value })}

                placeholder="xxxx xxxx xxxx xxxx"

                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-violet-500"

              />

            </div>

            <button

              type="submit"

              className="w-full py-2 bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold rounded-lg transition-colors"

            >

              {saved ? '✔️ Zapisano!' : 'Zapisz dane'}

            </button>

          </form>

        </div>

      ) : (

        <button

          onClick={() => setOpen(true)}

          className="flex items-center gap-1.5 px-3 py-2 bg-gray-900/90 hover:bg-gray-800 border border-gray-700 text-gray-300 hover:text-white text-xs font-medium rounded-xl shadow-lg backdrop-blur transition-all"

        >

          <span>⚙️</span>

          <span>WordPress</span>

          {isConfigured && (

            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />

          )}

        </button>

      )}

    </div>

  )

}
