'use client'
import { useState } from 'react'
import { signIn } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Video, Mail, Lock, User, Chrome } from 'lucide-react'

// CO: API_URL fallback musi byc '' (pusty string), NIE '/api'
// PO CO: nginx routuje /api/ -> Next.js (nie FastAPI). FastAPI zyje pod /v1/*.
//        Gdy NEXT_PUBLIC_API_URL nie jest ustawiony, fetch idzie na /v1/auth/register
//        (relatywnie do domeny) co nginx poprawnie proxuje do FastAPI :8085.
const API_URL = process.env.NEXT_PUBLIC_API_URL || ''

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [tosAccepted, setTosAccepted] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!tosAccepted) {
      setError('Musisz zaakceptować Regulamin i Politykę Prywatności, aby założyć konto.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_URL}/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, full_name: name })
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Błąd rejestracji')
      } else {
        setSuccess(true)
        setTimeout(() => router.push('/login'), 2000)
      }
    } catch {
      setError('Błąd połączenia z serwerem')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="glass rounded-2xl p-12 text-center max-w-md">
          <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">✅</span>
          </div>
          <h2 className="text-xl font-bold mb-2">Konto utworzone!</h2>
          <p className="text-dark-400">Sprawdź skrzynkę email i potwierdź adres. Przekierowanie...</p>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-hero-glow" />

      <div className="relative w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center">
              <Video className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-xl">VSE</span>
          </Link>
          <h1 className="text-2xl font-bold mt-6 mb-2">Załóż konto</h1>
          <p className="text-dark-400">Masz już konto? <Link href="/login" className="text-brand-400 hover:text-brand-300">Zaloguj się</Link></p>
        </div>

        <div className="glass rounded-2xl p-8">
          {/* Google OAuth */}
          <button
            type="button"
            onClick={() => signIn('google', { callbackUrl: '/dashboard' })}
            className="w-full flex items-center justify-center gap-3 py-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white font-medium transition-smooth mb-6"
          >
            <Chrome className="w-5 h-5" />
            Kontynuuj z Google
          </button>

          <div className="flex items-center gap-4 mb-6">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-dark-400 text-sm">lub</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-1.5">Imię i nazwisko (opcjonalne)</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                <input
                  id="full-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 rounded-xl bg-dark-900 border border-white/10 text-white placeholder-dark-400 focus:outline-none focus:border-brand-500 transition-smooth"
                  placeholder="Jan Kowalski"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-dark-300 mb-1.5">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 rounded-xl bg-dark-900 border border-white/10 text-white placeholder-dark-400 focus:outline-none focus:border-brand-500 transition-smooth"
                  placeholder="twoj@email.pl"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-dark-300 mb-1.5">Hasło (min. 8 znaków)</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 rounded-xl bg-dark-900 border border-white/10 text-white placeholder-dark-400 focus:outline-none focus:border-brand-500 transition-smooth"
                  placeholder="Minimum 8 znaków"
                  required
                  minLength={8}
                />
              </div>
            </div>

            {/* TOS Checkbox */}
            <div className="flex items-start gap-3 pt-1">
              <input
                id="tos-checkbox"
                type="checkbox"
                checked={tosAccepted}
                onChange={(e) => setTosAccepted(e.target.checked)}
                className="mt-0.5 w-4 h-4 rounded border-white/20 bg-dark-900 accent-brand-500 cursor-pointer flex-shrink-0"
              />
              <label htmlFor="tos-checkbox" className="text-dark-400 text-xs leading-relaxed cursor-pointer">
                Akceptuję{' '}
                <Link href="/regulamin" className="text-brand-400 hover:text-brand-300 underline" target="_blank">
                  Regulamin
                </Link>
                {' '}i{' '}
                <Link href="/polityka-prywatnosci" className="text-brand-400 hover:text-brand-300 underline" target="_blank">
                  Politykę Prywatności
                </Link>{' '}
                VSE. Wyrażam zgodę na przetwarzanie moich danych osobowych w celu realizacji usługi.
              </label>
            </div>

            <button
              id="btn-register"
              type="submit"
              disabled={loading || !tosAccepted}
              className="w-full py-3 rounded-xl bg-brand-500 hover:bg-brand-400 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold transition-smooth glow-sm mt-2"
            >
              {loading ? 'Tworzenie konta...' : 'Załóż konto za darmo'}
            </button>
          </form>
        </div>
      </div>
    </main>
  )
}
