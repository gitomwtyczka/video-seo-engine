'use client'

import { ResultSection } from './ResultSection'
import { CopyButton } from './CopyButton'
import type { SchemaData, FaqItem, QuoteItem } from '../types'
import { articleToText, faqToHtml } from '../utils'

interface ArticleTabProps {
  schema: SchemaData | null
  faq: FaqItem[]
  quotes?: QuoteItem[]
  copiedKey: string | null
  onCopy: (text: string, id: string) => void
}

export function ArticleTab({ schema, faq, quotes, copiedKey, onCopy }: ArticleTabProps) {
  const quotesList = (quotes ?? (schema?.quotes as QuoteItem[] | undefined) ?? []).filter(
    (q) => Boolean(q && (q.text || q.speaker || q.author))
  )

  return (
    <div>
      <div className="flex justify-end mb-4">
        <CopyButton
          text={articleToText(schema, faq)}
          id="article_all"
          copiedKey={copiedKey}
          onCopy={onCopy}
          label="Kopiuj cały artykuł"
        />
      </div>

      <ResultSection
        title="Lead artykułu"
        copyText={schema?.lead ?? ''}
        copyId="lead"
        copiedKey={copiedKey}
        onCopy={onCopy}
      >
        <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
          {schema?.lead ?? '(brak leadu)'}
        </p>
      </ResultSection>

      <ResultSection
        title="Treść artykułu"
        copyText={schema?.article_body ?? ''}
        copyId="article_body"
        copiedKey={copiedKey}
        onCopy={onCopy}
      >
        <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
          {schema?.article_body ?? '(brak treści)'}
        </div>
      </ResultSection>

      {quotesList.length > 0 && (
        <ResultSection
          title={`Cytaty (${quotesList.length})`}
          copyText={quotesList
            .map((q) => {
              const author = q.speaker || q.author
              return author ? `"${q.text ?? ''}" — ${author}` : `"${q.text ?? ''}"`
            })
            .join('\n')}
          copyId="art_quotes"
          copiedKey={copiedKey}
          onCopy={onCopy}
          badge={`${quotesList.length}`}
        >
          <div className="space-y-3">
            {quotesList.map((q, i) => {
              const author = q.speaker || q.author
              return (
                <blockquote key={i} className="border-l-2 border-violet-500/50 pl-4">
                  <p className="text-gray-200 text-sm italic">"{q.text ?? ''}"</p>
                  {author && (
                    <footer className="text-xs text-gray-500 mt-1">— {author}</footer>
                  )}
                </blockquote>
              )
            })}
          </div>
        </ResultSection>
      )}

      {faq.length > 0 && (
        <ResultSection
          title="Sekcja FAQ (HTML)"
          copyText={faqToHtml(faq)}
          copyId="faq"
          copiedKey={copiedKey}
          onCopy={onCopy}
          badge={`${faq.length} pytań`}
        >
          <div className="space-y-3 text-sm">
            {faq.map((item, idx) => (
              <details key={idx} className="bg-gray-800/50 rounded-lg p-3 border border-gray-700/50">
                <summary className="font-medium text-violet-300 cursor-pointer">{item.question}</summary>
                <p className="mt-2 text-gray-400 text-xs leading-relaxed">{item.answer}</p>
              </details>
            ))}
          </div>
        </ResultSection>
      )}
    </div>
  )
}

export default ArticleTab
