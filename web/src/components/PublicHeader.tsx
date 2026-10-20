'use client'

/**
 * CO: Komponent PublicHeader — współdzielony nagłówek dla stron publicznych / informacyjnych / płatności.
 * PO CO: Zapewnia spójną nawigację w całym serwisie: link powrotu do strony głównej (logo),
 *        dostęp do Cennika, płynne przejście do Panelu dla zalogowanych oraz logowanie/rejestrację
 *        dla niezalogowanych użytkowników. Zapobiega "ślepym zaułkom" nawigacyjnym.
 * JAK: Client component Next.js z useSession() z next-auth/react i useRouter() z next/navigation.
 *      Opcjonalny prop showBack wyświetla przycisk powrotu (router.back() z fallbackiem do '/').
 */

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { Video, ArrowLeft } from 'lucide-react'

export interface PublicHeaderProps {
  showBack?: boolean
}

export function PublicHeader({ showBack = false }: PublicHeaderProps) {
  const router = useRouter()
  const { data: session, status } = useSession()

  const handleBack = () => {
    if (typeof window !== 'undefined' && window.history.length > 1) {
      router.back()
    } else {
      router.push('/')
    }
  }

  return (
    <header className="sticky top-0 left-0 right-0 z-50 glass border-b border-white/5 bg-dark-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          {showBack && (
            <button
              type="button"
              onClick={handleBack}
              className="flex items-center gap-1.5 text-xs sm:text-sm text-dark-300 hover:text-white transition-smooth px-2.5 py-1.5 rounded-lg hover:bg-white/5 border border-white/5"
              title="Wróć"
            >
              <ArrowLeft className="w-4 h-4 shrink-0" />
              <span className="hidden xs:inline">Wróć</span>
            </button>
          )}
          <Link href="/" className="flex items-center gap-2 hover:opacity-90 transition-opacity">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center shrink-0">
              <Video className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight text-white">VSE</span>
            <span className="text-dark-400 text-sm ml-1 hidden sm:inline">Video SEO Engine</span>
          </Link>
        </div>

        <div className="flex items-center gap-2.5 sm:gap-4 shrink-0">
          <Link
            href="/cennik"
            className="text-dark-300 hover:text-white transition-smooth text-xs sm:text-sm font-medium"
          >
            Cennik
          </Link>

          {status === 'loading' ? (
            <div className="w-16 sm:w-20 h-8 rounded-lg bg-white/5 animate-pulse" />
          ) : session ? (
            <Link
              href="/dashboard"
              className="px-3 py-1.5 sm:px-4 sm:py-2 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-xs sm:text-sm font-medium transition-smooth glow-sm whitespace-nowrap"
            >
              Panel
            </Link>
          ) : (
            <div className="flex items-center gap-2 sm:gap-3">
              <Link
                href="/login"
                className="text-dark-300 hover:text-white transition-smooth text-xs sm:text-sm"
              >
                Zaloguj
              </Link>
              <Link
                href="/register"
                className="px-3 py-1.5 sm:px-4 sm:py-2 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-xs sm:text-sm font-medium transition-smooth glow-sm whitespace-nowrap"
              >
                Załóż konto
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

export default PublicHeader
