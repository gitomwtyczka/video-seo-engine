'use client'

import { ResultSection } from './ResultSection'

interface YouTubeTabProps {
  ytDescription: string
  copiedKey: string | null
  onCopy: (text: string, id: string) => void
}

export function YouTubeTab({ ytDescription, copiedKey, onCopy }: YouTubeTabProps) {
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
    </div>
  )
}

export default YouTubeTab
