import Link from 'next/link'
import { ErrorBoundary } from '../error-boundary'

export function WpQuickPanel() {
  return (
    <ErrorBoundary>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center text-base">\uD83D\uDE80</div>
          <div>
            <p className="text-sm font-medium text-white">Integracja WordPress</p>
            <p className="text-xs text-gray-500">Skonfiguruj portal do automatycznej publikacji</p>
          </div>
          <Link
            href="/ustawienia"
            className="ml-auto text-xs text-violet-400 hover:text-violet-300 transition-colors"
          >
            Konfiguruj \u2192
          </Link>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[
            { icon: '\uD83D\uDCCB', label: 'Kopiuj HTML', desc: 'Schemat gotowy do wklejenia' },
            { icon: '\uD83D\uDE80', label: 'Auto-publish', desc: 'Plan Pro/Agency' },
            { icon: '\uD83D\uDCCA', label: 'SEO Schema', desc: 'VideoObject + Clip + FAQ' },
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
