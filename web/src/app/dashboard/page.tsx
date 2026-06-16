'use client'
/**
 * CO: Dashboard — główny widok aplikacji po zalogowaniu
 * PO CO: Daje użytkownikowi dwie ścieżki:
 *   A (Free/Starter) — generuje SEO i pokazuje gotowe snippety HTML do skopiowania
 *   B (Pro/Agency)   — dodatkowo umożliwia automatyczną publikację na WordPress
 * JAK: Wywołuje POST /v1/generate → schema_data → renderuje 5 sekcji wynikowych.
 *      Dla planu pro/agency dodatkowo wyświetla PublishSection → POST /v1/inject.
 *
 * ROUTING NOTE: Frontend używa pustego prefixu ('') jako fallback dla NEXT_PUBLIC_API_URL.
 * Wywołania idą na /v1/generate, /v1/inject, /v1/users/me.
 * Nginx routuje location /v1/ → FastAPI :8085 (bez strippowania prefixu).
 * NIE używamy /api/v1/* — nginx /api/ nie strippuje /api i FastAPI zwraca 404.
 */
import { useSession, signOut } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect, useState, useCallback } from 'react'

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
  article_body?: string
  chapters?: ChapterItem[]
  faq?: FaqItem[]
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

type CopiedKey = string | null

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
}: {
  text: string
  id: string
  copiedKey: CopiedKey
  onCopy: (text: string, id: string) => void
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
      {active ? '✓ Skopiowano' : 'Kopiuj'}
    </button>
  )
}

/**
 * CO: ResultSection — pojedyncza sekcja wynikowa z nagłówkiem i przyciskiem Kopiuj
 * PO CO: Zapewnia spójny wygląd wszystkich pól wynikowych (tytuł, meta, schema, FAQ, chapters).
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
 * CO: PublishSection — sekcja automatycznej publikacji na WordPress
 * PO CO: Pozwala użytkownikom Pro/Agency opublikować wygenerowane SEO na WP jednym klikiem.
 *        Eliminuje potrzebę ręcznego kopiowania do WordPressa — oszczędza czas agencjom.
 * JAK: Zbiera WP credentials (URL, user, app_password) + wp_post_id + status (draft/publish),
 *      wywołuje POST /v1/inject z schema_data. Credentials w MVP wpisywane ręcznie.
 */
function PublishSection({ schemaData, videoUrl }: { schemaData: SchemaData; videoUrl: string }) {
  const [wpUrl, setWpUrl] = useState('https://prawy.pl')
  const [wpUser, setWpUser] = useState('')
  const [wpPassword, setWpPassword] = useState('')
  const [wpPostId, setWpPostId] = useState('')
  const [postStatus, setPostStatus] = useState<'draft' | 'publish'>('draft')
  const [publishing, setPublishing] = useState(false)
  const [publishResult, setPublishResult] = useState<{ status?: string; error?: string } | null>(null)

  const handlePublish = async () => {
    if (!wpUser || !wpPassword || !wpPostId) {
      setPublishResult({ error: 'Uzupełnij wszystkie pola WordPress.' })
      return
    }
    setPublishing(true)
    setPublishResult(null)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const res = await fetch(`${apiUrl}/v1/inject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wp_post_id: parseInt(wpPostId, 10),
          video_url: videoUrl,
          schema_data: schemaData,
          site_config: {
            wp_base_url: wpUrl,
            wp_user: wpUser,
            wp_app_password: wpPassword,
          },
        }),
      })
      let data
      try { data = await res.json() } catch { data = { error: `HTTP ${res.status}` } }
      setPublishResult(data)
    } catch (e: unknown) {
      setPublishResult({ error: e instanceof Error ? e.message : 'Błąd połączenia' })
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div className="mt-6 bg-gradient-to-br from-violet-950/40 to-fuchsia-950/20 border border-violet-500/30 rounded-2xl p-6">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center text-sm">
          🚀
        </div>
        <div>
          <h3 className="font-semibold text-white">Publikuj na WordPress</h3>
          <p className="text-xs text-gray-400">Automatyczna publikacja — plan Pro/Agency</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="col-span-2">
          <label className="block text-xs text-gray-400 mb-1">WordPress URL</label>
          <input
            type="text"
            value={wpUrl}
            onChange={(e) => setWpUrl(e.target.value)}
            placeholder="https://twojportal.pl"
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Użytkownik WP</label>
          <input
            type="text"
            value={wpUser}
            onChange={(e) => setWpUser(e.target.value)}
            placeholder="admin"
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">App Password</label>
          <input
            type="password"
            value={wpPassword}
            onChange={(e) => setWpPassword(e.target.value)}
            placeholder="xxxx xxxx xxxx xxxx"
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">ID Posta WP</label>
          <input
            type="number"
            value={wpPostId}
            onChange={(e) => setWpPostId(e.target.value)}
            placeholder="12345"
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
          />
        </div>
        <div className="flex items-end">
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="post_status"
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
                name="post_status"
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

      {publishResult && (
        <div
          className={`mt-3 p-3 rounded-lg text-sm ${
            publishResult.error
              ? 'bg-red-500/10 border border-red-500/20 text-red-400'
              : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
          }`}
        >
          {publishResult.error ? (
            <><span className="font-medium">⚠️ Błąd:</span> {publishResult.error}</>
          ) : (
            <><span className="font-medium">✓ Sukces:</span> status={publishResult.status ?? 'ok'}</>
          )}
        </div>
      )}
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
   */
  const { data: session, status } = useSession()
  const router = useRouter()

  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ raw: SchemaData; videoId: string; time?: number; inputUrl: string } | null>(null)
  const [error, setError] = useState('')
  const [copiedKey, setCopiedKey] = useState<CopiedKey>(null)
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null)

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
          <NavItem icon="grid" label="Dashboard" active />
          <NavItem icon="clock" label="Historia" />
          <NavItem icon="settings" label="Ustawienia" />
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
                <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-sm rounded-full border border-emerald-500/20">
                  ✓ Wygenerowano
                </span>
              </div>

              {/* ── 1. Tytuł artykułu ──────────────────────────────────── */}
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

              {/* ── 2. Meta description ───────────────────────────────── */}
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

              {/* ── 3. Schema JSON-LD ─────────────────────────────────── */}
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

              {/* ── 4. Rozdziały ──────────────────────────────────────── */}
              <ResultSection
                title={`Rozdziały (${chapters.length})`}
                copyText={chaptersToText(chapters)}
                copyId="chapters"
                copiedKey={copiedKey}
                onCopy={handleCopy}
              >
                {chapters.length > 0 ? (
                  <div className="space-y-1">
                    {chapters.map((ch, i) => (
                      <div key={i} className="flex items-center gap-3 py-1.5">
                        <span className="text-violet-400 font-mono text-sm w-12 flex-shrink-0">
                          {secToTimestamp(ch.startOffset)}
                        </span>
                        <span className="text-gray-300 text-sm">{ch.name ?? '(bez tytułu)'}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 text-sm">Brak rozdziałów w wygenerowanej schemie.</p>
                )}
              </ResultSection>

              {/* ── 5. FAQ ────────────────────────────────────────────── */}
              <ResultSection
                title={`FAQ (${faq.length})`}
                copyText={faqToHtml(faq)}
                copyId="faq"
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

              {/* ── Ścieżka B: Publikacja (pro/agency only) ───────────── */}
              {isPro && <PublishSection schemaData={result.raw} videoUrl={result.inputUrl} />}

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
    </div>
  )
}

// ─── NavItem ──────────────────────────────────────────────────────────────────

/**
 * CO: NavItem — element nawigacji w sidebarze
 * PO CO: Spójna wizualnie nawigacja z aktywnym stanem.
 * JAK: Prosty przycisk z ikoną SVG i labelem, highlight gdy active=true.
 */
function NavItem({ icon, label, active }: { icon: string; label: string; active?: boolean }) {
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
    <button
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-violet-600/10 text-violet-400'
          : 'text-gray-400 hover:text-white hover:bg-gray-800'
      }`}
    >
      {icons[icon]}
      {label}
    </button>
  )
}
