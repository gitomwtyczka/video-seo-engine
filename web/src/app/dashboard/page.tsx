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

// ─── Types ────────────────────────────────────────────────────────────────────

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

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Extract Clip chapters from JSON-LD @graph or top-level chapters array. */
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
  if (Array.isArray(schema.chapters)) return schema.chapters
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
    .map((c) => `${secToTimestamp(c.startOffset)} — ${c.name ?? '(bez tytułu)'}`)
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

// ─── Subcomponents ────────────────────────────────────────────────────────────

/**
 * CO: CopyButton — przycisk kopiowania z feedbackiem
 * PO CO: Umożliwia szybkie skopiowanie dowolnego tekstu do schowka
 *        z wizualnym potwierdzeniem ("✓ Skopiowano" przez 2s).
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
      {active ? '✓ Skopiowano' : (label ?? 'Kopiuj')}
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
 * CO: InjectModal — modalny formularz publikacji na WordPress
 * PO CO: Umożliwia użytkownikom Pro/Agency wstrzyknięcie SEO na WordPress jednym klikiem.
 *        Credentials zapamiętywane w localStorage — nie trzeba ich wpisywać za każdym razem.
 * JAK: Overlay modal z formularzem WP (URL, user, app password, opcjonalny post ID, status draft/publish).
 *      Po kliknięciu "Opublikuj" → POST /v1/inject → wyświetla wynik z linkiem do posta.
 */
function InjectModal({
  schemaData,
  videoUrl,
  onClose,
}: {
  schemaData: SchemaData
  videoUrl: string
  onClose: () => void
}) {
  const initialCreds = loadWpCredentials()
  const [wpUrl, setWpUrl] = useState(initialCreds.wpUrl)
  const [wpUser, setWpUser] = useState(initialCreds.wpUser)
  const [wpPassword, setWpPassword] = useState(initialCreds.wpPassword)
  const [wpPostId, setWpPostId] = useState('')
  const [postStatus, setPostStatus] = useState<'draft' | 'publish'>('draft')
  const [publishing, setPublishing] = useState(false)
  const [publishResult, setPublishResult] = useState<InjectResult | null>(null)
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

  const handlePublish = async () => {
    if (!wpUser || !wpPassword || !wpUrl) {
      setPublishResult({ error: 'Uzupełnij URL portalu, użytkownika i Application Password.' })
      return
    }

    // Save credentials to localStorage
    saveWpCredentials({ wpUrl, wpUser, wpPassword })

    setPublishing(true)
    setPublishResult(null)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const body: Record<string, unknown> = {
        video_url: videoUrl,
        schema_data: schemaData,
        site_config: {
          wp_base_url: wpUrl,
          wp_user: wpUser,
          wp_app_password: wpPassword,
        },
        post_status: postStatus,
      }
      // wp_post_id: jeśli podane → aktualizacja, jeśli puste → nowy post
      if (wpPostId.trim()) {
        body.wp_post_id = parseInt(wpPostId, 10)
      }

      const res = await fetch(`${apiUrl}/v1/inject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      let data: InjectResult
      try { data = await res.json() } catch { data = { error: `HTTP ${res.status}` } }
      setPublishResult(data)
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

          {/* Post ID + Status */}
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

          {/* Publish button */}
          <button
            onClick={handlePublish}
            disabled={publishing}
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
                  <p><span className="font-medium">✓ Sukces!</span>
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
            Dane logowania zapamiętane w przeglądarce (localStorage)
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

// ─── Main Dashboard ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  /**
   * CO: DashboardPage — główny komponent strony /dashboard
   * PO CO: Hub dla użytkownika — generuje SEO z YouTube URL i wyświetla wyniki w czytelnej formie.
   * JAK: useSession z NextAuth → auth guard. Stan lokalny dla URL, wyników, plan usera.
   *      Fetch plan przez /v1/users/me (Bearer token z session.accessToken).
   *      Wyniki wyświetlane w 3 zakładkach: Schemat, Artykuł, Rozdziały.
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

  // Auth guard
  useEffect(() => {
    if (status === 'unauthenticated') router.push('/login')
  }, [status, router])

  // Fetch user plan — needed to conditionally show PublishSection
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
        // silent — plan check is best-effort
      }
    }
    fetchProfile()
  }, [session?.accessToken])

  const isPro =
    userProfile != null &&
    ['pro', 'agency'].includes(userProfile.plan.id)

  // Copy to clipboard with visual feedback
  const handleCopy = useCallback(async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedKey(id)
      setTimeout(() => setCopiedKey(null), 2000)
    } catch {
      // clipboard unavailable — silent
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
        body: JSON.stringify({ video_url: url.trim(), llm_provider: 'claude', lang: 'pl' }),
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
      setActiveTab('article') // default to article tab after generation
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

  // Derived display data
  const schema = result?.raw ?? null
  const chapters = extractChapters(schema)
  const faq = extractFaq(schema)
  const quotes = (schema?.quotes as QuoteItem[] | undefined) ?? []

  const planLabel = userProfile?.plan?.display_name ?? 'Free'
  const usageUsed = userProfile?.usage?.used_this_month ?? 0
  const usageQuota = userProfile?.usage?.quota ?? 5

  return (
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
          <h1 className="text-2xl font-bold text-white mb-1">Video SEO Engine</h1>
          <p className="text-gray-400 mb-8">
            Wklej URL YouTube — AI wygeneruje schema VideoObject + Clip + FAQPage.
          </p>

          {/* ─── URL Form ─────────────────────────────────────────────────── */}
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

          {/* ─── Empty state stats ────────────────────────────────────────── */}
          {!result && !loading && (
            <>
            <div className="grid grid-cols-3 gap-4 mb-8">
              {[
                { label: 'Filmy w tym miesiącu', value: `${usageUsed}/${usageQuota}`, sub: `Plan ${planLabel}` },
                { label: 'Benchmark score', value: '8/10', sub: 'vs 2–3/10 konkurencja' },
                { label: 'Schema standard', value: 'v5.3', sub: 'Google 2026' },
              ].map((stat) => (
                <div key={stat.label} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <p className="text-gray-400 text-sm mb-1">{stat.label}</p>
                  <p className="text-2xl font-bold text-white">{stat.value}</p>
                  <p className="text-xs text-gray-500 mt-1">{stat.sub}</p>
                </div>
              ))}
            </div>

            {/* ─── WP Integration Panel (always visible) ────────────────────── */}
            <WpQuickPanel />
            </>
          )}

          {/* ─── Results ──────────────────────────────────────────────────── */}
          {result && (
            <div>
              {/* Result header */}
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h2 className="text-lg font-semibold text-white">Wyniki SEO</h2>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Video: <span className="font-mono">{result.videoId}</span>
                    {result.time && <> · {result.time.toFixed(1)}s</>}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-sm rounded-full border border-emerald-500/20">
                    ✓ Wygenerowano
                  </span>
                  {isPro && (
                    <button
                      onClick={() => setShowInjectModal(true)}
                      className="px-4 py-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-sm font-medium text-white rounded-full hover:opacity-90 transition-all flex items-center gap-1.5"
                    >
                      🚀 Wyślij do portalu
                    </button>
                  )}
                </div>
              </div>

              {/* ── Tab Bar ───────────────────────────────────────── */}
              <TabBar
                active={activeTab}
                onChange={setActiveTab}
                chaptersCount={chapters.length}
                faqCount={faq.length}
              />

              {/* ── Tab: Schemat ──────────────────────────────────── */}
              {activeTab === 'schema' && (
                <div>
                  {/* Tytuł artykułu */}
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

              {/* ── Tab: Artykuł ──────────────────────────────────── */}
              {activeTab === 'article' && (
                <div>
                  {/* Copy all button */}
                  <div className="flex justify-end mb-4">
                    <CopyButton
                      text={articleToText(schema, faq)}
                      id="article_all"
                      copiedKey={copiedKey}
                      onCopy={handleCopy}
                      label="Kopiuj cały artykuł"
                    />
                  </div>

                  {/* Tytuł */}
                  {schema?.post_title && (
                    <ResultSection
                      title="Tytuł artykułu"
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
                      title="Lead / Wstęp"
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

                  {/* Treść artykułu */}
                  {schema?.article_body && (
                    <ResultSection
                      title="Treść artykułu"
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
                      copyText={quotes.map((q) => `"${q.text ?? ''}" — ${q.author ?? ''}`).join('\n')}
                      copyId="art_quotes"
                      copiedKey={copiedKey}
                      onCopy={handleCopy}
                    >
                      <div className="space-y-3">
                        {quotes.map((q, i) => (
                          <blockquote key={i} className="border-l-2 border-violet-500/50 pl-4">
                            <p className="text-gray-200 text-sm italic">"{q.text ?? ''}"</p>
                            {q.author && (
                              <footer className="text-xs text-gray-500 mt-1">— {q.author}</footer>
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
                              <span className="text-violet-400 group-open:rotate-90 transition-transform inline-block">›</span>
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
                      <p className="text-lg mb-1">📝</p>
                      <p className="text-sm">Brak treści artykułu w wygenerowanej schemie.</p>
                      <p className="text-xs text-gray-600 mt-1">Sprawdź zakładkę Schemat — tam znajdziesz pełne dane JSON-LD.</p>
                    </div>
                  )}
                </div>
              )}

              {/* ── Tab: Rozdziały ────────────────────────────────── */}
              {activeTab === 'chapters' && (
                <div>
                  <ResultSection
                    title={`Rozdziały (${chapters.length})`}
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
                              {secToTimestamp(ch.startOffset)}
                            </span>
                            <span className="text-gray-200 text-sm flex-1">{ch.name ?? '(bez tytułu)'}</span>
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
                        <p className="text-lg mb-1">📑</p>
                        <p className="text-sm">Brak rozdziałów w wygenerowanej schemie.</p>
                        <p className="text-xs text-gray-600 mt-1">Rozdziały wymagają transkryptu z timestampami (format VTT).</p>
                      </div>
                    )}
                  </ResultSection>

                  {/* YouTube-format copy */}
                  {chapters.length > 0 && (
                    <div className="mt-2">
                      <ResultSection
                        title="Format YouTube (do opisu wideo)"
                        copyText={chapters.map((c) => `${secToTimestamp(c.startOffset)} ${c.name ?? ''}`).join('\n')}
                        copyId="chapters_yt"
                        copiedKey={copiedKey}
                        onCopy={handleCopy}
                        badge="Wklej do opisu YT"
                      >
                        <pre className="text-sm text-gray-300 font-mono leading-relaxed">
                          {chapters.map((c) => `${secToTimestamp(c.startOffset)} ${c.name ?? ''}`).join('\n')}
                        </pre>
                      </ResultSection>
                    </div>
                  )}
                </div>
              )}

              {/* ── Action buttons row ─────────────────────────────── */}
              <div className="flex items-center gap-3 mt-6 pt-6 border-t border-gray-800">
                <CopyButton
                  text={schemaToScriptTag(schema)}
                  id="action_schema"
                  copiedKey={copiedKey}
                  onCopy={handleCopy}
                  label="📋 Kopiuj JSON-LD"
                />
                <CopyButton
                  text={articleToText(schema, faq)}
                  id="action_article"
                  copiedKey={copiedKey}
                  onCopy={handleCopy}
                  label="📋 Kopiuj artykuł"
                />
                {isPro && (
                  <button
                    onClick={() => setShowInjectModal(true)}
                    className="px-4 py-1.5 text-xs rounded-lg bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-medium hover:opacity-90 transition-all"
                  >
                    🚀 Wyślij do portalu
                  </button>
                )}
              </div>

              {/* Upsell dla free — widoczny gdy nie jest pro */}
              {!isPro && (
                <div className="mt-4 p-4 bg-gray-900/50 border border-gray-800 rounded-xl flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-300">Automatyczna publikacja na WordPress</p>
                    <p className="text-xs text-gray-500 mt-0.5">Dostępna w planie Pro i Agency</p>
                  </div>
                  <span className="px-3 py-1.5 text-xs bg-violet-500/10 text-violet-400 border border-violet-500/20 rounded-lg">
                    Ulepsz plan →
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {/* Inject Modal */}
      {showInjectModal && result && (
        <InjectModal
          schemaData={result.raw}
          videoUrl={result.inputUrl}
          onClose={() => setShowInjectModal(false)}
        />
      )}
    </div>
  )
}

// ─── NavItem ──────────────────────────────────────────────────────────────────

/**
 * CO: NavItem — element nawigacji w sidebarze z routingiem
 * PO CO: Spójna wizualnie nawigacja z aktywnym stanem i prawdziwymi linkami.
 * JAK: Next.js Link z ikoną SVG i labelem, highlight gdy active=true.
 */
function NavItem({ icon, label, href, active }: { icon: string; label: string; href: string; active?: boolean }) {
  const icons: Record<string, React.ReactNode> = {
    grid: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    ),
    clock: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    settings: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
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
      {icons[icon]}
      {label}
    </Link>
  )
}

// ─── WpQuickPanel ─────────────────────────────────────────────────────────────

/**
 * CO: WpQuickPanel — stały panel konfiguracji WordPress na dashboardzie
 * PO CO: Użytkownik widzi panel WP OD RAZU po zalogowaniu — nie musi generować
 *        schema żeby zobaczyć sekcję publikacji. Credentials zapamiętane w localStorage.
 * JAK: Collapsible panel z formularzem WP credentials. Pokazuje status połączenia.
 */
function WpQuickPanel() {
  const [expanded, setExpanded] = useState(false)
  const creds = loadWpCredentials()
  const hasCredentials = creds.wpUser && creds.wpPassword && creds.wpUrl !== 'https://'

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden mb-8">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-800/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-sm">
            🔗
          </div>
          <div className="text-left">
            <p className="text-sm font-medium text-white">Integracja WordPress</p>
            <p className="text-xs text-gray-500">
              {hasCredentials ? `Skonfigurowano: ${creds.wpUrl}` : 'Skonfiguruj portal do publikacji'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {hasCredentials && (
            <span className="px-2 py-0.5 text-xs bg-emerald-500/10 text-emerald-400 rounded-full border border-emerald-500/20">
              ✓ Połączono
            </span>
          )}
          <svg
            className={`w-4 h-4 text-gray-500 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>
      {expanded && (
        <div className="px-5 pb-5 border-t border-gray-800">
          <p className="text-xs text-gray-400 mt-3 mb-3">
            Dane logowania będą użyte przy publikacji artykułu. Zapamiętywane w przeglądarce (localStorage).
          </p>
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">URL portalu WordPress</label>
              <input
                type="text"
                defaultValue={creds.wpUrl}
                onBlur={(e) => saveWpCredentials({ ...loadWpCredentials(), wpUrl: e.target.value })}
                placeholder="https://twojportal.pl"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Użytkownik WP</label>
                <input
                  type="text"
                  defaultValue={creds.wpUser}
                  onBlur={(e) => saveWpCredentials({ ...loadWpCredentials(), wpUser: e.target.value })}
                  placeholder="admin"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Application Password</label>
                <input
                  type="password"
                  defaultValue={creds.wpPassword}
                  onBlur={(e) => saveWpCredentials({ ...loadWpCredentials(), wpPassword: e.target.value })}
                  placeholder="xxxx xxxx xxxx xxxx"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
