'use client'
import { useSession, signOut } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

// GenerateResponse shape from /v1/generate
interface GenerateResult {
  status: string           // "ok" | "error"
  video_id: string
  processing_time_s?: number
  schema_data?: Record<string, unknown> | null
  error?: string | null
}

// Derived display shape extracted from schema_data
interface DisplayResult {
  videoId: string
  schema: Record<string, unknown> | null
  chapters: Array<{ name?: string; startOffset?: number }>
  faq: Array<{ question?: string; answer?: string }>
  processingTime?: number
}

/** Extract chapters list from schema_data (Clip array inside @graph or top-level). */
function extractChapters(schema: Record<string, unknown> | null | undefined): Array<{ name?: string; startOffset?: number }> {
  if (!schema) return []
  // Try @graph array
  const graph = schema['@graph']
  if (Array.isArray(graph)) {
    const clips = graph.filter((n: unknown) => (n as Record<string, unknown>)?.['@type'] === 'Clip')
    if (clips.length > 0) {
      return clips.map((c: unknown) => ({
        name: (c as Record<string, unknown>).name as string | undefined,
        startOffset: (c as Record<string, unknown>).startOffset as number | undefined,
      }))
    }
  }
  // Try direct clips key
  const clips = schema['clips']
  if (Array.isArray(clips)) return clips as Array<{ name?: string; startOffset?: number }>
  return []
}

/** Extract FAQ list from schema_data. */
function extractFaq(schema: Record<string, unknown> | null | undefined): Array<{ question?: string; answer?: string }> {
  if (!schema) return []
  const graph = schema['@graph']
  if (Array.isArray(graph)) {
    const faqPage = graph.find((n: unknown) => (n as Record<string, unknown>)?.['@type'] === 'FAQPage')
    if (faqPage) {
      const items = (faqPage as Record<string, unknown>)['mainEntity']
      if (Array.isArray(items)) {
        return items.map((q: unknown) => {
          const item = q as Record<string, unknown>
          const answer = item['acceptedAnswer'] as Record<string, unknown> | undefined
          return {
            question: item['name'] as string | undefined,
            answer: answer?.['text'] as string | undefined,
          }
        })
      }
    }
  }
  // Try direct faq key
  const faq = schema['faq']
  if (Array.isArray(faq)) return faq as Array<{ question?: string; answer?: string }>
  return []
}

export default function DashboardPage() {
  const { data: session, status } = useSession()
  const router = useRouter()
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DisplayResult | null>(null)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'schema' | 'chapters' | 'faq'>('schema')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (status === 'unauthenticated') router.push('/login')
  }, [status, router])

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-violet-500"></div>
      </div>
    )
  }

  const handleProcess = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api'
      // Use /v1/generate (no WP credentials required — generate-only endpoint)
      const res = await fetch(`${apiUrl}/v1/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(session?.accessToken ? { Authorization: `Bearer ${session.accessToken}` } : {}),
        },
        body: JSON.stringify({
          video_url: url.trim(),    // API field is video_url (not url)
          llm_provider: 'gemini',   // use gemini — GEMINI_API_KEY is set on VPS
          lang: 'pl',
        }),
      })

      // Guard: res.json() may throw SyntaxError when server returns HTML (e.g. 502 nginx)
      let data: GenerateResult | null = null
      try {
        data = await res.json() as GenerateResult
      } catch {
        throw new Error(`Serwer zwrócił nieprawidłową odpowiedź (HTTP ${res.status})`)
      }

      if (!res.ok) {
        const errData = data as unknown as { detail?: string | Array<{ msg: string }> }
        const detail = errData?.detail
        if (Array.isArray(detail)) throw new Error(detail.map(d => d.msg).join(', '))
        throw new Error(typeof detail === 'string' ? detail : `Błąd serwera: HTTP ${res.status}`)
      }

      if (!data) throw new Error('Pusta odpowiedź serwera')

      // API may return status=error even on HTTP 200 (RuntimeError path)
      if (data.error) throw new Error(data.error)

      const schema = data.schema_data ?? null
      setResult({
        videoId: data.video_id,
        schema,
        chapters: extractChapters(schema),
        faq: extractFaq(schema),
        processingTime: data.processing_time_s,
      })
      setActiveTab('schema')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Nieznany błąd połączenia z serwerem'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard API may be unavailable — silently ignore
    }
  }

  const chapters = result?.chapters ?? []
  const faq = result?.faq ?? []

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Sidebar */}
      <div className="fixed left-0 top-0 h-full w-64 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-6 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-violet-600 to-fuchsia-600 flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.069A1 1 0 0121 8.87v6.26a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </div>
            <span className="font-bold text-white">VSE</span>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          <NavItem icon="grid" label="Dashboard" active />
          <NavItem icon="clock" label="Historia" />
          <NavItem icon="settings" label="Ustawienia" />
        </nav>

        <div className="p-4 border-t border-gray-800">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-violet-600 flex items-center justify-center text-xs font-bold">
              {session?.user?.email?.[0]?.toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-white truncate">{session?.user?.email}</p>
              <p className="text-xs text-gray-500">Plan Free</p>
            </div>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: '/login' })}
            className="w-full text-left text-sm text-gray-400 hover:text-white transition-colors py-1"
          >
            → Wyloguj się
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="ml-64 p-8">
        <div className="max-w-4xl">
          <h1 className="text-2xl font-bold text-white mb-2">Video SEO Engine</h1>
          <p className="text-gray-400 mb-8">Wklej URL YouTube — AI wygeneruje pełny schemat SEO (VideoObject + Clip + FAQPage).</p>

          {/* URL Form */}
          <form onSubmit={handleProcess} className="mb-8">
            <div className="flex gap-3">
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
              />
              <button
                type="submit"
                disabled={loading || !url.trim()}
                className="px-6 py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-xl font-semibold text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
              >
                {loading ? (
                  <><span className="animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full"></span> Generuję...</>
                ) : (
                  <>✦ Generuj SEO</>
                )}
              </button>
            </div>
            {error && (
              <div className="mt-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm flex items-start gap-2">
                <span className="mt-0.5 flex-shrink-0">⚠️</span>
                <div>
                  <p className="font-medium mb-0.5">Wystąpił błąd</p>
                  <p className="text-red-300/80">{error}</p>
                </div>
              </div>
            )}
          </form>

          {/* Placeholder info cards */}
          {!result && !loading && (
            <div className="grid grid-cols-3 gap-4 mb-8">
              {[
                { label: 'Filmy przetworzone', value: '0', sub: 'z 5 darmowych' },
                { label: 'Benchmark', value: '8/10', sub: 'vs 2-3/10 konkurencja' },
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

          {/* Results */}
          {result && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
              {/* Result header */}
              <div className="p-5 border-b border-gray-800 flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Wynik dla: <span className="font-mono text-xs text-gray-500">{result.videoId}</span></p>
                  <p className="font-medium text-white truncate max-w-sm">{url}</p>
                </div>
                <div className="flex items-center gap-3">
                  {result.processingTime && (
                    <span className="text-xs text-gray-500">{result.processingTime}s</span>
                  )}
                  <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-sm rounded-full border border-emerald-500/20">
                    ✓ Sukces
                  </span>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex border-b border-gray-800">
                {(['schema', 'chapters', 'faq'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-5 py-3 text-sm font-medium transition-colors ${
                      activeTab === tab
                        ? 'text-violet-400 border-b-2 border-violet-500'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {tab === 'schema' ? 'JSON-LD Schema' : tab === 'chapters' ? `Rozdziały (${chapters.length})` : `FAQ (${faq.length})`}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              <div className="p-5">
                {activeTab === 'schema' && (
                  <div className="relative">
                    <button
                      onClick={() => handleCopy(JSON.stringify(result.schema ?? {}, null, 2))}
                      className="absolute top-2 right-2 px-3 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors z-10"
                    >
                      {copied ? '✓ Skopiowano' : 'Kopiuj'}
                    </button>
                    <pre className="text-xs text-green-400 bg-gray-950 rounded-xl p-4 overflow-auto max-h-96 font-mono pr-24">
                      {JSON.stringify(result.schema ?? {}, null, 2)}
                    </pre>
                  </div>
                )}
                {activeTab === 'chapters' && (
                  <div className="space-y-2">
                    {chapters.map((ch, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-gray-950 rounded-lg">
                        <span className="text-violet-400 font-mono text-sm min-w-[3rem]">{ch.startOffset ?? '?'}s</span>
                        <span className="text-white text-sm">{ch.name ?? '(bez tytułu)'}</span>
                      </div>
                    ))}
                    {chapters.length === 0 && (
                      <p className="text-gray-500 text-sm">Brak rozdziałów w wygenerowanej schemie.</p>
                    )}
                  </div>
                )}
                {activeTab === 'faq' && (
                  <div className="space-y-3">
                    {faq.map((item, i) => (
                      <div key={i} className="p-4 bg-gray-950 rounded-lg">
                        <p className="text-white font-medium mb-1">{item.question ?? '(brak pytania)'}</p>
                        <p className="text-gray-400 text-sm">{item.answer ?? '(brak odpowiedzi)'}</p>
                      </div>
                    ))}
                    {faq.length === 0 && (
                      <p className="text-gray-500 text-sm">Brak FAQ w wygenerowanej schemie.</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function NavItem({ icon, label, active }: { icon: string; label: string; active?: boolean }) {
  const icons: Record<string, JSX.Element> = {
    grid: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>,
    clock: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
    settings: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>,
  }
  return (
    <button className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
      active ? 'bg-violet-600/10 text-violet-400' : 'text-gray-400 hover:text-white hover:bg-gray-800'
    }`}>
      {icons[icon]}
      {label}
    </button>
  )
}
