'use client'
/**
 * CO: EmailVerificationBanner — baner informujący o niezweryfikowanym adresie email.
 *
 * PO CO: RODO wymaga potwierdzenia adresu email.
 *        Baner informuje użytkownika i umożliwia ponowne wysłanie emaila weryfikacyjnego.
 *        NIE blokuje dostępu — soft enforcement.
 *
 * JAK: Pobiera accessToken z sesji, wywołuje POST /v1/auth/resend-verification.
 *      Ukrywa się jeśli is_verified == true lub użytkownik kliknie X.
 *
 * Użycie: <EmailVerificationBanner isVerified={userProfile?.is_verified} accessToken={session?.accessToken} />
 */
import { useState } from 'react'

interface EmailVerificationBannerProps {
  /** Whether the current user's email is verified. undefined = unknown (loading). */
  isVerified?: boolean
  /** JWT access token for authenticated API calls. */
  accessToken?: string
}

export default function EmailVerificationBanner({
  isVerified,
  accessToken,
}: EmailVerificationBannerProps) {
  const [dismissed, setDismissed] = useState(false)
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  // Don't render if: verified, unknown state (loading), or dismissed
  if (isVerified !== false || dismissed) return null

  const handleResend = async () => {
    if (sending || sent) return
    setSending(true)
    setError('')
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const res = await fetch(`${apiUrl}/v1/auth/resend-verification`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
      })
      if (res.ok) {
        setSent(true)
      } else {
        const data = await res.json().catch(() => ({}))
        setError(data?.detail ?? 'Błąd wysyłania. Spróbuj ponownie.')
      }
    } catch {
      setError('Błąd połączenia. Spróbuj ponownie.')
    } finally {
      setSending(false)
    }
  }

  return (
    <div
      id="email-verification-banner"
      className="relative flex items-center gap-3 px-4 py-3 mb-4 rounded-xl border border-amber-500/30 bg-amber-500/8 backdrop-blur-sm"
      style={{ background: 'rgba(245, 158, 11, 0.06)', borderColor: 'rgba(245, 158, 11, 0.3)' }}
    >
      {/* Icon */}
      <span className="text-amber-400 text-lg flex-shrink-0" aria-hidden>✉️</span>

      {/* Text */}
      <div className="flex-1 min-w-0">
        {sent ? (
          <p className="text-sm text-emerald-400 font-medium">
            ✓ Email weryfikacyjny wysłany! Sprawdź skrzynkę odbiorczą.
          </p>
        ) : (
          <p className="text-sm text-amber-300">
            <span className="font-medium">Zweryfikuj swój email</span>
            {' '}— potwierdź adres email, aby spełnić wymogi RODO.
            {' '}
            <button
              id="resend-verification-btn"
              onClick={handleResend}
              disabled={sending}
              className="underline underline-offset-2 text-amber-200 hover:text-white transition-colors font-medium disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {sending ? 'Wysyłanie...' : 'Wyślij ponownie'}
            </button>
          </p>
        )}
        {error && (
          <p className="text-xs text-red-400 mt-0.5">{error}</p>
        )}
      </div>

      {/* Dismiss button */}
      <button
        id="dismiss-verification-banner-btn"
        onClick={() => setDismissed(true)}
        aria-label="Zamknij baner weryfikacji"
        className="flex-shrink-0 text-gray-500 hover:text-gray-300 transition-colors p-1"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
