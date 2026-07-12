'use client'

/**

 * CO: Dashboard Ă”Ă‡Ă¶ gâ”ĽĂ©â”śâ”‚wny widok aplikacji po zalogowaniu

 * PO CO: Daje uâ”Ľâ•ťytkownikowi dwie â”ĽĹ¤cieâ”Ľâ•ťki:

 *   A (Free/Starter) Ă”Ă‡Ă¶ generuje SEO i pokazuje gotowe snippety HTML do skopiowania

 *   B (Pro/Agency)   Ă”Ă‡Ă¶ dodatkowo umoâ”Ľâ•ťliwia automatycznâ”€ĹŻ publikacjâ”€Ă– na WordPress

 * JAK: Wywoâ”ĽĂ©uje POST /v1/generate Ă”Ä‡Äş schema_data Ă”Ä‡Äş renderuje 3 zakâ”ĽĂ©adki wynikowe

 *      (Schemat, Artykuâ”ĽĂ©, Rozdziaâ”ĽĂ©y). Dla planu pro/agency InjectModal Ă”Ä‡Äş POST /v1/inject.

 *

 * ROUTING NOTE: Frontend uâ”Ľâ•ťywa pustego prefixu ('') jako fallback dla NEXT_PUBLIC_API_URL.

 * Wywoâ”ĽĂ©ania idâ”€ĹŻ na /v1/generate, /v1/inject, /v1/users/me.

 * Nginx routuje location /v1/ Ă”Ä‡Äş FastAPI :8085 (bez strippowania prefixu).

 * NIE uâ”Ľâ•ťywamy /api/v1/* Ă”Ă‡Ă¶ nginx /api/ nie strippuje /api i FastAPI zwraca 404.

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





// Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Types Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡



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

type TabKey = 'schema' | 'article' | 'chapters'



// Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Helpers Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡



/**

 * Extract Clip chapters from JSON-LD @graph or top-level chapters array.

 *

 * CO: Normalizuje format rozdziaâ”ĽĂ©â”śâ”‚w do ChapterItem[].

 * PO CO: Backend (generator.py) zwraca chapters jako {time, label, matched, anchor_text}.

 *        Frontend oczekiwaâ”ĽĂ© {startOffset, name, endOffset} Ă”Ă‡Ă¶ powodowaâ”ĽĂ©o "(bez tytuâ”ĽĂ©u)" i "?".

 * JAK: Sprawdza @graph (JSON-LD Clip), nastâ”€Ă–pnie normalizes top-level chapters

 *      mapujâ”€ĹŻc labelĂ”Ä‡Äşname i timeĂ”Ä‡ÄşstartOffset.

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

    // Normalize backend format {time, label} Ă”Ä‡Äş frontend format {startOffset, name}

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



/** Build copyable chapters text: "MM:SS Ă”Ă‡Ă¶ Tytuâ”ĽĂ©" per line. */

function chaptersToText(chapters: ChapterItem[]): string {

  return chapters

    .map((c) => `${secToTimestamp(c.startOffset ?? c.time)} Ă”Ă‡Ă¶ ${c.name ?? c.label ?? '(bez tytuâ”ĽĂ©u)'}`)

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

  return `<h3>Czâ”€Ă–sto zadawane pytania</h3>\n${items}`

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



// Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Subcomponents Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡



/**

 * CO: CopyButton Ă”Ă‡Ă¶ przycisk kopiowania z feedbackiem

 * PO CO: Umoâ”Ľâ•ťliwia szybkie skopiowanie dowolnego tekstu do schowka

 *        z wizualnym potwierdzeniem ("Ă”ĹĄĂ´ Skopiowano" przez 2s).

 * JAK: Uâ”Ľâ•ťywa navigator.clipboard.writeText, przekazuje copied-key do rodzica.

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

      {active ? 'Ă”ĹĄĂ´ Skopiowano' : (label ?? 'Kopiuj')}

    </button>

  )

}



/**

 * CO: ResultSection Ă”Ă‡Ă¶ pojedyncza sekcja wynikowa z nagâ”ĽĂ©â”śâ”‚wkiem i przyciskiem Kopiuj

 * PO CO: Zapewnia spâ”śâ”‚jny wyglâ”€ĹŻd wszystkich pâ”śâ”‚l wynikowych.

 * JAK: Opakowuje dowolny content children w ramkâ”€Ă– z nagâ”ĽĂ©â”śâ”‚wkiem i przyciskiem kopiowania.

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

 * CO: TabBar Ă”Ă‡Ă¶ przeâ”ĽĂ©â”€ĹŻcznik zakâ”ĽĂ©adek Schemat/Artykuâ”ĽĂ©/Rozdziaâ”ĽĂ©y

 * PO CO: Pozwala uâ”Ľâ•ťytkownikowi przeâ”ĽĂ©â”€ĹŻczaâ”€Ă§ widok wynikâ”śâ”‚w bez przeâ”ĽĂ©adowania strony.

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

    { key: 'article', label: 'Artykuâ”ĽĂ©', badge: faqCount > 0 ? faqCount : undefined },

    { key: 'chapters', label: 'Rozdziaâ”ĽĂ©y', badge: chaptersCount > 0 ? chaptersCount : undefined },

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

 * CO: InjectModal Ă”Ă‡Ă¶ modalny formularz publikacji na WordPress z dropdown portalâ”śâ”‚w

 * PO CO: Umoâ”Ľâ•ťliwia uâ”Ľâ•ťytkownikom Pro/Agency wstrzykniâ”€Ă–cie SEO na WordPress jednym klikiem.

 *        Portale zapisane w bazie danych (/v1/portals) Ă”Ă‡Ă¶ dropdown z auto-fill credentials.

 *        Fallback: râ”€Ă–czne wpisanie credentials (zapisywane w localStorage).

 * JAK: usePortals() Ă”Ä‡Äş dropdown z listâ”€ĹŻ portali Ă”Ä‡Äş wybâ”śâ”‚r portalu Ă”Ä‡Äş getCredentials() Ă”Ä‡Äş auto-fill.

 *      Po klikniâ”€Ă–ciu "Opublikuj" Ă”Ä‡Äş POST /v1/inject Ă”Ä‡Äş wyâ”ĽĹ¤wietla wynik z linkiem do posta.

 */

function InjectModal({

  schemaData,

  videoUrl,

  selectedPortalId,

  portalName,

  portalUrl,
  accessToken,

  onClose,

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



  const handlePublish = async () => {

    const isPublishingToWp = !isManual || (wpUser && wpPassword && wpUrl)

    if (!isPublishingToWp && selectedYtChannelIds.length === 0) {

      setPublishResult({ error: 'UzupeĹ‚nij URL portalu, uĹĽytkownika i Application Password lub wybierz kanaĹ‚ YouTube.' })

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

        let errStr = data?.detail || data?.error || `Bâ”ĽĂ©â”€ĹŻd serwera (HTTP ${res.status})`;

        if (typeof errStr === 'object') {

            errStr = JSON.stringify(errStr, null, 2);

        }

        throw new Error(errStr);

      }

      setPublishResult(data)

      if (data?.yt_results) {

        const errors: string[] = [];

        Object.entries(data.yt_results).forEach(([chId, status]) => {

          if (status !== "ok") errors.push(`BĹ‚Ä…d YT: ${status}`);

        });

        if (errors.length > 0) {

          setPublishResult(prev => ({

            ...prev,

            error: (prev?.error ? prev.error + "\n" : "") + errors.join("\n")

          }))

        }

      }

    } catch (e: unknown) {

      setPublishResult({ error: e instanceof Error ? e.message : 'Bâ”ĽĂ©â”€ĹŻd poâ”ĽĂ©â”€ĹŻczenia' })

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

              Â­ÄŤĂśĂ‡

            </div>

            <div>

              <h3 className="font-semibold text-white">Publikuj na WordPress</h3>

              <p className="text-xs text-gray-400">Wyâ”ĽĹ¤lij artykuâ”ĽĂ© + SEO schema na portal</p>

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

            <p className="text-xs text-gray-500 mb-1">Artykuâ”ĽĂ© do publikacji:</p>

            <p className="text-sm font-medium text-white truncate">

              {schemaData.post_title ?? '(brak tytuâ”ĽĂ©u)'}

            </p>

            {schemaData.meta_description && (

              <p className="text-xs text-gray-400 mt-1 line-clamp-2">

                {schemaData.meta_description}

              </p>

            )}

          </div>



          {/* Selected portal info Ă”Ă‡Ă¶ visible in portal mode */}

          {!isManual && portalName && (

            <div className="flex items-center gap-2 px-3 py-2 bg-violet-500/5 border border-violet-500/15 rounded-lg mb-4">

              <span className="text-xs text-violet-400">Â­ÄŤĂ¶Ĺš</span>

              <span className="text-sm text-gray-200">Publikujesz na: <span className="font-semibold">{portalName}</span></span>

              <span className="text-xs text-gray-500 ml-auto">{portalUrl}</span>

            </div>

          )}



          {/* Manual credentials Ă”Ă‡Ă¶ visible only when manual mode or no portals */}

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

                  <label className="block text-xs text-gray-400 mb-1.5">Uâ”Ľâ•ťytkownik WP</label>

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

          {ytChannels && ytChannels.length > 0 && (

            <div className="mb-4">

              <label className="block text-xs text-gray-400 mb-1.5">Dodatkowo: Opublikuj opis na YouTube</label>

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

            </div>

          )}



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

                placeholder="Puste = nowy artykuâ”ĽĂ©"

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

              <option value="video">Â­ÄŤĂ„ÄŚ Film (video)</option>

              <option value="standard">Â­ÄŤĂ´Ă¤ Standard</option>

              <option value="gallery">Â­ÄŤÄľâ•ťÂ´ĹžÄ† Galeria (gallery)</option>

              <option value="quote">Â­ÄŤÄşÄŚ Cytat (quote)</option>

            </select>

            <p className="text-xs text-gray-600 mt-1">Domyâ”ĽĹ¤lnie: Film Ă”Ă‡Ă¶ optymalny dla treâ”ĽĹ¤ci video SEO</p>

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

              <>Â­ÄŤĂśĂ‡ Opublikuj na portalu</>

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

                <><span className="font-medium">Ă”ĂśĂˇÂ´ĹžÄ† Bâ”ĽĂ©â”€ĹŻd:</span> {publishResult.error}</>

              ) : (

                <div className="space-y-1">

                  <p><span className="font-medium">Ă”ĹĄĂ´ Sukces!</span>

                    {publishResult.created ? ' Utworzono nowy artykuâ”ĽĂ©' : ' Zaktualizowano artykuâ”ĽĂ©'}

                    {publishResult.wp_post_id && ` (ID: ${publishResult.wp_post_id})`}

                  </p>

                  {publishResult.post_url && (

                    <a

                      href={publishResult.post_url}

                      target="_blank"

                      rel="noopener noreferrer"

                      className="inline-flex items-center gap-1 text-emerald-300 hover:text-emerald-200 underline underline-offset-2"

                    >

                      Otwâ”śâ”‚rz artykuâ”ĽĂ© na portalu Ă”Ä‡Äş

                    </a>

                  )}

                </div>

              )}

            </div>

          )}



          <p className="text-xs text-gray-600 text-center">

            {isManual ? 'Dane logowania zapamiâ”€Ă–tane w przeglâ”€ĹŻdarce (localStorage)' : 'Credentials pobrane z zapisanego portalu'}

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





// Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ AddPortalModal Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡

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

  const [newProfileType, setNewProfileType] = useState('full_analysis')

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

      .replace(/[â”€ĹŻâ”śĂˇâ”śĂ­â”śĂłâ”śĂşâ”śÄ„â”śÄ…]/g, 'a').replace(/[â”€Ă§â”€Ĺąâ”śĹľ]/g, 'c')

      .replace(/[â”€Ă–â”śÄâ”śÄ™â”śÂ¬â”śĹş]/g, 'e').replace(/[â”śÄŚâ”śĹźâ”śÂ«â”śÂ»]/g, 'i')

      .replace(/[â”ĽĂ©â”€ĹĽ]/g, 'l').replace(/[â”ĽĂ¤â”śâ–’â”ĽĹ‚]/g, 'n')

      .replace(/[â”śâ”‚â”śâ–“â”śâ”¤â”śĂâ”śĂ‚â”ĽÄą]/g, 'o').replace(/[â”ĽĹ¤â”ĽĂ­â”ĽÄŤ]/g, 's')

      .replace(/[â”śâ•Łâ”śâ•‘â”śâ•—â”śâ•ťâ”Ľâ–’]/g, 'u').replace(/[â”śĹ»â”śâ”]/g, 'y')

      .replace(/[â”Ľâ•‘â”Ľâ•ťâ”ĽĹĽ]/g, 'z').replace(/[â”€Äąâ”śâ–‘]/g, 'd')

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

      setError('Uzupeâ”ĽĂ©nij wszystkie pola.')

      return

    }



    // Validate new profile fields if creating inline

    if (showNewProfileForm) {

      if (!newProfileBrand.trim()) {

        setError('Podaj nazwâ”€Ă– brandu dla nowego profilu.')

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

          setError('Nazwa portalu jest za krâ”śâ”‚tka (min. 3 znaki).')

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

          setError('Nie udaâ”ĽĂ©o siâ”€Ă– utworzyâ”€Ă§ profilu. Sprawdâ”Ľâ•‘ dane.')

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

        setError('Nie udaâ”ĽĂ©o siâ”€Ă– utworzyâ”€Ă§ portalu.')

      }

    } catch (e: unknown) {

      setError(e instanceof Error ? e.message : 'Bâ”ĽĂ©â”€ĹŻd podczas zapisu')

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

              placeholder="https://biznesciti.com"

              className={inputClass}

            />

          </div>

          {/* WP credentials */}

          <div className="grid grid-cols-2 gap-3">

            <div>

              <label className="block text-xs text-gray-400 mb-1.5">Uâ”Ľâ•ťytkownik WP</label>

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



          {/* Profile selector Ă”Ă‡Ă¶ dynamic from useProfiles() + inline creation */}

          <div>

            <label className="block text-xs text-gray-400 mb-1.5">Profil treâ”ĽĹ¤ci</label>

            {profilesLoading ? (

              <div className="text-gray-500 text-xs py-2">â”ĽĂĽadowanie profili...</div>

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

                <option value="__new__">+ Utwâ”śâ”‚rz nowy profil</option>

              </select>

            )}

          </div>



          {/* Inline profile creation fields */}

          {showNewProfileForm && (

            <div className="space-y-3 pl-3 border-l-2 border-violet-500/30">

              <p className="text-xs text-violet-400 font-medium">Nowy profil treâ”ĽĹ¤ci</p>



              {/* Site brand */}

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



              {/* Publication type */}

              <div>

                <label className="block text-xs text-gray-400 mb-1">Domyâ”ĽĹ¤lny typ publikacji</label>

                <select

                  value={newProfileType}

                  onChange={(e) => setNewProfileType(e.target.value)}

                  className={selectClass}

                  style={selectStyle}

                >

                  <option value="full_analysis">Full Analysis Ă”Ă‡Ă¶ rozbudowany artykuâ”ĽĂ© SEO</option>

                  <option value="watching_page">Film Ă”Ă‡Ă¶ krâ”śâ”‚tki artykuâ”ĽĂ© z embedem</option>

                  <option value="discover">Discover Ă”Ă‡Ă¶ format Google Discover</option>

                </select>

              </div>



              {/* SEO language */}

              <div>

                <label className="block text-xs text-gray-400 mb-1">Jâ”€Ă–zyk SEO</label>

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



              {/* External link (optional) */}

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

                    placeholder="â”Ľâ•Łrâ”śâ”‚dâ”ĽĂ©o wideo"

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

              {saving ? 'Zapisywanie...' : showNewProfileForm ? 'Â­ÄŤÄşĹĽ Utwâ”śâ”‚rz profil i portal' : 'Zapisz portal'}

            </button>

          </div>

        </div>

      </div>

    </div>

  )

}





/**

 * CO: ManageSubscriptionLink Ă”Ă‡Ă¶ przycisk zarzâ”€ĹŻdzania subskrypcjâ”€ĹŻ Stripe

 * PO CO: Uâ”Ľâ•ťytkownicy Pro/Agency mogâ”€ĹŻ zmieniâ”€Ă§ plan, anulowaâ”€Ă§ lub zaktualizowaâ”€Ă§ kartâ”€Ă–

 *        bez budowania custom UI Ă”Ă‡Ă¶ Stripe Customer Portal.

 * JAK: Wywoâ”ĽĂ©uje GET /v1/payments/portal-session Ă”Ä‡Äş redirect do Stripe Portal.

 */

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

      // silent Ă”Ă‡Ă¶ user stays on dashboard

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

      {loading ? '...' : 'Ă”ĂśĂ– Zarzâ”€ĹŻdzaj subskrypcjâ”€ĹŻ'}

    </button>

  )

}





// Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Main Dashboard Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡



export default function DashboardInner() {

  /**

   * CO: DashboardPage Ă”Ă‡Ă¶ gâ”ĽĂ©â”śâ”‚wny komponent strony /dashboard

   * PO CO: Hub dla uâ”Ľâ•ťytkownika Ă”Ă‡Ă¶ generuje SEO z YouTube URL i wyâ”ĽĹ¤wietla wyniki w czytelnej formie.

   * JAK: useSession z NextAuth Ă”Ä‡Äş auth guard. Stan lokalny dla URL, wynikâ”śâ”‚w, plan usera.

   *      Fetch plan przez /v1/users/me (Bearer token z session.accessToken).

   *      Wyniki wyâ”ĽĹ¤wietlane w 3 zakâ”ĽĂ©adkach: Schemat, Artykuâ”ĽĂ©, Rozdziaâ”ĽĂ©y.

   */

  const { data: session, status } = useSession()

  const router = useRouter()



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



  useEffect(() => {

    if (!session?.accessToken) return

    fetch('/api/youtube/channels', {

      headers: { Authorization: `Bearer ${session.accessToken}` }

    })

      .then((r) => r.ok ? r.json() : [])

      .then((data) => setYtChannels(Array.isArray(data) ? data : []))

      .catch(() => setYtChannels([]))

  }, [session?.accessToken])




  // Portal selector + publication type

  const { portals, loading: portalsLoading } = usePortals()

  const [selectedPortalId, setSelectedPortalId] = useState<string>('')

  const [publicationType, setPublicationType] = useState<string>('full_analysis')

  const [showAddPortalModal, setShowAddPortalModal] = useState(false)



  // Auto-select first portal when loaded

  useEffect(() => {

    if (portals.length > 0 && !selectedPortalId) {

      const defaultPortal = portals.find((p) => p.is_default) ?? portals[0]

      if (defaultPortal) {

        setSelectedPortalId(defaultPortal.id)

      }

    }

  // eslint-disable-next-line react-hooks/exhaustive-deps

  }, [portals])



  // Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Load from history (?job_id in URL) Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡

  const accessToken = (session as any)?.accessToken as string | undefined;

  const { jobId, jobData, jobLoading, jobError } = useJobLoader(accessToken);



  // When jobData arrives from history, populate result state

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



  // Auth guard

  useEffect(() => {

    if (status === 'unauthenticated') router.push('/login')

  }, [status, router])



  // Fetch user plan Ă”Ă‡Ă¶ needed to conditionally show PublishSection

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

        // silent Ă”Ă‡Ă¶ plan check is best-effort

      }

    }

    fetchProfile()

  }, [session?.accessToken])



  const isPro =

    (userProfile != null && ['pro', 'agency'].includes(userProfile.plan.id)) ||

    (userProfile == null && ['pro', 'agency'].includes((session?.user as any)?.plan ?? ''))



  // Copy to clipboard with visual feedback

  const handleCopy = useCallback(async (text: string, id: string) => {

    try {

      await navigator.clipboard.writeText(text)

      setCopiedKey(id)

      setTimeout(() => setCopiedKey(null), 2000)

    } catch {

      // clipboard unavailable Ă”Ă‡Ă¶ silent

    }

  }, [])



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

        throw new Error(`Serwer zwrâ”śâ”‚ciâ”ĽĂ© nieprawidâ”ĽĂ©owâ”€ĹŻ odpowiedâ”Ľâ•‘ (HTTP ${res.status})`)

      }



      if (!res.ok) {

        const detail = (data as unknown as { detail?: string | { msg: string }[] })?.detail

        if (Array.isArray(detail)) throw new Error(detail.map((d) => d.msg).join(', '))

        throw new Error(typeof detail === 'string' ? detail : `Bâ”ĽĂ©â”€ĹŻd serwera: HTTP ${res.status}`)

      }

      if (!data) throw new Error('Pusta odpowiedâ”Ľâ•‘ serwera')

      if (data.error) throw new Error(data.error)



      const schema = data.schema_data ?? null

      if (!schema) throw new Error('Serwer nie zwrâ”śâ”‚ciâ”ĽĂ© schema_data')



      setResult({ raw: schema, videoId: data.video_id, time: data.processing_time_s, inputUrl: url.trim() })

      setActiveTab('article') // default to article tab after generation

    } catch (err: unknown) {

      setError(err instanceof Error ? err.message : 'Nieznany bâ”ĽĂ©â”€ĹŻd')

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



  // Derived display data

  const schema = result?.raw ?? null

  const chapters = extractChapters(schema)

  const faq = extractFaq(schema)

  const quotes = (schema?.quotes as QuoteItem[] | undefined) ?? []



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

          {/* Usage bar */}

          <div className="mb-3">

            <div className="flex justify-between text-xs text-gray-500 mb-1">

              <span>Uâ”Ľâ•ťyto</span>

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

          {/* Plan actions Ă”Ă‡Ă¶ Stripe integration */}

          <div className="flex flex-col gap-1 mb-3">

            <a

              href="/cennik"

              className="text-xs text-gray-400 hover:text-violet-300 transition-colors py-0.5"

            >

              Ă”Ä‡Äą Zmieâ”ĽĂ¤ plan

            </a>

            {userProfile?.plan?.id !== 'free' && (

              <ManageSubscriptionLink accessToken={(session as { accessToken?: string })?.accessToken} />

            )}

          </div>

          <button

            onClick={() => signOut({ callbackUrl: '/login' })}

            className="w-full text-left text-sm text-gray-400 hover:text-white transition-colors py-1"

          >

            Ă”Ä‡Äş Wyloguj siâ”€Ă–

          </button>

        </div>

      </aside>



      {/* Main content */}

      <main className="ml-64 p-8">

        <div className="max-w-3xl">

          {/* Email verification banner Ă”Ă‡Ă¶ soft enforcement (RODO) */}

          <EmailVerificationBanner

            isVerified={userProfile?.is_verified}

            accessToken={(session as { accessToken?: string })?.accessToken}

          />

          <h1 className="text-2xl font-bold text-white mb-1">Video SEO Engine</h1>

          <p className="text-gray-400 mb-8">

            Wklej URL YouTube Ă”Ă‡Ă¶ AI wygeneruje schema VideoObject + Clip + FAQPage.

          </p>



          {/* Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Job loading from history Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ */}

          {jobLoading && (

            <div className="mb-6 flex items-center gap-3 p-4 bg-violet-500/5 border border-violet-500/20 rounded-xl">

              <span className="animate-spin inline-block w-4 h-4 border-2 border-violet-300/30 border-t-violet-400 rounded-full" />

              <span className="text-sm text-violet-300">â”ĽĂĽadowanie wynikâ”śâ”‚w z historii...</span>

            </div>

          )}

          {jobError && (

            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">

              Ă”ĂśĂˇÂ´ĹžÄ† {jobError}

            </div>

          )}

          {jobId && result && (

            <div className="mb-6 flex items-center gap-2 p-3 bg-blue-500/5 border border-blue-500/20 rounded-xl">

              <span className="text-xs text-blue-400">Â­ÄŤĂ´Ĺ‘ Wyniki zaâ”ĽĂ©adowane z historii</span>

              <Link href="/historia" className="text-xs text-gray-500 hover:text-white ml-auto transition-colors">

                Ă”Ä‡Ă‰ Wrâ”śâ”‚â”€Ă§ do historii

              </Link>

            </div>

          )}



          {/* Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Portal & Publication Type Selector Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ */}

          <div className="grid grid-cols-2 gap-3 mb-5">

            {/* Portal selector */}

            <div>

              <label className="block text-xs text-gray-400 mb-1.5">Portal docelowy</label>

              {portalsLoading ? (

                <div className="flex items-center gap-2 h-[42px] text-sm text-gray-500">

                  <span className="animate-spin inline-block w-3 h-3 border border-gray-500 border-t-violet-400 rounded-full" />

                  â”ĽĂĽadowanie...

                </div>

              ) : portals.length === 0 ? (

                <select

                  value=""

                  onChange={(e) => {

                    const val = e.target.value;

                    if (val === '__add__') {

                      setShowAddPortalModal(true);

                    } else if (val === '__manual__') {

                      setSelectedPortalId('__manual__');

                    }

                  }}

                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer"

                  style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3E%3Cpath stroke=\'%236b7280\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.75rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }}

                >

                  <option value="" disabled>Brak portali Ă”Ă‡Ă¶ dodaj pierwszy portal</option>

                  <option value="__add__">+ Dodaj nowy portal...</option>

                  <option value="__manual__">Ă”ĹĄÄ†Â´ĹžÄ† Wpisz râ”€Ă–cznie...</option>

                </select>

              ) : (

                <select

                  id="portal-selector"

                  value={selectedPortalId}

                  onChange={(e) => {

                    const val = e.target.value;

                    if (val === '__add__') {

                      setShowAddPortalModal(true);

                    } else if (val === '__manual__') {

                      setSelectedPortalId('__manual__');

                    } else {

                      setSelectedPortalId(val);

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

                  <option value="__manual__">Ă”ĹĄÄ†Â´ĹžÄ† Wpisz râ”€Ă–cznie...</option>

                </select>

              )}

            </div>



            {/* Publication type selector */}

            <div>

              <label className="block text-xs text-gray-400 mb-1.5">Typ publikacji</label>

              <select

                id="publication-type-selector"

                value={publicationType}

                onChange={(e) => setPublicationType(e.target.value)}

                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer"

                style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3E%3Cpath stroke=\'%236b7280\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.75rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }}

              >

                <option value="full_analysis">Â­ÄŤĂ´Ĺ Peâ”ĽĂ©na analiza</option>

                <option value="watching_page">Â­ÄŤĂ„ÄŚ Strona z filmem</option>

                <option value="discover">Â­ÄŤĂ¶Ĺą Discover</option>

              </select>

            </div>

          </div>



          {/* Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ URL Form Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ */}

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

                  <><span className="animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> Generujâ”€Ă–...</>

                ) : (

                  <>Ă”ĹĄĹ˝ Generuj SEO</>

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

                <span className="flex-shrink-0 mt-0.5">Ă”ĂśĂˇÂ´ĹžÄ†</span>

                <div>

                  <p className="font-medium mb-0.5">Wystâ”€ĹŻpiâ”ĽĂ© bâ”ĽĂ©â”€ĹŻd</p>

                  <p className="text-red-300/80">{error}</p>

                </div>

              </div>

            )}

          </form>



          {/* Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Empty state stats Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ */}

          {!result && !loading && (

            <>

            <div className="grid grid-cols-3 gap-4 mb-8">

              {[

                { label: 'Filmy w tym miesiâ”€ĹŻcu', value: `${usageUsed}/${usageQuota}`, sub: `Plan ${planLabel}` },

                { label: 'Benchmark score', value: '8/10', sub: 'vs 2Ă”Ă‡Ă´3/10 konkurencja' },

                { label: 'Schema standard', value: 'v5.3', sub: 'Google 2026' },

              ].map((stat) => (

                <div key={stat.label} className="bg-gray-900 border border-gray-800 rounded-xl p-5">

                  <p className="text-gray-400 text-sm mb-1">{stat.label}</p>

                  <p className="text-2xl font-bold text-white">{stat.value}</p>

                  <p className="text-xs text-gray-500 mt-1">{stat.sub}</p>

                </div>

              ))}

            </div>



            {/* Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ WP Integration Panel (always visible) Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ */}

            <WpQuickPanel />

            </>

          )}



          {/* Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Results Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ */}

          {result && (

            <div>

              {/* Result header */}

              <div className="flex items-center justify-between mb-5">

                <div>

                  <h2 className="text-lg font-semibold text-white">Wyniki SEO</h2>

                  <p className="text-xs text-gray-500 mt-0.5">

                    Video: <span className="font-mono">{result.videoId}</span>

                    {result.time && <> â”¬Äš {result.time.toFixed(1)}s</>}

                  </p>

                </div>

                <div className="flex items-center gap-2">

                  <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-sm rounded-full border border-emerald-500/20">

                    Ă”ĹĄĂ´ Wygenerowano

                  </span>

                  {isPro && (

                    <button

                      onClick={() => setShowInjectModal(true)}

                      className="px-4 py-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-sm font-medium text-white rounded-full hover:opacity-90 transition-all flex items-center gap-1.5"

                    >

                      Â­ÄŤĂśĂ‡ Wyâ”ĽĹ¤lij do portalu

                    </button>

                  )}

                  {ytChannels.length > 0 && (

                    <button

                      onClick={() => setYtModalOpen(true)}

                      className="px-4 py-1.5 bg-gradient-to-r from-red-600 to-red-500 text-sm font-medium text-white rounded-full hover:opacity-90 transition-all flex items-center gap-1.5 ml-2"

                    >

                      Ă”ÄľĂ‚Â´ĹžÄ† Wyâ”ĽĹ¤lij na YouTube

                    </button>

                  )}

                </div>

              </div>



              {/* Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Tab Bar Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ */}

              <TabBar

                active={activeTab}

                onChange={setActiveTab}

                chaptersCount={chapters.length}

                faqCount={faq.length}

              />



              {/* Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Tab: Schemat Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ */}

              {activeTab === 'schema' && (

                <div>

                  {/* Tytuâ”ĽĂ© artykuâ”ĽĂ©u */}

                  <ResultSection

                    title="Tytuâ”ĽĂ© artykuâ”ĽĂ©u"

                    copyText={schema?.post_title ?? ''}

                    copyId="post_title"

                    copiedKey={copiedKey}

                    onCopy={handleCopy}

                  >

                    <p className="text-white font-medium">{schema?.post_title ?? '(brak tytuâ”ĽĂ©u)'}</p>

                    {schema?.focus_keyphrase && (

                      <p className="text-xs text-gray-500 mt-1">

                        Focus: <span className="text-violet-400">{schema.focus_keyphrase}</span>

                      </p>

                    )}

                  </ResultSection>



                  {/* Meta description */}

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



                  {/* Schema JSON-LD */}

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



              {/* Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Tab: Artykuâ”ĽĂ© Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ */}

              {activeTab === 'article' && (

                <div>

                  {/* Copy all button */}

                  <div className="flex justify-end mb-4">

                    <CopyButton

                      text={articleToText(schema, faq)}

                      id="article_all"

                      copiedKey={copiedKey}

                      onCopy={handleCopy}

                      label="Kopiuj caâ”ĽĂ©y artykuâ”ĽĂ©"

                    />

                  </div>



                  {/* Tytuâ”ĽĂ© */}

                  {schema?.post_title && (

                    <ResultSection

                      title="Tytuâ”ĽĂ© artykuâ”ĽĂ©u"

                      copyText={schema.post_title}

                      copyId="art_title"

                      copiedKey={copiedKey}

                      onCopy={handleCopy}

                    >

                      <h3 className="text-xl font-bold text-white">{schema.post_title}</h3>

                    </ResultSection>

                  )}



                  {/* Lead */}

                  {schema?.lead && (

                    <ResultSection

                      title="Lead / Wstâ”€Ă–p"

                      copyText={schema.lead}

                      copyId="art_lead"

                      copiedKey={copiedKey}

                      onCopy={handleCopy}

                    >

                      <p className="text-gray-200 text-sm leading-relaxed italic">

                        {schema.lead}

                      </p>

                    </ResultSection>

                  )}



                  {/* Treâ”ĽĹ¤â”€Ă§ artykuâ”ĽĂ©u */}

                  {schema?.article_body && (

                    <ResultSection

                      title="Treâ”ĽĹ¤â”€Ă§ artykuâ”ĽĂ©u"

                      copyText={schema.article_body}

                      copyId="art_body"

                      copiedKey={copiedKey}

                      onCopy={handleCopy}

                    >

                      <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">

                        {schema.article_body}

                      </div>

                    </ResultSection>

                  )}



                  {/* Cytaty */}

                  {quotes.length > 0 && (

                    <ResultSection

                      title={`Cytaty (${quotes.length})`}

                      copyText={quotes.map((q) => `"${q.text ?? ''}" Ă”Ă‡Ă¶ ${q.author ?? ''}`).join('\n')}

                      copyId="art_quotes"

                      copiedKey={copiedKey}

                      onCopy={handleCopy}

                    >

                      <div className="space-y-3">

                        {quotes.map((q, i) => (

                          <blockquote key={i} className="border-l-2 border-violet-500/50 pl-4">

                            <p className="text-gray-200 text-sm italic">"{q.text ?? ''}"</p>

                            {q.author && (

                              <footer className="text-xs text-gray-500 mt-1">Ă”Ă‡Ă¶ {q.author}</footer>

                            )}

                          </blockquote>

                        ))}

                      </div>

                    </ResultSection>

                  )}



                  {/* FAQ */}

                  <ResultSection

                    title={`FAQ (${faq.length})`}

                    copyText={faqToHtml(faq)}

                    copyId="art_faq"

                    copiedKey={copiedKey}

                    onCopy={handleCopy}

                    badge="Kopiuj HTML"

                  >

                    {faq.length > 0 ? (

                      <div className="space-y-3">

                        {faq.map((item, i) => (

                          <details key={i} className="group">

                            <summary className="cursor-pointer text-sm font-medium text-white flex items-center gap-2 select-none">

                              <span className="text-violet-400 group-open:rotate-90 transition-transform inline-block">Ă”Ă‡â•‘</span>

                              {item.question ?? '(brak pytania)'}

                            </summary>

                            <p className="ml-4 mt-1.5 text-gray-400 text-sm leading-relaxed">

                              {item.answer ?? '(brak odpowiedzi)'}

                            </p>

                          </details>

                        ))}

                      </div>

                    ) : (

                      <p className="text-gray-500 text-sm">Brak FAQ w wygenerowanej schemie.</p>

                    )}

                  </ResultSection>



                  {/* No article content fallback */}

                  {!schema?.lead && !schema?.article_body && faq.length === 0 && (

                    <div className="text-center py-8 text-gray-500">

                      <p className="text-lg mb-1">Â­ÄŤĂ´Ĺ</p>

                      <p className="text-sm">Brak treâ”ĽĹ¤ci artykuâ”ĽĂ©u w wygenerowanej schemie.</p>

                      <p className="text-xs text-gray-600 mt-1">Sprawdâ”Ľâ•‘ zakâ”ĽĂ©adkâ”€Ă– Schemat Ă”Ă‡Ă¶ tam znajdziesz peâ”ĽĂ©ne dane JSON-LD.</p>

                    </div>

                  )}

                </div>

              )}



              {/* Ă”Ă¶Ă‡Ă”Ă¶Ă‡ Tab: Rozdziaâ”ĽĂ©y Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ */}

              {activeTab === 'chapters' && (

                <div>

                  <ResultSection

                    title={`Rozdziaâ”ĽĂ©y (${chapters.length})`}

                    copyText={chaptersToText(chapters)}

                    copyId="chapters_tab"

                    copiedKey={copiedKey}

                    onCopy={handleCopy}

                  >

                    {chapters.length > 0 ? (

                      <div className="space-y-0.5">

                        {chapters.map((ch, i) => (

                          <div

                            key={i}

                            className="flex items-center gap-4 py-2.5 px-3 rounded-lg hover:bg-gray-800/50 transition-colors group"

                          >

                            <span className="text-violet-400 font-mono text-sm w-14 flex-shrink-0 bg-violet-500/10 px-2 py-1 rounded text-center">

                              {secToTimestamp(ch.startOffset ?? ch.time)}

                            </span>

                            <span className="text-gray-200 text-sm flex-1">{ch.name ?? ch.label ?? '(bez tytuâ”ĽĂ©u)'}</span>

                            {ch.endOffset != null && ch.startOffset != null && (

                              <span className="text-xs text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity">

                                {Math.round(ch.endOffset - ch.startOffset)}s

                              </span>

                            )}

                          </div>

                        ))}

                      </div>

                    ) : (

                      <div className="text-center py-8 text-gray-500">

                        <p className="text-lg mb-1">Â­ÄŤĂ´Äą</p>

                        <p className="text-sm">Brak rozdziaâ”ĽĂ©â”śâ”‚w w wygenerowanej schemie.</p>

                        <p className="text-xs text-gray-600 mt-1">Rozdziaâ”ĽĂ©y wymagajâ”€ĹŻ transkryptu z timestampami (format VTT).</p>

                      </div>

                    )}

                  </ResultSection>



                  {/* YouTube-format copy */}

                  {chapters.length > 0 && (

                    <div className="mt-2">

                      <ResultSection

                        title="Format YouTube (do opisu wideo)"

                        copyText={chapters.map((c) => `${secToTimestamp(c.startOffset ?? c.time)} ${c.name ?? c.label ?? ''}`).join('\n')}

                        copyId="chapters_yt"

                        copiedKey={copiedKey}

                        onCopy={handleCopy}

                        badge="Wklej do opisu YT"

                      >

                        <pre className="text-sm text-gray-300 font-mono leading-relaxed">

                          {chapters.map((c) => `${secToTimestamp(c.startOffset ?? c.time)} ${c.name ?? c.label ?? ''}`).join('\n')}

                        </pre>

                      </ResultSection>

                    </div>

                  )}

                </div>

              )}

            </div>

          )}

        </div>

      </main>



      {/* Inject Modal Ă”Ă‡Ă¶ pass selected portal so isManual=false for Pro/Agency users [vse-dev-37 fix] */}

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
        const hook = result.raw?.youtube_description_hook || result.raw?.youtube_description || "";
        const hashtags = Array.isArray(result.raw?.youtube_hashtags)
          ? result.raw.youtube_hashtags.join(" ")
          : "";
        const parsedChapters = typeof extractChapters === 'function' ? extractChapters(result.raw) : [];
        const chaptersStr = parsedChapters ? parsedChapters.map((c: any) => `${typeof secToTimestamp === 'function' ? secToTimestamp(c.startOffset ?? c.time) : (c.startOffset ?? c.time)} ${c.name ?? c.label ?? ''}`).join('\n') : "";
        const wpUrl = result.raw?.wp_article_url || result.raw?.published_url || "";
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';

        const ytDescription = [
          hook,
          wpUrl ? `\n\nÂ­ÄŤĂ¶Ĺš Peâ”ĽĂ©ny artykuâ”ĽĂ©: ${wpUrl}` : "",
          chaptersStr ? `\n\nĂ”Ä†â–’Â´ĹžÄ† Rozdziaâ”ĽĂ©y:\n${chaptersStr}` : "",
          hashtags ? `\n\n---\n${hashtags}` : "",
        ].join("");

        return (
          <YouTubePublishModal
            isOpen={ytModalOpen}
            onClose={() => setYtModalOpen(false)}
            videoId={result.raw?.video_id || result.inputUrl?.split('v=')[1] || ""}
            description={ytDescription}
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



// Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ NavItem helper Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡



function NavItem({

  icon,

  label,

  href,

  active,

}: {

  icon: string

  label: string

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

      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">

        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={iconPath[icon] ?? ''} />

      </svg>

      {label}

    </Link>

  )

}



// Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡ WpQuickPanel Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡Ă”Ă¶Ă‡



function WpQuickPanel() {

  /**

   * CO: Panel integracji WordPress Ă”Ă‡Ă¶ skrâ”śâ”‚cony widok na pustym stanie dashboardu

   * PO CO: Zachâ”€Ă–ca uâ”Ľâ•ťytkownika do skonfigurowania portalu WP zanim zacznie generowaâ”€Ă§.

   * JAK: Statyczny informacyjny panel, link do ustawieâ”ĽĂ¤.

   */

  return (
    <ErrorBoundary>

    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">

      <div className="flex items-center gap-3 mb-4">

        <div className="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center text-base">Â­ÄŤĂ¶Ĺš</div>

        <div>

          <p className="text-sm font-medium text-white">Integracja WordPress</p>

          <p className="text-xs text-gray-500">Skonfiguruj portal do automatycznej publikacji</p>

        </div>

        <Link

          href="/ustawienia"

          className="ml-auto text-xs text-violet-400 hover:text-violet-300 transition-colors"

        >

          Konfiguruj Ă”Ä‡Äş

        </Link>

      </div>

      <div className="grid grid-cols-3 gap-3">

        {[

          { icon: 'Â­ÄŤĂ´Ĺ‘', label: 'Kopiuj HTML', desc: 'Schemat gotowy do wklejenia' },

          { icon: 'Â­ÄŤĂśĂ‡', label: 'Auto-publish', desc: 'Plan Pro/Agency' },

          { icon: 'Â­ÄŤĂ´Ĺ', label: 'SEO Schema', desc: 'VideoObject + Clip + FAQ' },

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

