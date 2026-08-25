'use client'

import { ResultSection } from './ResultSection'

interface YouTubeTabProps {
  ytDescription: string
  copiedKey: string | null
  onCopy: (text: string, id: string) => void
  credits?: unknown
}

export function YouTubeTab({ ytDescription, copiedKey, onCopy, credits }: YouTubeTabProps) {
  return (
    <div>
      <ResultSection
        title="Wygenerowany opis YouTube"
        copyText={ytDescription}
        copyId="yt_desc"
        copiedKey={copiedKey}
        onCopy={onCopy}
      >
        <pre className="text-xs text-gray-300 font-mono overflow-auto max-h-96 whitespace-pre-wrap leading-relaxed">
          {ytDescription}
        </pre>
      </ResultSection>

      {credits !== undefined && (
        <ResultSection
          title="Credits"
          copyText={typeof credits === 'string' ? credits : credits ? JSON.stringify(credits) : ''}
          copyId="yt_credits"
          copiedKey={copiedKey}
          onCopy={onCopy}
        >
          <div className="text-xs text-gray-300 font-mono">
            {typeof credits === 'string' ? credits : credits ? JSON.stringify(credits) : '-'}
          </div>
        </ResultSection>
      )}
    </div>
  )
}

export default YouTubeTab
