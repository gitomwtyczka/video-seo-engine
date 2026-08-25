import { useState } from 'react'

export function ManageSubscriptionLink({ accessToken }: { accessToken?: string }) {
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
      className="text-xs text-gray-400 hover:text-violet-300 transition-colors py-0.5 text-left disabled:opacity-50"
    >
      {loading ? '...' : '\u2699 Zarz\u0105dzaj subskrypcj\u0105'}
    </button>
  )
}
