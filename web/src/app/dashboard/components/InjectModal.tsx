'use client'

import { useState, useEffect, useRef } from 'react'
import type { SchemaData, InjectResult } from '../types'
import { loadWpCredentials, saveWpCredentials } from '../utils'

export function InjectModal({
  schemaData,
  videoUrl,
  selectedPortalId,
  portalName,
  portalUrl,
  accessToken,
  onClose,
  ytChannels,
}: {
  schemaData: SchemaData
  videoUrl: string
  selectedPortalId: string
  portalName?: string
  portalUrl?: string
  accessToken?: string
  onClose: () => void
  ytChannels?: any[]
}) {
  const initialCreds = loadWpCredentials()
  const [wpUrl, setWpUrl] = useState(initialCreds.wpUrl)
  const [wpUser, setWpUser] = useState(initialCreds.wpUser)
  const [wpPassword, setWpPassword] = useState(initialCreds.wpPassword)
  const [wpPostId, setWpPostId] = useState('')
  const [postStatus, setPostStatus] = useState<'draft' | 'publish'>('draft')
  const [postFormat, setPostFormat] = useState('video')
  const [publishing, setPublishing] = useState(false)
  const [publishResult, setPublishResult] = useState<InjectResult | null>(null)
  const [selectedYtChannelIds, setSelectedYtChannelIds] = useState<string[]>([])
  const [ytDescPreview, setYtDescPreview] = useState<string>('')
  const [showYtPreview, setShowYtPreview] = useState<boolean>(false)

  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
      onClose()
    }
  }

  const isManual = selectedPortalId === '__manual__' || !selectedPortalId

  useEffect(() => {
    if (selectedYtChannelIds.length === 0) { setYtDescPreview(''); return }
    const parts: string[] = []
    if (schemaData?.youtube_description_body) parts.push(schemaData.youtube_description_body)
    if (schemaData?.youtube_mid_cta) parts.push(schemaData.youtube_mid_cta)
    if (schemaData?.youtube_credits) parts.push(schemaData.youtube_credits)
    if (schemaData?.youtube_hashtags) {
      if (Array.isArray(schemaData.youtube_hashtags)) {
        parts.push(schemaData.youtube_hashtags.join(' '))
      } else {
        parts.push(schemaData.youtube_hashtags)
      }
    }
    const firstCh = ytChannels?.find(ch => selectedYtChannelIds.includes(ch.channel_id))
    if (firstCh?.footer_text) parts.push(firstCh.footer_text)
    setYtDescPreview(parts.join('\n\n') || '(brak wygenerowanego opisu)')
  }, [selectedYtChannelIds, schemaData, ytChannels])

  const handlePublish = async () => {
    const isPublishingToWp = !isManual || (wpUser && wpPassword && wpUrl)
    if (!isPublishingToWp && selectedYtChannelIds.length === 0) {
      setPublishResult({ error: 'Uzupełnij URL portalu, użytkownika i Application Password lub wybierz kanał YouTube.' })
      return
    }

    if (isPublishingToWp && isManual) {
      saveWpCredentials({ wpUrl, wpUser, wpPassword })
    }

    setPublishing(true)
    setPublishResult(null)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const body: Record<string, unknown> = {
        video_url: videoUrl,
        schema_data: schemaData,
        post_status: postStatus,
        post_format: postFormat,
      }

      if (selectedYtChannelIds.length > 0) {
        body.yt_channel_ids = selectedYtChannelIds
        if (showYtPreview && ytDescPreview) {
          body.yt_override_description = ytDescPreview
        }
      }

      if (isPublishingToWp) {
        if (isManual) {
          body.site_config = {
            wp_base_url: wpUrl,
            wp_user: wpUser,
            wp_app_password: wpPassword,
          }
        } else {
          body.portal_id = selectedPortalId.trim()
        }
        if (wpPostId.trim()) {
          body.wp_post_id = parseInt(wpPostId, 10)
        }
      }

      const res = await fetch(`${apiUrl}/v1/inject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken && { Authorization: `Bearer ${accessToken}` }),
        },
        body: JSON.stringify(body),
      })
      let data: any
      try { data = await res.json() } catch { data = { error: `HTTP ${res.status}` } }

      if (!res.ok) {
        let errStr = data?.detail || data?.error || `Błąd serwera (HTTP ${res.status})`
        if (typeof errStr === 'object') {
          errStr = JSON.stringify(errStr, null, 2)
        }
        throw new Error(errStr)
      }
      setPublishResult(data)
      if (data?.yt_results) {
        const errors: string[] = []
        Object.entries(data.yt_results).forEach(([_, status]) => {
          if (status !== 'ok') errors.push(`Błąd YT: ${status}`)
        })
        if (errors.length > 0) {
          setPublishResult(prev => ({
            ...prev,
            error: (prev?.error ? prev.error + '\n' : '') + errors.join('\n')
          }))
        }
      }
    } catch (e: unknown) {
      setPublishResult({ error: e instanceof Error ? e.message : 'Błąd połączenia' })
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={handleBackdropClick}
    >
      <div
        ref={modalRef}
        className="w-full max-w-lg bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden animate-in"
        style={{ animation: 'fadeInUp 0.25s ease-out' }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gradient-to-r from-violet-950/50 to-fuchsia-950/30">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center text-sm">
              🚀
            </div>
            <div>
              <h3 className="font-semibold text-white">Publikuj na WordPress</h3>
              <p className="text-xs text-gray-400">Wyślij artykuł + SEO schema na portal</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-1">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4">
            <p className="text-xs text-gray-500 mb-1">Artykuł do publikacji:</p>
            <p className="text-sm font-medium text-white truncate">
              {schemaData.post_title ?? '(brak tytułu)'}
            </p>
            {schemaData.meta_description && (
              <p className="text-xs text-gray-400 mt-1 line-clamp-2">
                {schemaData.meta_description}
              </p>
            )}
          </div>

          {!isManual && portalName && (
            <div className="flex items-center gap-2 px-3 py-2 bg-violet-500/5 border border-violet-500/15 rounded-lg mb-4">
              <span className="text-xs text-violet-400">🚀</span>
              <span className="text-sm text-gray-200">Publikujesz na: <span className="font-semibold">{portalName}</span></span>
              <span className="text-xs text-gray-500 ml-auto">{portalUrl}</span>
            </div>
          )}

          {isManual && (
            <>
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">URL portalu WordPress</label>
                <input
                  type="text"
                  value={wpUrl}
                  onChange={(e) => setWpUrl(e.target.value)}
                  placeholder="https://twojportal.pl"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1.5">Użytkownik WP</label>
                  <input
                    type="text"
                    value={wpUser}
                    onChange={(e) => setWpUser(e.target.value)}
                    placeholder="admin"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1.5">Application Password</label>
                  <input
                    type="password"
                    value={wpPassword}
                    onChange={(e) => setWpPassword(e.target.value)}
                    placeholder="xxxx xxxx xxxx xxxx"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
                  />
                </div>
              </div>
            </>
          )}

          <div className="mb-4">
            <label className="block text-xs text-gray-400 mb-1.5">Dodatkowo: Opublikuj opis na YouTube</label>
            {ytChannels && ytChannels.length > 0 ? (
              <div className="space-y-2 max-h-32 overflow-y-auto bg-gray-800/50 p-2 rounded-lg border border-gray-700">
                {ytChannels.map(ch => (
                  <label key={ch.channel_id} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedYtChannelIds.includes(ch.channel_id)}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedYtChannelIds(p => [...p, ch.channel_id])
                        else setSelectedYtChannelIds(p => p.filter(id => id !== ch.channel_id))
                      }}
                      className="accent-violet-500 rounded"
                    />
                    <span className="text-sm text-gray-300">{ch.channel_title}</span>
                  </label>
                ))}
              </div>
            ) : (
              <div className="p-3 bg-gray-800/50 rounded-lg border border-gray-700">
                <p className="text-xs text-amber-500/90 flex items-center gap-1.5">
                  ⚠️ Brak podłączonych kanałów YouTube.
                  <a href="/ustawienia" target="_blank" rel="noreferrer" className="underline hover:text-amber-400 transition-colors ml-1">
                    Przejdź do ustawień
                  </a>
                </p>
              </div>
            )}

            {selectedYtChannelIds.length > 0 && ytChannels && ytChannels.length > 0 && (
              <div className="mt-3">
                {!showYtPreview ? (
                  <button
                    onClick={() => setShowYtPreview(true)}
                    className="text-xs text-violet-400 hover:text-violet-300 underline"
                  >
                    Pokaż edytowalny podgląd opisu YT
                  </button>
                ) : (
                  <div className="mt-2 animate-in slide-in-from-top-2">
                    <label className="block text-xs text-gray-400 mb-1">
                      Podgląd opisu YouTube <span className="text-gray-600">(edytowalny)</span>
                    </label>
                    <textarea
                      value={ytDescPreview}
                      onChange={(e) => setYtDescPreview(e.target.value)}
                      rows={6}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-violet-500 resize-y font-mono"
                    />
                    <button
                      onClick={() => setShowYtPreview(false)}
                      className="mt-1 text-xs text-gray-500 hover:text-gray-400"
                    >
                      Ukryj podgląd
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">
                ID posta WP <span className="text-gray-600">(puste = nowy post)</span>
              </label>
              <input
                type="number"
                value={wpPostId}
                onChange={(e) => setWpPostId(e.target.value)}
                placeholder="Puste = nowy artykuł"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Status publikacji</label>
              <div className="flex gap-4 h-[42px] items-center">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="modal_post_status"
                    value="draft"
                    checked={postStatus === 'draft'}
                    onChange={() => setPostStatus('draft')}
                    className="accent-violet-500"
                  />
                  <span className="text-sm text-gray-300">Szkic</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="modal_post_status"
                    value="publish"
                    checked={postStatus === 'publish'}
                    onChange={() => setPostStatus('publish')}
                    className="accent-violet-500"
                  />
                  <span className="text-sm text-gray-300">Publikuj</span>
                </label>
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Format wpisu WordPress</label>
            <select
              value={postFormat}
              onChange={(e) => setPostFormat(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer"
              style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3E%3Cpath stroke=\'%236b7280\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.5rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }}
            >
              <option value="video">🎬 Film (video)</option>
              <option value="standard">📄 Standard</option>
              <option value="gallery">🖼️ Galeria (gallery)</option>
              <option value="quote">💬 Cytat (quote)</option>
            </select>
            <p className="text-xs text-gray-600 mt-1">Domyślnie: Film — optymalny dla treści video SEO</p>
          </div>

          <button
            onClick={handlePublish}
            disabled={publishing || (!isManual && !selectedPortalId && selectedYtChannelIds.length === 0) || (isManual && !wpUrl && selectedYtChannelIds.length === 0)}
            className="w-full py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-xl font-semibold text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
          >
            {publishing ? (
              <><span className="animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> Publikowanie...</>
            ) : (
              <>🚀 Opublikuj na portalu</>
            )}
          </button>

          {publishResult && (
            <div
              className={`p-4 rounded-xl text-sm ${
                publishResult.error
                  ? 'bg-red-500/10 border border-red-500/20 text-red-400'
                  : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
              }`}
            >
              {publishResult.error ? (
                <><span className="font-medium">⚠️ Błąd:</span> {publishResult.error}</>
              ) : (
                <div className="space-y-1">
                  <p><span className="font-medium">✔️ Sukces!</span>
                    {publishResult.created ? ' Utworzono nowy artykuł' : ' Zaktualizowano artykuł'}
                    {publishResult.wp_post_id && ` (ID: ${publishResult.wp_post_id})`}
                  </p>
                  {publishResult.post_url && (
                    <a
                      href={publishResult.post_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-emerald-300 hover:text-emerald-200 underline underline-offset-2"
                    >
                      Otwórz artykuł na portalu →
                    </a>
                  )}
                </div>
              )}
            </div>
          )}

          <p className="text-xs text-gray-600 text-center">
            {isManual ? 'Dane logowania zapamiętane w przeglądarce (localStorage)' : 'Credentials pobrane z zapisanego portalu'}
          </p>
        </div>
      </div>
    </div>
  )
}

export default InjectModal
