// ─── Utils / Helpers ────────────────────────────────────────────────────────
// Wydzielone z dashboard-inner.tsx — ETAP 0 refaktoru

import type { SchemaData, ChapterItem, FaqItem } from './types'

export function extractChapters(schema: SchemaData | null | undefined): ChapterItem[] {
  if (!schema) return []
  const graph = schema['@graph']
  if (Array.isArray(graph)) {
    const clips = (graph as Record<string, unknown>[]).filter(
      (n) => n['@type'] === 'Clip'
    )
    if (clips.length > 0)
      return clips.map((c) => ({
        name: c.name as string | undefined,
        startOffset: c.startOffset as number | undefined,
        endOffset: c.endOffset as number | undefined,
      }))
  }
  if (Array.isArray(schema.chapters)) {
    return schema.chapters.map((c: ChapterItem) => ({
      name: c.name ?? c.label,
      startOffset: c.startOffset ?? c.time,
      endOffset: c.endOffset,
    }))
  }
  return []
}

export function extractFaq(schema: SchemaData | null | undefined): FaqItem[] {
  if (!schema) return []
  const graph = schema['@graph']
  if (Array.isArray(graph)) {
    const faqPage = (graph as Record<string, unknown>[]).find(
      (n) => n['@type'] === 'FAQPage'
    )
    if (faqPage) {
      const items = faqPage['mainEntity']
      if (Array.isArray(items))
        return (items as Record<string, unknown>[]).map((q) => ({
          question: q['name'] as string | undefined,
          answer: ((q['acceptedAnswer'] as Record<string, unknown>)?.['text']) as string | undefined,
        }))
    }
  }
  if (Array.isArray(schema.faq)) return schema.faq
  return []
}

export function secToTimestamp(sec?: number): string {
  if (sec == null) return '?'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function chaptersToText(chapters: ChapterItem[]): string {
  return chapters
    .map((c) => `${secToTimestamp(c.startOffset ?? c.time)} — ${c.name ?? c.label ?? '(bez tytułu)'}`)
    .join('\n')
}

export function faqToHtml(faq: FaqItem[]): string {
  const items = faq
    .map(
      (f) =>
        `<details><summary>${f.question ?? ''}</summary>\n${f.answer ?? ''}\n</details>`
    )
    .join('\n')
  return `<h3>Często zadawane pytania</h3>\n${items}`
}

export function schemaToScriptTag(schema: SchemaData | null): string {
  return `<script type="application/ld+json">\n${JSON.stringify(schema ?? {}, null, 2)}\n</script>`
}

export function articleToText(schema: SchemaData | null, faq: FaqItem[]): string {
  const parts: string[] = []
  if (schema?.post_title) parts.push(`# ${schema.post_title}\n`)
  if (schema?.lead) parts.push(`${schema.lead}\n`)
  if (schema?.article_body) parts.push(`${schema.article_body}\n`)
  if (faq.length > 0) {
    parts.push('## FAQ\n')
    faq.forEach((f) => {
      parts.push(`**${f.question ?? ''}**\n${f.answer ?? ''}\n`)
    })
  }
  return parts.join('\n')
}

export function loadWpCredentials(): { wpUrl: string; wpUser: string; wpPassword: string } {
  if (typeof window === 'undefined') return { wpUrl: 'https://', wpUser: '', wpPassword: '' }
  try {
    const saved = localStorage.getItem('vse_wp_credentials')
    if (saved) return JSON.parse(saved)
  } catch { /* ignore */ }
  return { wpUrl: 'https://', wpUser: '', wpPassword: '' }
}

export function saveWpCredentials(creds: { wpUrl: string; wpUser: string; wpPassword: string }): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem('vse_wp_credentials', JSON.stringify(creds))
  } catch { /* ignore */ }
}

export function extractVideoId(url: string): string {
  if (!url) return ''
  const match = url.match(/(?:youtu\.be\/|youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|shorts\/)([^"&?\/\s]{11})/)
  return match ? match[1] : (url.length === 11 ? url : '')
}

export function buildYtDescription(schema: SchemaData | null | undefined, wpUrl?: string): string {
  if (!schema) return ''
  const parts: string[] = []

  const body = schema?.youtube_description_body ?? schema?.youtube_description_hook ?? schema?.video_description ?? ''
  if (body) parts.push(body as string)

  if (wpUrl) parts.push(`🔗 Artykuł: ${wpUrl}`)

  if (schema.youtube_mid_cta) parts.push(schema.youtube_mid_cta as string)

  const rawChapters = schema.chapters
  if (Array.isArray(rawChapters) && rawChapters.length > 0) {
    const lines = rawChapters.map((c: ChapterItem) => {
      const sec = c.time ?? c.startOffset ?? 0
      const m = Math.floor(sec / 60).toString().padStart(2, '0')
      const s = Math.floor(sec % 60).toString().padStart(2, '0')
      const title = c.label ?? c.name ?? ''
      return `${m}:${s} ${title}`.trim()
    })
    parts.push('ROZDZIAŁY:\n' + lines.join('\n'))
  }

  if (schema.youtube_credits) parts.push(schema.youtube_credits as string)

  const hashtags = schema.youtube_hashtags
  if (hashtags) {
    if (Array.isArray(hashtags)) {
      const tags = (hashtags as string[])
        .map(t => t.startsWith('#') ? t : `#${t}`)
        .join(', ')
      if (tags) parts.push(tags)
    } else if (typeof hashtags === 'string') {
      parts.push(hashtags)
    }
  }

  return parts.join('\n\n')
}
