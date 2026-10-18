// ─── Types ──────────────────────────────────────────────────────────────────
// Wydzielone z dashboard-inner.tsx — ETAP 0 refaktoru

export interface VseLanguage {
  code: string
  label: string
  flag: string
  short: string
}

export const VSE_LANGUAGES: VseLanguage[] = [
  { code: 'pl', label: 'Polski', flag: '🇵🇱', short: 'PL' },
  { code: 'en', label: 'English', flag: '🇬🇧', short: 'EN' },
  { code: 'de', label: 'Deutsch', flag: '🇩🇪', short: 'DE' },
  { code: 'es', label: 'Español', flag: '🇪🇸', short: 'ES' },
  { code: 'fr', label: 'Français', flag: '🇫🇷', short: 'FR' },
  { code: 'it', label: 'Italiano', flag: '🇮🇹', short: 'IT' },
  { code: 'uk', label: 'Українська', flag: '🇺🇦', short: 'UK' },
  { code: 'pt', label: 'Português', flag: '🇵🇹', short: 'PT' },
]

export interface MultilangEntitlements {
  allow_cross_lang_input?: boolean
  allow_target_override?: boolean
  allow_per_material_adapt?: boolean
  max_adaptations_per_video?: number
  allowed_languages?: string[]
  has_multilang_addon?: boolean
}

export interface GenerateResponse {
  status: string
  video_id: string
  processing_time_s?: number
  schema_data?: SchemaData | null
  source_lang?: string | null
  target_lang?: string | null
  error?: string | null
}

export interface SchemaData {
  video_id?: string
  focus_keyphrase?: string
  focus_keyphrases?: string[]
  post_title?: string
  seo_title?: string
  yt_title?: string
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
  tags?: string[]
  wp_article_url?: string
  published_url?: string
  wp_url?: string
  source?: string
  media_id?: string
  source_lang?: string
  target_lang?: string
  json_ld?: unknown
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
  speaker?: string
  time?: number
}

export interface UserPlan {
  id: string
  display_name: string
  monthly_quota: number
}

export interface UserProfile {
  email: string
  is_verified?: boolean
  is_admin?: boolean
  has_multilang_addon?: boolean
  multilang?: MultilangEntitlements
  plan_badge?: string
  desktop_runner_active?: boolean
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

