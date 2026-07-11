'use client'
/**
 * CO: Strona /ustawienia — ustawienia konta, portale WordPress, plan subskrypcji.
 * PO CO: Daje użytkownikowi dostęp do zarządzania kontem, listą portali WP
 *        i informacją o aktualnym planie — bez wychodzenia z aplikacji.
 * JAK: 3 sekcje — Konto (email + plan + ManageSubscription),
 *      Portale WP (usePortals + AddPortalModal inline + usuwanie),
 *      Plan (link do /cennik lub info o planie płatnym).
 *
 * Limity portali per plan:
 *   free: 0 | starter: 3 | pro: 10 | agency: 999
 */
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect, useState, useRef, useCallback } from 'react'
import Link from 'next/link'
import { usePortals, type Portal, type PortalCreatePayload } from '../dashboard/use-portals'
import { useProfiles, type Profile } from '../dashboard/use-profiles'

// ─── Constants ───────────────────────────────────────────────────────────────

const PLAN_PORTAL_LIMITS: Record<string, number> = {
  free: 0,
  starter: 3,
  pro: 10,
  agency: 999,
}

const PLAN_LABELS: Record<string, string> = {
  free: 'Free',
  starter: 'Starter',
  pro: 'Pro',
  agency: 'Agency',
}

// ─── Types ───────────────────────────────────────────────────────────────────

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
  subscription?: {
    status?: string
    current_period_end?: string
  } | null
}

interface YtChannel {
  id: string
  channel_id: string
  channel_title: string
  channel_thumbnail?: string
}

// ─── ManageSubscriptionLink ──────────────────────────────────────────────────

/**
 * CO: Przycisk otwierający Stripe Customer Portal.
 * PO CO: Płatni użytkownicy mogą zarządzać subskrypcją bez kontaktu z supportem.
 * JAK: GET /v1/payments/portal-session z Bearer token → redirect do Stripe Portal URL.
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
      // silent
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleManage}
      disabled={loading}
      className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 border border-gray-700 hover:border-violet-500/50 text-gray-300 hover:text-white rounded-lg text-sm font-medium transition-all disabled:opacity-50"
    >
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
      {loading ? 'Przekierowuję...' : 'Zarządzaj subskrypcją'}
    </button>
  )
}

// ─── AddPortalModal ──────────────────────────────────────────────────────────

/**
 * CO: Modal dodawania nowego portalu WordPress.
 * PO CO: Użytkownik może dodać portal WP bez opuszczania strony ustawień.
 * JAK: Formularz z nazwą, URL, credentials WP i profilem treści.
 *      usePortals().createPortal → odświeżenie listy portali.
 */
function AddPortalModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void
  onSuccess: () => void
}) {
  const { createPortal } = usePortals()
  const { profiles, loading: profilesLoading } = useProfiles()

  const [name, setName] = useState('')
  const [url, setUrl] = useState('https://')
  const [wpUser, setWpUser] = useState('')
  const [wpPassword, setWpPassword] = useState('')
  const [profileId, setProfileId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (profiles.length > 0 && !profileId) {
      setProfileId(profiles[0].id)
    }
  }, [profiles, profileId])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const handleBackdrop = (e: React.MouseEvent) => {
    if (modalRef.current && !modalRef.current.contains(e.target as Node)) onClose()
  }

  const handleSave = async () => {
    if (!name || !url || !wpUser || !wpPassword) {
      setError('Uzupełnij wszystkie pola.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const payload: PortalCreatePayload = {
        name,
        url,
        wp_username: wpUser,
        wp_app_password: wpPassword,
        profile_id: profileId === 'none' || !profileId ? null : profileId,
      }
      const created = await createPortal(payload)
      if (created) {
        onSuccess()
        onClose()
      } else {
        setError('Nie udało się utworzyć portalu.')
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Błąd podczas zapisu')
    } finally {
      setSaving(false)
    }
  }

  const inputCls = 'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={handleBackdrop}
    >
      <div
        ref={modalRef}
        className="w-full max-w-md bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden"
        style={{ animation: 'fadeInUp 0.25s ease-out', maxHeight: '90vh', overflowY: 'auto' }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gradient-to-r from-violet-950/50 to-fuchsia-950/30">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center text-sm">🌐</div>
            <h3 className="font-semibold text-white">Dodaj nowy portal</h3>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-1">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Nazwa portalu</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="np. BiznesCiti.com" className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">URL WordPress</label>
            <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://twojportal.pl" className={inputCls} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Użytkownik WP</label>
              <input type="text" value={wpUser} onChange={(e) => setWpUser(e.target.value)} placeholder="admin" className={inputCls} />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">App Password</label>
              <input type="password" value={wpPassword} onChange={(e) => setWpPassword(e.target.value)} placeholder="xxxx xxxx xxxx xxxx" className={inputCls} />
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Profil treści</label>
            {profilesLoading ? (
              <div className="text-gray-500 text-xs py-2">Ładowanie profili...</div>
            ) : (
              <select
                value={profileId}
                onChange={(e) => setProfileId(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white focus:border-violet-500 focus:outline-none cursor-pointer"
              >
                {profiles.map((p: Profile) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name}{p.site_brand ? ` (${p.site_brand})` : ''}
                  </option>
                ))}
                <option value="none">(brak profilu)</option>
              </select>
            )}
          </div>

          {error && <p className="text-red-400 text-xs">{error}</p>}

          <div className="flex gap-3 pt-2">
            <button
              onClick={onClose}
              disabled={saving}
              className="flex-1 py-2.5 bg-gray-800 text-white rounded-lg font-medium hover:bg-gray-700 transition-colors"
            >
              Anuluj
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex-1 py-2.5 bg-violet-600 text-white rounded-lg font-medium hover:bg-violet-500 transition-colors disabled:opacity-50"
            >
              {saving ? 'Zapisywanie...' : 'Zapisz portal'}
            </button>
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}

// ─── Sidebar ─────────────────────────────────────────────────────────────────

function SidebarLink({
  href,
  icon,
  label,
  active,
}: {
  href: string
  icon: React.ReactNode
  label: string
  active?: boolean
}) {
  return (
    <Link
      href={href}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-violet-600/10 text-violet-400'
          : 'text-gray-400 hover:text-white hover:bg-gray-800'
      }`}
    >
      {icon}
      {label}
    </Link>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function UstawieniaPage() {
  /**
   * CO: Strona /ustawienia — hub zarządzania kontem.
   * PO CO: Użytkownik widzi swój email, plan, zarządza portalami WP i subskrypcją.
   * JAK: useSession → auth guard. Fetch /v1/users/me → dane planu.
   *      usePortals() → lista portali z możliwością dodawania i usuwania.
   */
  const { data: session, status } = useSession()
  const router = useRouter()

  const [userProfile, setUserProfile] = useState<UserProfile | null>(null)
  const [profileLoading, setProfileLoading] = useState(true)
  const [showAddPortal, setShowAddPortal] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState('')

  const [ytChannels, setYtChannels] = useState<YtChannel[]>([])
  const [ytLoading, setYtLoading] = useState(false)
  const [ytConnecting, setYtConnecting] = useState(false)

  const { portals, loading: portalsLoading, error: portalsError, fetchPortals, deletePortal } = usePortals()

  // Auth guard
  useEffect(() => {
    if (status === 'unauthenticated') router.push('/login')
  }, [status, router])

  // Fetch user plan
  const fetchUserProfile = useCallback(async () => {
    if (!session?.accessToken) return
    setProfileLoading(true)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const res = await fetch(`${apiUrl}/v1/users/me`, {
        headers: { Authorization: `Bearer ${session.accessToken as string}` },
      })
      if (res.ok) setUserProfile(await res.json())
    } catch {
      // silent
    } finally {
      setProfileLoading(false)
    }
  }, [session?.accessToken])

  useEffect(() => { fetchUserProfile() }, [fetchUserProfile])

  const handleDeletePortal = async (portalId: string) => {
    if (!confirm('Czy na pewno chcesz usunąć ten portal?')) return
    setDeletingId(portalId)
    setDeleteError('')
    const ok = await deletePortal(portalId)
    if (!ok) setDeleteError('Nie udało się usunąć portalu.')
    setDeletingId(null)
  }

  useEffect(() => {
    if (!session?.accessToken) return
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
    setYtLoading(true)
    fetch(`${apiUrl}/v1/youtube/channels`, {
      headers: { Authorization: `Bearer ${session.accessToken as string}` },
    })
      .then((r) => r.ok ? r.json() : [])
      .then((data) => setYtChannels(Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setYtLoading(false))
  }, [session?.accessToken])

  const handleConnectYoutube = async () => {
    if (!session?.accessToken) return
    setYtConnecting(true)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const res = await fetch(`${apiUrl}/v1/youtube/oauth/login`, {
        headers: { Authorization: `Bearer ${session.accessToken as string}` },
      })
      if (res.ok) {
        const { authorization_url } = await res.json()
        window.location.href = authorization_url
      }
    } catch {}
    finally { setYtConnecting(false) }
  }

  const handleDisconnectYoutube = async (channelId: string) => {
    if (!session?.accessToken) return
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
    await fetch(`${apiUrl}/v1/youtube/channels/${channelId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${session.accessToken as string}` },
    })
    setYtChannels((prev) => prev.filter((c) => c.id !== channelId))
  }

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-violet-500" />
      </div>
    )
  }

  const planId = userProfile?.plan?.id ?? 'free'
  const planLabel = PLAN_LABELS[planId] ?? userProfile?.plan?.display_name ?? 'Free'
  const isPaid = planId !== 'free'
  const portalLimit = PLAN_PORTAL_LIMITS[planId] ?? 0
  const portalCount = portals.length
  const canAddPortal = portalLimit === 0 ? false : portalCount < portalLimit
  const accessToken = session?.accessToken as string | undefined

  // Renewal date display
  const renewalDate = userProfile?.subscription?.current_period_end
    ? new Date(userProfile.subscription.current_period_end).toLocaleDateString('pl-PL', {
        day: 'numeric', month: 'long', year: 'numeric',
      })
    : null

  // Icons
  const iconDashboard = (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
    </svg>
  )
  const iconHistory = (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
  const iconSettings = (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  )

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
          <SidebarLink href="/dashboard" icon={iconDashboard} label="Dashboard" />
          <SidebarLink href="/historia" icon={iconHistory} label="Historia" />
          <SidebarLink href="/ustawienia" icon={iconSettings} label="Ustawienia" active />
        </nav>

        <div className="p-4 border-t border-gray-800 space-y-1">
          <p className="text-sm text-white truncate">{session?.user?.email}</p>
          <span className="inline-block px-2 py-0.5 text-xs bg-violet-500/15 text-violet-400 rounded-full border border-violet-500/20">
            {planLabel}
          </span>
        </div>
      </aside>

      {/* Main */}
      <main className="ml-64 p-8">
        <div className="max-w-2xl">
          <h1 className="text-2xl font-bold text-white mb-1">Ustawienia</h1>
          <p className="text-gray-400 mb-8">Zarządzaj kontem, portalami i subskrypcją.</p>

          {/* ── Sekcja 1: Konto ───────────────────────────────────────────── */}
          <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-6">
            <h2 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-violet-500/20 flex items-center justify-center text-violet-400 text-xs">👤</span>
              Konto
            </h2>

            <div className="space-y-4">
              {/* Email */}
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-gray-500 mb-0.5">Email</p>
                  <p className="text-sm font-medium text-white">{session?.user?.email ?? '—'}</p>
                </div>
              </div>

              {/* Plan */}
              <div className="flex items-center justify-between border-t border-gray-800 pt-4">
                <div>
                  <p className="text-xs text-gray-500 mb-0.5">Aktualny plan</p>
                  {profileLoading ? (
                    <div className="h-5 w-16 bg-gray-800 rounded animate-pulse" />
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-white">{planLabel}</span>
                      {isPaid && (
                        <span className="px-2 py-0.5 text-xs bg-emerald-500/15 text-emerald-400 rounded-full border border-emerald-500/20">
                          Aktywny
                        </span>
                      )}
                      {!isPaid && (
                        <span className="px-2 py-0.5 text-xs bg-gray-700/50 text-gray-400 rounded-full">
                          Bezpłatny
                        </span>
                      )}
                    </div>
                  )}
                </div>
                {isPaid && accessToken && (
                  <ManageSubscriptionLink accessToken={accessToken} />
                )}
              </div>

              {/* Usage */}
              {userProfile && (
                <div className="border-t border-gray-800 pt-4">
                  <p className="text-xs text-gray-500 mb-2">
                    Wykorzystanie w tym miesiącu: <span className="text-gray-300">{userProfile.usage.used_this_month} / {userProfile.usage.quota}</span> generacji
                  </p>
                  <div className="w-full bg-gray-800 rounded-full h-1.5">
                    <div
                      className="bg-gradient-to-r from-violet-500 to-fuchsia-500 h-1.5 rounded-full transition-all"
                      style={{ width: `${Math.min(userProfile.usage.percent, 100)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* ── Sekcja 2: Portale WordPress ──────────────────────────────── */}
          <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <span className="w-6 h-6 rounded-lg bg-violet-500/20 flex items-center justify-center text-violet-400 text-xs">🌐</span>
                Portale WordPress
              </h2>
              {!portalsLoading && (
                <span className="text-xs text-gray-500">
                  {portalLimit === 999
                    ? `${portalCount} portali (bez limitu)`
                    : portalLimit === 0
                    ? '0 portali (plan Free)'
                    : `${portalCount} / ${portalLimit} portali`}
                </span>
              )}
            </div>

            {/* Free plan lock */}
            {planId === 'free' && !profileLoading && (
              <div className="flex items-start gap-3 p-4 bg-amber-500/5 border border-amber-500/20 rounded-xl mb-4">
                <span className="text-amber-400 mt-0.5">🔒</span>
                <div>
                  <p className="text-sm font-medium text-amber-300">Funkcja dostępna od planu Starter</p>
                  <p className="text-xs text-gray-400 mt-1">Portale WordPress umożliwiają automatyczną publikację SEO.</p>
                  <Link
                    href="/cennik"
                    className="inline-block mt-2 text-xs text-violet-400 hover:text-violet-300 underline underline-offset-2"
                  >
                    Upgrade do Starter →
                  </Link>
                </div>
              </div>
            )}

            {/* Portal list */}
            {portalsLoading ? (
              <div className="space-y-3">
                {[1, 2].map((i) => (
                  <div key={i} className="h-14 bg-gray-800/50 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : portalsError ? (
              <p className="text-red-400 text-sm">{portalsError}</p>
            ) : portals.length === 0 && planId !== 'free' ? (
              <div className="text-center py-6 text-gray-500">
                <p className="text-sm">Brak portali. Dodaj pierwszy portal WordPress.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {portals.map((portal: Portal) => (
                  <div
                    key={portal.id}
                    className="flex items-center justify-between p-4 bg-gray-800/40 border border-gray-700/50 rounded-xl hover:border-gray-700 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-sm font-medium text-white truncate">{portal.name}</span>
                        {portal.is_default && (
                          <span className="flex-shrink-0 px-1.5 py-0.5 text-xs bg-violet-500/20 text-violet-400 rounded-full border border-violet-500/20">
                            domyślny
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 truncate">{portal.url}</p>
                    </div>
                    <button
                      onClick={() => handleDeletePortal(portal.id)}
                      disabled={deletingId === portal.id}
                      className="ml-3 flex-shrink-0 p-2 text-gray-600 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all disabled:opacity-30"
                      title="Usuń portal"
                    >
                      {deletingId === portal.id ? (
                        <span className="animate-spin inline-block w-4 h-4 border-2 border-gray-500/30 border-t-gray-400 rounded-full" />
                      ) : (
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      )}
                    </button>
                  </div>
                ))}
              </div>
            )}

            {deleteError && <p className="text-red-400 text-xs mt-3">{deleteError}</p>}

            {/* Add portal button */}
            {planId !== 'free' && !profileLoading && (
              <div className="mt-4">
                {canAddPortal ? (
                  <button
                    onClick={() => setShowAddPortal(true)}
                    className="flex items-center gap-2 px-4 py-2.5 bg-violet-600/10 border border-violet-500/20 hover:border-violet-500/50 hover:bg-violet-600/20 text-violet-400 rounded-xl text-sm font-medium transition-all"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Dodaj portal
                  </button>
                ) : (
                  <p className="text-xs text-gray-500">
                    Osiągnięto limit portali dla planu {planLabel} ({portalLimit}).
                    {planId === 'starter' && (
                      <> <Link href="/cennik" className="text-violet-400 hover:text-violet-300 underline underline-offset-2">Upgrade do Pro →</Link></>
                    )}
                  </p>
                )}
              </div>
            )}
          </section>

          {/* ── YouTube Channels ─────────────────────────────────────────── */}
          <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-red-600/20 flex items-center justify-center text-sm">
                  📺
                </div>
                <div>
                  <h2 className="font-semibold text-white">Kanały YouTube</h2>
                  <p className="text-xs text-gray-500">Podłączone kanały do wysyłki SEO</p>
                </div>
              </div>
              <button
                onClick={handleConnectYoutube}
                disabled={ytConnecting}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
              >
                {ytConnecting ? '...' : '+ Podłącz kanał'}
              </button>
            </div>

            {ytLoading && <p className="text-sm text-gray-500">Ładowanie...</p>}

            {!ytLoading && ytChannels.length === 0 && (
              <p className="text-sm text-gray-600">Brak podłączonych kanałów YouTube.</p>
            )}

            {!ytLoading && ytChannels.map((ch) => (
              <div key={ch.id} className="flex items-center justify-between py-3 border-b border-gray-800 last:border-0">
                <div className="flex items-center gap-3">
                  {ch.channel_thumbnail && (
                    <img src={ch.channel_thumbnail} alt="" className="w-8 h-8 rounded-full" />
                  )}
                  <div>
                    <p className="text-sm font-medium text-white">{ch.channel_title}</p>
                    <p className="text-xs text-gray-500">{ch.channel_id}</p>
                  </div>
                </div>
                <button
                  onClick={() => handleDisconnectYoutube(ch.id)}
                  className="text-gray-500 hover:text-red-400 transition-colors p-1"
                  title="Odłącz kanał"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            ))}
          </section>

          {/* ── Sekcja 3: Plan ───────────────────────────────────────────── */}
          <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
            <h2 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-violet-500/20 flex items-center justify-center text-violet-400 text-xs">💳</span>
              Plan subskrypcji
            </h2>

            {profileLoading ? (
              <div className="h-10 bg-gray-800/50 rounded-xl animate-pulse" />
            ) : !isPaid ? (
              <div className="flex items-center justify-between p-4 bg-gray-800/40 border border-gray-700/50 rounded-xl">
                <div>
                  <p className="text-sm font-medium text-white mb-1">Plan Free</p>
                  <p className="text-xs text-gray-400">5 generacji / miesiąc · bez portali WordPress</p>
                </div>
                <Link
                  href="/cennik"
                  className="flex-shrink-0 px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-xl text-sm font-semibold text-white hover:opacity-90 transition-all"
                >
                  Upgrade ↗
                </Link>
              </div>
            ) : (
              <div className="p-4 bg-emerald-500/5 border border-emerald-500/15 rounded-xl">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-white">Plan {planLabel}</span>
                    <span className="px-2 py-0.5 text-xs bg-emerald-500/20 text-emerald-400 rounded-full border border-emerald-500/20">Aktywny</span>
                  </div>
                  {accessToken && <ManageSubscriptionLink accessToken={accessToken} />}
                </div>
                {renewalDate && (
                  <p className="text-xs text-gray-400">Odnowienie: <span className="text-gray-300">{renewalDate}</span></p>
                )}
                <p className="text-xs text-gray-500 mt-1">
                  {userProfile?.usage?.quota ?? '—'} generacji / miesiąc ·
                  {` ${portalLimit === 999 ? 'Bez limitu' : portalLimit} portali WordPress`}
                </p>
              </div>
            )}
          </section>
        </div>
      </main>

      {/* AddPortalModal */}
      {showAddPortal && (
        <AddPortalModal
          onClose={() => setShowAddPortal(false)}
          onSuccess={() => {
            setShowAddPortal(false)
            fetchPortals()
          }}
        />
      )}
    </div>
  )
}
