'use client'
/**
 * CO: Panel Administratora — zarządzanie użytkownikami i planami
 * PO CO: Admin może zmieniać plany użytkowników bez SQL na VPS.
 *        Wcześniej zmiana planu (np. tobroz@gmail.com → agency) wymagała ręcznego SQL.
 *        Panel eliminuje tę potrzebę — dostęp przez UI bez wiedzy DevOps.
 * JAK: Wywołuje GET /v1/admin/users → tabela użytkowników.
 *      PATCH /v1/admin/users/{id}/plan → modal ze zmianą planu.
 *      GET /v1/admin/stats → statystyki systemu.
 *      Chroniony przez middleware.ts: requires is_admin=true lub plan=agency.
 */
import { useSession, signOut } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect, useState, useCallback } from 'react'

// ─── Types ────────────────────────────────────────────────────────────────────

interface AdminUser {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  is_admin: boolean
  is_verified: boolean
  plan_id: string
  plan_name: string
  usage_this_month: number
  created_at: string | null
}

interface AdminStats {
  total_users: number
  users_by_plan: Record<string, number>
  active_users_30d: number
  generations_today: number
}

const PLAN_COLORS: Record<string, string> = {
  free: 'bg-gray-700/50 text-gray-300 border-gray-600/50',
  starter: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  pro: 'bg-violet-500/15 text-violet-400 border-violet-500/30',
  agency: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
}

const PLAN_OPTIONS = [
  { id: 'free', label: 'Free', desc: '5 generacji/mies.' },
  { id: 'starter', label: 'Starter', desc: '50 generacji/mies.' },
  { id: 'pro', label: 'Pro', desc: '300 generacji/mies.' },
  { id: 'agency', label: 'Agency', desc: 'Unlimited' },
]

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('pl-PL', {
      year: 'numeric', month: 'short', day: 'numeric',
    })
  } catch {
    return iso
  }
}

function PlanBadge({ plan }: { plan: string }) {
  const cls = PLAN_COLORS[plan] ?? PLAN_COLORS.free
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${cls}`}>
      {plan.charAt(0).toUpperCase() + plan.slice(1)}
    </span>
  )
}

// ─── Change Plan Modal ─────────────────────────────────────────────────────────

function ChangePlanModal({
  user,
  onClose,
  onSuccess,
  accessToken,
}: {
  user: AdminUser
  onClose: () => void
  onSuccess: (userId: string, newPlan: string) => void
  accessToken: string
}) {
  const [selectedPlan, setSelectedPlan] = useState(user.plan_id)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async () => {
    if (selectedPlan === user.plan_id) { onClose(); return }
    setSaving(true)
    setError('')
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const res = await fetch(`${apiUrl}/v1/admin/users/${user.id}/plan`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ plan_id: selectedPlan }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
      onSuccess(user.id, selectedPlan)
      onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Nieznany błąd')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-lg font-semibold text-white">Zmień plan</h3>
            <p className="text-sm text-gray-400 mt-0.5 truncate max-w-xs">{user.email}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white transition-colors p-1"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="space-y-2 mb-5">
          {PLAN_OPTIONS.map((plan) => (
            <button
              key={plan.id}
              id={`plan-option-${plan.id}`}
              onClick={() => setSelectedPlan(plan.id)}
              className={`w-full flex items-center justify-between p-3.5 rounded-xl border transition-all ${
                selectedPlan === plan.id
                  ? 'border-violet-500/60 bg-violet-500/10'
                  : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                  selectedPlan === plan.id ? 'border-violet-500' : 'border-gray-600'
                }`}>
                  {selectedPlan === plan.id && (
                    <div className="w-2 h-2 rounded-full bg-violet-500" />
                  )}
                </div>
                <span className="font-medium text-white">{plan.label}</span>
              </div>
              <span className="text-xs text-gray-400">{plan.desc}</span>
            </button>
          ))}
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
            ⚠️ {error}
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 border border-gray-700 text-gray-300 rounded-xl hover:border-gray-600 hover:text-white transition-colors text-sm font-medium"
          >
            Anuluj
          </button>
          <button
            id="confirm-plan-change-btn"
            onClick={handleSave}
            disabled={saving || selectedPlan === user.plan_id}
            className="flex-1 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-xl font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-sm flex items-center justify-center gap-2"
          >
            {saving ? (
              <><span className="animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> Zapisywanie...</>
            ) : (
              'Zapisz zmianę'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Stats Card ────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-gray-400 text-xs mb-1 uppercase tracking-wide">{label}</p>
      <p className={`text-3xl font-bold ${color ?? 'text-white'}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}

// ─── Main Admin Page ───────────────────────────────────────────────────────────

export default function AdminPage() {
  /**
   * CO: AdminPage — panel zarządzania użytkownikami na /admin
   * PO CO: Operacyjny panel do zmiany planów bez SQL. Jeden klik = zmiana subskrypcji.
   * JAK: Session z NextAuth, Bearer token do /v1/admin/*. Lista + modal edycji.
   */
  const { data: session, status } = useSession()
  const router = useRouter()

  const [users, setUsers] = useState<AdminUser[]>([])
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [modalUser, setModalUser] = useState<AdminUser | null>(null)
  const [planFilter, setPlanFilter] = useState<string>('all')

  const accessToken = (session?.accessToken as string) || ''

  // Auth guard
  useEffect(() => {
    if (status === 'unauthenticated') router.push('/login')
  }, [status, router])

  const fetchData = useCallback(async () => {
    if (!accessToken) return
    setLoading(true)
    setError('')
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const headers = { Authorization: `Bearer ${accessToken}` }

      const [usersRes, statsRes] = await Promise.all([
        fetch(`${apiUrl}/v1/admin/users?limit=500`, { headers }),
        fetch(`${apiUrl}/v1/admin/stats`, { headers }),
      ])

      if (usersRes.status === 403) {
        setError('Brak uprawnień administratora. Skontaktuj się z Supervisorem.')
        setLoading(false)
        return
      }

      if (!usersRes.ok) throw new Error(`Users API: HTTP ${usersRes.status}`)
      const usersData = await usersRes.json()
      setUsers(usersData.users ?? [])

      if (statsRes.ok) {
        setStats(await statsRes.json())
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd pobierania danych')
    } finally {
      setLoading(false)
    }
  }, [accessToken])

  useEffect(() => {
    if (accessToken) fetchData()
  }, [accessToken, fetchData])

  const handlePlanSuccess = useCallback((userId: string, newPlan: string) => {
    setUsers((prev) =>
      prev.map((u) =>
        u.id === userId
          ? { ...u, plan_id: newPlan, plan_name: PLAN_OPTIONS.find((p) => p.id === newPlan)?.label ?? newPlan }
          : u
      )
    )
  }, [])

  // Filtered users
  const filteredUsers = users.filter((u) => {
    const matchSearch = search === '' ||
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      (u.full_name ?? '').toLowerCase().includes(search.toLowerCase())
    const matchPlan = planFilter === 'all' || u.plan_id === planFilter
    return matchSearch && matchPlan
  })

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
              <span className="text-xs text-gray-500">Admin Panel</span>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          <button
            onClick={() => router.push('/dashboard')}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            Dashboard
          </button>
          <button
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium bg-violet-600/10 text-violet-400 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            Użytkownicy
          </button>
        </nav>

        <div className="p-4 border-t border-gray-800">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-amber-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
              {session?.user?.email?.[0]?.toUpperCase() || 'A'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-white truncate">{session?.user?.email}</p>
              <p className="text-xs text-amber-400">Admin</p>
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
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">Panel Administratora</h1>
            <p className="text-gray-400 mt-0.5">Zarządzanie użytkownikami i planami subskrypcji</p>
          </div>
          <button
            id="admin-refresh-btn"
            onClick={fetchData}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 border border-gray-700 text-gray-300 rounded-xl hover:border-gray-600 hover:text-white transition-colors text-sm"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Odśwież
          </button>
        </div>

        {/* Stats Grid */}
        {stats && (
          <div className="grid grid-cols-4 gap-4 mb-8">
            <StatCard label="Łącznie użytkowników" value={stats.total_users} />
            <StatCard label="Aktywni (30 dni)" value={stats.active_users_30d} color="text-emerald-400" />
            <StatCard label="Generacje dzisiaj" value={stats.generations_today} color="text-violet-400" />
            <StatCard
              label="Agency / Pro"
              value={(stats.users_by_plan['agency'] ?? 0) + (stats.users_by_plan['pro'] ?? 0)}
              sub="płatni użytkownicy"
              color="text-amber-400"
            />
          </div>
        )}

        {/* Plan distribution */}
        {stats && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
            <h2 className="text-sm font-semibold text-gray-300 mb-4 uppercase tracking-wide">Rozkład planów</h2>
            <div className="flex gap-4">
              {PLAN_OPTIONS.map((plan) => {
                const count = stats.users_by_plan[plan.id] ?? 0
                const pct = stats.total_users > 0 ? Math.round((count / stats.total_users) * 100) : 0
                return (
                  <div key={plan.id} className="flex-1">
                    <div className="flex justify-between text-xs mb-1.5">
                      <span className="text-gray-400">{plan.label}</span>
                      <span className="text-gray-300 font-medium">{count}</span>
                    </div>
                    <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${pct}%`,
                          background: plan.id === 'agency' ? '#f59e0b' : plan.id === 'pro' ? '#8b5cf6' : plan.id === 'starter' ? '#3b82f6' : '#6b7280'
                        }}
                      />
                    </div>
                    <p className="text-xs text-gray-600 mt-1">{pct}%</p>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-start gap-2">
            <span className="flex-shrink-0 mt-0.5">⚠️</span>
            <div>
              <p className="font-medium">Błąd pobierania danych</p>
              <p className="text-red-300/80">{error}</p>
            </div>
          </div>
        )}

        {/* User Table */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          {/* Table toolbar */}
          <div className="flex items-center gap-4 p-4 border-b border-gray-800">
            <div className="flex-1 relative">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                id="admin-search-input"
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Szukaj po emailu lub nazwie..."
                className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>
            <div className="flex gap-2">
              {['all', 'free', 'starter', 'pro', 'agency'].map((plan) => (
                <button
                  key={plan}
                  id={`filter-${plan}`}
                  onClick={() => setPlanFilter(plan)}
                  className={`px-3 py-1.5 text-xs rounded-lg border transition-colors font-medium ${
                    planFilter === plan
                      ? 'bg-violet-600/20 border-violet-500/50 text-violet-300'
                      : 'bg-transparent border-gray-700 text-gray-400 hover:border-gray-600 hover:text-gray-300'
                  }`}
                >
                  {plan === 'all' ? 'Wszyscy' : plan.charAt(0).toUpperCase() + plan.slice(1)}
                </button>
              ))}
            </div>
            <span className="text-xs text-gray-500 whitespace-nowrap">
              {filteredUsers.length} / {users.length}
            </span>
          </div>

          {/* Table */}
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-500" />
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="text-center py-16 text-gray-500">
              <svg className="w-8 h-8 mx-auto mb-3 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <p>Brak użytkowników spełniających kryteria</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800">
                  {['Email', 'Imię i nazwisko', 'Plan', 'Generacje (mies.)', 'Rejestracja', 'Status', 'Akcje'].map((col) => (
                    <th key={col} className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((user, idx) => (
                  <tr
                    key={user.id}
                    id={`user-row-${idx}`}
                    className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center text-xs font-bold text-gray-300 flex-shrink-0">
                          {user.email[0]?.toUpperCase()}
                        </div>
                        <span className="text-sm text-white font-medium">{user.email}</span>
                        {user.is_admin && (
                          <span className="text-xs text-amber-400" title="Administrator">👑</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-300">{user.full_name || '—'}</span>
                    </td>
                    <td className="px-4 py-3">
                      <PlanBadge plan={user.plan_id} />
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-300 font-mono">{user.usage_this_month}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-gray-500">{formatDate(user.created_at)}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1.5">
                        {user.is_active ? (
                          <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
                            Aktywny
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-red-400">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-400 inline-block" />
                            Nieaktywny
                          </span>
                        )}
                        {user.is_verified && (
                          <span className="text-xs text-gray-500 ml-1">✓ zweryfikowany</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        id={`change-plan-btn-${idx}`}
                        onClick={() => setModalUser(user)}
                        className="px-3 py-1.5 text-xs font-medium bg-gray-800 border border-gray-700 text-gray-300 rounded-lg hover:border-violet-500/50 hover:text-violet-400 transition-colors"
                      >
                        Zmień plan
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>

      {/* Change Plan Modal */}
      {modalUser && (
        <ChangePlanModal
          user={modalUser}
          onClose={() => setModalUser(null)}
          onSuccess={handlePlanSuccess}
          accessToken={accessToken}
        />
      )}
    </div>
  )
}
