import type { CopiedKey } from '../types'

export function CopyButton({
  text,
  id,
  copiedKey,
  onCopy,
  label,
}: {
  text: string
  id: string
  copiedKey: CopiedKey
  onCopy: (text: string, id: string) => void
  label?: string
}) {
  const active = copiedKey === id
  return (
    <button
      onClick={() => onCopy(text, id)}
      className={`px-3 py-1 text-xs rounded-lg border transition-all duration-200 ${
        active
          ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
          : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white hover:border-gray-500'
      }`}
    >
      {active ? '\u2714\uFE0F Skopiowano' : (label ?? 'Kopiuj')}
    </button>
  )
}
