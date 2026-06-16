'use client'
/**
 * CO: Strona /historia — lista przetworzonych filmów YouTube
 * PO CO: Użytkownik widzi historię swoich generacji SEO z bazy PostgreSQL.
 *        NIE z localStorage, NIE z cache — zawsze z API (/v1/jobs/history).
 *        Kliknięcie "Otwórz wyniki" przenosi do /dashboard?job_id=X
 *        gdzie dashboard ładuje pełne dane z DB.
 * JAK: Fetch GET /v1/jobs/history z paginacją, wyświetla tabelę z filmami.
 */
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import Link from 'next/link'

interface HistoryJob {
  id: string
  video_url: string
  video_id: string | null
  status: string
  error: string | null
  has_vtt: boolean
  has_schema: boolean
  post_title: string | null
  created_at: string
  updated_at: string | null
}

export default function HistoriaPage() {
  const { data: session, status } = useSession()
  const router = useRouter()
  const [jobs, setJobs] = useState<HistoryJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (status === 'unauthenticated') router.push('/login')
  }, [status, router])

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
        const res = await fetch(`${apiUrl}/v1/jobs/history?limit=50`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setJobs(data)
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Błąd ładowania historii')
      } finally {
        setLoading(false)
      }
    }
    if (status === 'authenticated') fetchHistory()
  }, [status])

  const statusBadge = (s: string) => {
    const map: Record<string, { bg: string; text: string; label: string }> = {
      completed: { bg: 'bg-emerald-500/10 border-emerald-500/20', text: 'text-emerald-400', label: '✅ Gotowe' },
      done: { bg: 'bg-emerald-500/10 border-emerald-500/20', text: 'text-emerald-400', label: '✅ Gotowe' },
      fetched: { bg: 'bg-blue-500/10 border-blue-500/20', text: 'text-blue-400', label: '📥 Pobrano' },
      pending: { bg: 'bg-yellow-500/10 border-yellow-500/20', text: 'text-yellow-400', label: '⏳ W kolejce' },
      processing: { bg: 'bg-blue-500/10 border-blue-500/20', text: 'text-blue-400', label: '⏳ W trakcie' },
      failed: { bg: 'bg-red-500/10 border-red-500/20', text: 'text-red-400', label: '❌ Błąd' },
    }
    const style = map[s] || { bg: 'bg-gray-500/10 border-gray-500/20', text: 'text-gray-400', label: s }
    return (
      <span className={`px-2 py-0.5 text-xs rounded-full border ${style.bg} ${style.text}`}>
        {style.label}
      </span>
    )
  }

  const formatDate = (iso: string) => {
    try {
      const d = new Date(iso)
      return d.toLocaleString('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    } catch {
      return iso
    }
  }

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-violet-500" />
      </div>
    )
  }

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
          <Link href="/dashboard" className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-800 transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
            Dashboard
          </Link>
          <Link href="/historia" className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium bg-violet-600/10 text-violet-400">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            Historia
          </Link>
          <Link href="/ustawienia" className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-800 transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
            Ustawienia
          </Link>
        </nav>
        <div className="p-4 border-t border-gray-800">
          <p className="text-sm text-white truncate">{session?.user?.email}</p>
        </div>
      </aside>

      {/* Main */}
      <main className="ml-64 p-8">
        <div className="max-w-4xl">
          <h1 className="text-2xl font-bold text-white mb-1">Historia generacji</h1>
          <p className="text-gray-400 mb-8">Lista przetworzonych filmów YouTube z bazy danych.</p>

          {loading && (
            <div className="flex items-center gap-2 text-gray-400">
              <span className="animate-spin inline-block w-4 h-4 border-2 border-gray-500 border-t-violet-400 rounded-full" />
              Ładowanie historii...
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
              ⚠️ {error}
            </div>
          )}

          {!loading && !error && jobs.length === 0 && (
            <div className="text-center py-16 text-gray-500">
              <p className="text-4xl mb-3">🎬</p>
              <p className="text-lg font-medium">Brak historii</p>
              <p className="text-sm mt-1">Przetwórz pierwszy film na <Link href="/dashboard" className="text-violet-400 hover:underline">Dashboardzie</Link>.</p>
            </div>
          )}

          {!loading && jobs.length > 0 && (
            <div className="space-y-2">
              {jobs.map((job) => (
                <div key={job.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1">
                        {job.video_id && (
                          <img
                            src={`https://i.ytimg.com/vi/${job.video_id}/default.jpg`}
                            alt=""
                            className="w-16 h-12 rounded object-cover flex-shrink-0"
                          />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-white truncate">
                            {job.post_title || job.video_url}
                          </p>
                          {job.post_title && (
                            <p className="text-xs text-gray-600 truncate mt-0.5">
                              {job.video_url}
                            </p>
                          )}
                          <div className="flex items-center gap-2 mt-1">
                            {statusBadge(job.status)}
                            {job.has_vtt && (
                              <span className="px-2 py-0.5 text-xs rounded-full border bg-blue-500/10 border-blue-500/20 text-blue-400">
                                VTT
                              </span>
                            )}
                            <span className="text-xs text-gray-600">{formatDate(job.created_at)}</span>
                          </div>
                        </div>
                      </div>
                      {job.error && (
                        <p className="text-xs text-red-400 mt-1 ml-[76px]">{job.error}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0 ml-4">
                      {/* Otwórz wyniki — widoczny gdy schema jest dostępna */}
                      {job.has_schema && (
                        <Link
                          href={`/dashboard?job_id=${job.id}`}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-violet-600/15 text-violet-400 border border-violet-500/25 hover:bg-violet-600/25 hover:border-violet-500/40 transition-all flex items-center gap-1.5"
                        >
                          🔍 Otwórz wyniki →
                        </Link>
                      )}
                      {/* Generuj ponownie — gdy brak schema */}
                      {!job.has_schema && (job.status === 'fetched' || job.status === 'done') && (
                        <Link
                          href={`/dashboard`}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-800 text-gray-400 border border-gray-700 hover:text-white hover:border-gray-600 transition-all"
                        >
                          Generuj →
                        </Link>
                      )}
                      {job.video_id && (
                        <a
                          href={`https://www.youtube.com/watch?v=${job.video_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-gray-500 hover:text-violet-400 transition-colors"
                        >
                          YT →
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
