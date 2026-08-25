'use client'

import { ResultSection } from './ResultSection'
import type { SchemaData } from '../types'
import { schemaToScriptTag } from '../utils'

interface SchemaTabProps {
  schema: SchemaData | null
  copiedKey: string | null
  onCopy: (text: string, id: string) => void
}

export function SchemaTab({ schema, copiedKey, onCopy }: SchemaTabProps) {
  return (
    <div>
      <ResultSection
        title="Tytuł artykułu"
        copyText={schema?.post_title ?? ''}
        copyId="post_title"
        copiedKey={copiedKey}
        onCopy={onCopy}
      >
        <p className="text-white font-medium">{schema?.post_title ?? '(brak tytułu)'}</p>
        {schema?.focus_keyphrase && (
          <p className="text-xs text-gray-500 mt-1">
            Focus: <span className="text-violet-400">{schema.focus_keyphrase}</span>
          </p>
        )}
      </ResultSection>

      <ResultSection
        title="Meta description"
        copyText={schema?.meta_description ?? ''}
        copyId="meta_description"
        copiedKey={copiedKey}
        onCopy={onCopy}
      >
        <p className="text-gray-300 text-sm leading-relaxed">
          {schema?.meta_description ?? '(brak meta description)'}
        </p>
      </ResultSection>

      <ResultSection
        title="Schema JSON-LD"
        copyText={schemaToScriptTag(schema)}
        copyId="schema_jsonld"
        copiedKey={copiedKey}
        onCopy={onCopy}
        badge="Wklej do <head>"
      >
        <pre className="text-xs text-emerald-400 font-mono overflow-auto max-h-72 leading-relaxed">
{`<script type="application/ld+json">`}
{JSON.stringify(schema ?? {}, null, 2)}
{`</script>`}
        </pre>
      </ResultSection>
    </div>
  )
}

export default SchemaTab
