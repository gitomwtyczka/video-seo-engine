import Link from 'next/link'
import { ErrorBoundary } from '../error-boundary'

export function WpQuickPanel() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
  return (
    <ErrorBoundary>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center text-base">🔌</div>
            <div>
              <p className="text-sm font-medium text-white">Integracja WordPress &amp; Wtyczka VSE v3.0</p>
              <p className="text-xs text-gray-500">Auto-parowanie portali przez Klucz API (Zero App Passwords!) lub ręczna publikacja</p>
            </div>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <a
              href={`${apiUrl}/v1/plugin/download`}
              download="vse-video-seo.zip"
              className="px-3 py-1.5 rounded-lg bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/40 text-xs font-semibold text-violet-300 transition-colors"
            >
              📥 Pobierz wtyczkę WordPress v3.0 (.zip)
            </a>
            <Link
              href="/ustawienia#wp-plugin"
              className="text-xs text-violet-400 hover:text-violet-300 transition-colors font-medium"
            >
              Klucz API / Portale →
            </Link>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[
            { icon: '🔌', label: 'Wtyczka VSE v3.0', desc: 'Auto-parowanie z klucza API' },
            { icon: '🚀', label: '1-Click Publish', desc: 'Publikacja z Dashboardu i WP' },
            { icon: '📊', label: 'SEO Schema <head>', desc: 'VideoObject + Clip + FAQ' },
          ].map((item) => (
            <div key={item.label} className="bg-gray-800/50 rounded-lg p-3 text-center">
              <div className="text-xl mb-1">{item.icon}</div>
              <p className="text-xs font-medium text-white">{item.label}</p>
              <p className="text-xs text-gray-500 mt-0.5">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </ErrorBoundary>
  )
}
