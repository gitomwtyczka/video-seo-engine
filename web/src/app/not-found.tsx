/**
 * CO: Strona błędu 404 (Not Found) w Next.js 14 App Router.
 * PO CO: Zapewnia estetyczną stronę błędu 404 z PublicHeader oraz szybkimi
 *        linkami powrotu do strony głównej i panelu użytkownika.
 * JAK: Komponent not-found.tsx z PublicHeader, oznaczeniem 404
 *      oraz przyciskami "Strona główna" i "Panel".
 */

import Link from 'next/link'
import { PublicHeader } from '@/components/PublicHeader'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 flex flex-col">
      <PublicHeader showBack />
      <main className="flex-1 flex items-center justify-center px-4 py-16">
        <div className="max-w-md w-full text-center">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-brand-500/10 border border-brand-500/20 text-brand-400 font-extrabold text-3xl mb-6 glow-sm">
            404
          </div>
          <h1 className="text-3xl font-extrabold text-white mb-3">
            Nie znaleziono strony
          </h1>
          <p className="text-dark-300 text-sm mb-8 leading-relaxed">
            Strona, której szukasz, nie istnieje lub została przeniesiona pod inny adres.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              href="/"
              className="px-6 py-3 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-medium text-sm transition-smooth glow-sm"
            >
              Strona główna
            </Link>
            <Link
              href="/dashboard"
              className="px-6 py-3 rounded-xl glass hover:bg-white/10 text-white font-medium text-sm transition-smooth"
            >
              Panel
            </Link>
          </div>
        </div>
      </main>
    </div>
  )
}
