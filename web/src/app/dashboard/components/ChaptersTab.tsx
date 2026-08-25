'use client'

import { ResultSection } from './ResultSection'
import type { ChapterItem } from '../types'
import { chaptersToText } from '../utils'

interface ChaptersTabProps {
  chapters: ChapterItem[]
  copiedKey: string | null
  onCopy: (text: string, id: string) => void
}

export function ChaptersTab({ chapters, copiedKey, onCopy }: ChaptersTabProps) {
  return (
    <div>
      <ResultSection
        title="Rozdziały YouTube"
        copyText={chaptersToText(chapters)}
        copyId="chapters"
        copiedKey={copiedKey}
        onCopy={onCopy}
        badge={`${chapters.length} rozdziałów`}
      >
        <pre className="text-xs text-gray-300 font-mono overflow-auto max-h-60 leading-relaxed">
          {chaptersToText(chapters)}
        </pre>
      </ResultSection>
    </div>
  )
}

export default ChaptersTab
