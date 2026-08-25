// ─── Types ──────────────────────────────────────────────────────────────────
// Wydzielone z dashboard-inner.tsx — ETAP 0 refaktoru

export interface GenerateResponse {
  status: string
  video_id: string
  processing_time_s?: number
  schema_data?: SchemaData | null
  error?: string | null
}

export interface SchemaData {
  focus_keyphrase?: string
  post_title?: string
  meta_description?: string
  wp_slug?: string
  lead?: string
  article_body?: string
  chapters?: ChapterItem[]
  faq?: FaqItem[]
  quotes?: QuoteItem[]
  youtube_description_body?: string
  youtube_description_hook?: string
  youtube_description?: string
  video_description?: string
  youtube_mid_cta?: string
  youtube_credits?: string
  youtube_hashtags?: string[] | string
  wp_article_url?: string
  published_url?: string
  wp_url?: string
  [key: string]: unknown
}

export interface ChapterItem {
  name?: string
  startOffset?: number
  endOffset?: number
  label?: string
  time?: number
}

export interface FaqItem {
  question?: string
  answer?: string
}

export interface QuoteItem {
  text?: string
  author?: string
}

export interface UserPlan {
  id: string
  display_name: string
  monthly_quota: number
}

export interface UserProfile {
  email: string
  is_verified?: boolean
  plan: UserPlan
  usage: { used_this_month: number; quota: number; percent: number }
}

export interface InjectResult {
  status?: string
  wp_post_id?: number
  post_url?: string
  created?: boolean
  error?: string
  yt_results?: Record<string, string>
}

export type CopiedKey = string | null
export type TabKey = 'schema' | 'article' | 'chapters' | 'youtube' | 'shorts'
