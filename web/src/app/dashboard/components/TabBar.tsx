import type { TabKey } from '../types'

export function TabBar({
  active,
  onChange,
  chaptersCount,
  faqCount,
}: {
  active: TabKey
  onChange: (tab: TabKey) => void
  chaptersCount: number
  faqCount: number
}) {
  const tabs: { key: TabKey; label: string; badge?: number }[] = [
    { key: 'schema', label: 'Schemat' },
    { key: 'article', label: 'Artyku\u0142', badge: faqCount > 0 ? faqCount : undefined },
    { key: 'chapters', label: 'Rozdzia\u0142y', badge: chaptersCount > 0 ? chaptersCount : undefined },
    { key: 'youtube', label: 'Opis YouTube' },
    { key: 'shorts', label: '\u2702\uFE0F ShortMachine' },
  ]

  return (
    <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-xl p-1 mb-5">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
            active === tab.key
              ? 'bg-violet-600/20 text-violet-400 border border-violet-500/30'
              : 'text-gray-400 hover:text-white hover:bg-gray-800/50 border border-transparent'
          }`}
        >
          {tab.label}
          {tab.badge != null && tab.badge > 0 && (
            <span className={`px-1.5 py-0.5 text-xs rounded-full ${
              active === tab.key
                ? 'bg-violet-500/30 text-violet-300'
                : 'bg-gray-700 text-gray-500'
            }`}>
              {tab.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
