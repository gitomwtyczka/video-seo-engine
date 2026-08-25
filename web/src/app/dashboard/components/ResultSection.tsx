import type { CopiedKey } from '../types'
import { CopyButton } from './CopyButton'

export function ResultSection({
  title,
  copyText,
  copyId,
  copiedKey,
  onCopy,
  badge,
  children,
}: {
  title: string
  copyText: string
  copyId: string
  copiedKey: CopiedKey
  onCopy: (text: string, id: string) => void
  badge?: string
  children: React.ReactNode
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden mb-4">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-gray-900/50">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-200">{title}</span>
          {badge && (
            <span className="px-2 py-0.5 text-xs bg-violet-500/15 text-violet-400 rounded-full border border-violet-500/20">
              {badge}
            </span>
          )}
        </div>
        <CopyButton text={copyText} id={copyId} copiedKey={copiedKey} onCopy={onCopy} />
      </div>
      <div className="p-4">{children}</div>
    </div>
  )
}
