'use client'

import { useState, useEffect, useRef } from 'react'
import type { SchemaData, InjectResult } from '../types'
import { loadWpCredentials, saveWpCredentials } from '../utils'

export interface InjectModalProps {
  schemaData: SchemaData
  videoUrl: string
  selectedPortalId: string
  portalName?: string
  portalUrl?: string
  accessToken?: string
  onClose: () => void
  ytChannels?: any[]
  jobId?: string | null
}

export function InjectModal({
  schemaData,
  videoUrl,
  selectedPortalId,
  portalName,
  portalUrl,
  accessToken,
  onClose,
  ytChannels,
  jobId,
}: InjectModalProps) {
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

  // Preselekcja kanału będącego właścicielem wideo
  const videoOwnerChannelId = (schemaData as any)?.channel_id || (schemaData as any)?.youtube_channel_id || ''

  useEffect(() => {
    if (selectedYtChannelIds.length === 0 && ytChannels && ytChannels.length > 0) {
      if (videoOwnerChannelId) {
        const ownerMatch = ytChannels.find(c => c.channel_id === videoOwnerChannelId)
        if (ownerMatch) {
          setSelectedYtChannelIds([ownerMatch.channel_id])
          return
        }
      }
      if (ytChannels.length === 1) {
        setSelectedYtChannelIds([ytChannels[0].channel_id])
      }
    }
  }, [ytChannels, videoOwnerChannelId, selectedYtChannelIds.length])

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
        job_id: jobId || undefined,
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
      try { data = await res.json() } catch { data = { error: `Błąd serwera (HTTP ${res.status})` } }

      if (!res.ok) {
        let errStr = data?.detail || data?.error || `Błąd serwera (HTTP ${res.status})`
        if (typeof errStr === 'object') {
          errStr = JSON.stringify(errStr, null, 2)
        }
        throw new Error(errStr)
      }

      const ytChannelsList: Array<{ channel_id: string; status: string }> = data?.yt_channels || []
      const ytErrors = ytChannelsList
        .filter(item => item.status && item.status !== 'ok' && !item.status.startsWith('warning'))
        .map(item => `${item.channel_id}: ${item.status}`)

      let ytErrorMsg: string | undefined = undefined
      if (selectedYtChannelIds.length > 0) {
        if (!data?.youtube_updated || ytErrors.length > 0) {
          ytErrorMsg = ytErrors.length > 0 ? ytErrors.join('; ') : 'Brak potwierdzenia aktualizacji wideo na YouTube'
        }
      }

      setPublishResult({
        ...data,
        ytError: ytErrorMsg,
      })
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
            {schemaData.meta_description && (\n              <p className=\"text-xs text-gray-400 mt-1 line-clamp-2\">\n                {schemaData.meta_description}\n              </p>\n            )}\n          </div>\n\n          {!isManual && portalName && (\n            <div className=\"flex items-center gap-2 px-3 py-2 bg-violet-500/5 border border-violet-500/15 rounded-lg mb-4\">\n              <span className=\"text-xs text-violet-400\">🚀</span>\n              <span className=\"text-sm text-gray-200\">Publikujesz na: <span className=\"font-semibold\">{portalName}</span></span>\n              <span className=\"text-xs text-gray-500 ml-auto\">{portalUrl}</span>\n            </div>\n          )}\n\n          {isManual && (\n            <>\n              <div>\n                <label className=\"block text-xs text-gray-400 mb-1.5\">URL portalu WordPress</label>\n                <input\n                  type=\"text\"\n                  value={wpUrl}\n                  onChange={(e) => setWpUrl(e.target.value)}\n                  placeholder=\"https://twojportal.pl\"\n                  className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors\"\n                />\n              </div>\n\n              <div className=\"grid grid-cols-2 gap-3\">\n                <div>\n                  <label className=\"block text-xs text-gray-400 mb-1.5\">Użytkownik WP</label>\n                  <input\n                    type=\"text\"\n                    value={wpUser}\n                    onChange={(e) => setWpUser(e.target.value)}\n                    placeholder=\"admin\"\n                    className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors\"\n                  />\n                </div>\n                <div>\n                  <label className=\"block text-xs text-gray-400 mb-1.5\">Application Password</label>\n                  <input\n                    type=\"password\"\n                    value={wpPassword}\n                    onChange={(e) => setWpPassword(e.target.value)}\n                    placeholder=\"xxxx xxxx xxxx xxxx\"\n                    className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors\"\n                  />\n                </div>\n              </div>\n            </>\n          )}\n\n          <div className=\"mb-4\">\n            <label className=\"block text-xs text-gray-400 mb-1.5\">Dodatkowo: Opublikuj opis na YouTube</label>\n            {ytChannels && ytChannels.length > 0 ? (\n              <div className=\"space-y-2 max-h-32 overflow-y-auto bg-gray-800/50 p-2 rounded-lg border border-gray-700\">\n                {ytChannels.map(ch => {\n                  const isOwner = videoOwnerChannelId && ch.channel_id === videoOwnerChannelId\n                  return (\n                    <label key={ch.channel_id} className=\"flex items-center gap-2 cursor-pointer\">\n                      <input\n                        type=\"checkbox\"\n                        checked={selectedYtChannelIds.includes(ch.channel_id)}\n                        onChange={(e) => {\n                          if (e.target.checked) setSelectedYtChannelIds(p => [...p, ch.channel_id])\n                          else setSelectedYtChannelIds(p => p.filter(id => id !== ch.channel_id))\n                        }}\n                        className=\"accent-violet-500 rounded\"\n                      />\n                      <span className=\"text-sm text-gray-300\">{ch.channel_title}</span>\n                      {isOwner && (\n                        <span className=\"text-[10px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded border border-emerald-500/30\">\n                          Właściciel wideo\n                        </span>\n                      )}\n                    </label>\n                  )\n                })}\n              </div>\n            ) : (\n              <div className=\"p-3 bg-gray-800/50 rounded-lg border border-gray-700\">\n                <p className=\"text-xs text-amber-500/90 flex items-center gap-1.5\">\n                  ⚠️ Brak podłączonych kanałów YouTube.\n                  <a href=\"/ustawienia\" target=\"_blank\" rel=\"noreferrer\" className=\"underline hover:text-amber-400 transition-colors ml-1\">\n                    Przejdź do ustawień\n                  </a>\n                </p>\n              </div>\n            )}\n\n            {selectedYtChannelIds.length > 0 && ytChannels && ytChannels.length > 0 && (\n              <div className=\"mt-3\">\n                {!showYtPreview ? (\n                  <button\n                    onClick={() => setShowYtPreview(true)}\n                    className=\"text-xs text-violet-400 hover:text-violet-300 underline\"\n                  >\n                    Pokaż edytowalny podgląd opisu YT\n                  </button>\n                ) : (\n                  <div className=\"mt-2 animate-in slide-in-from-top-2\">\n                    <label className=\"block text-xs text-gray-400 mb-1\">\n                      Podgląd opisu YouTube <span className=\"text-gray-600\">(edytowalny)</span>\n                    </label>\n                    <textarea\n                      value={ytDescPreview}\n                      onChange={(e) => setYtDescPreview(e.target.value)}\n                      rows={6}\n                      className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-violet-500 resize-y font-mono\"\n                    />\n                    <button\n                      onClick={() => setShowYtPreview(false)}\n                      className=\"mt-1 text-xs text-gray-500 hover:text-gray-400\"\n                    >\n                      Ukryj podgląd\n                    </button>\n                  </div>\n                )}\n              </div>\n            )}\n          </div>\n\n          <div className=\"grid grid-cols-2 gap-3\">\n            <div>\n              <label className=\"block text-xs text-gray-400 mb-1.5\">\n                ID posta WP <span className=\"text-gray-600\">(puste = nowy post)</span>\n              </label>\n              <input\n                type=\"number\"\n                value={wpPostId}\n                onChange={(e) => setWpPostId(e.target.value)}\n                placeholder=\"Puste = nowy artykuł\"\n                className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors\"\n              />\n            </div>\n            <div>\n              <label className=\"block text-xs text-gray-400 mb-1.5\">Status publikacji</label>\n              <div className=\"flex gap-4 h-[42px] items-center\">\n                <label className=\"flex items-center gap-2 cursor-pointer\">\n                  <input\n                    type=\"radio\"\n                    name=\"modal_post_status\"\n                    value=\"draft\"\n                    checked={postStatus === 'draft'}\n                    onChange={() => setPostStatus('draft')}\n                    className=\"accent-violet-500\"\n                  />\n                  <span className=\"text-sm text-gray-300\">Szkic</span>\n                </label>\n                <label className=\"flex items-center gap-2 cursor-pointer\">\n                  <input\n                    type=\"radio\"\n                    name=\"modal_post_status\"\n                    value=\"publish\"\n                    checked={postStatus === 'publish'}\n                    onChange={() => setPostStatus('publish')}\n                    className=\"accent-violet-500\"\n                  />\n                  <span className=\"text-sm text-gray-300\">Publikuj</span>\n                </label>\n              </div>\n            </div>\n          </div>\n\n          <div>\n            <label className=\"block text-xs text-gray-400 mb-1.5\">Format wpisu WordPress</label>\n            <select\n              value={postFormat}\n              onChange={(e) => setPostFormat(e.target.value)}\n              className=\"w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer\"\n              style={{ backgroundImage: 'url(\"data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' fill=\\'none\\' viewBox=\\'0 0 20 20\\'%3E%3Cpath stroke=\\'%236b7280\\' stroke-linecap=\\'round\\' stroke-linejoin=\\'round\\' stroke-width=\\'1.5\\' d=\\'M6 8l4 4 4-4\\'/%3E%3C/svg%3E\")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.5rem center', backgroundSize: '1.5em 1.5em', paddingRight: '2.5rem' }}\n            >\n              <option value=\"video\">🎬 Film (video)</option>\n              <option value=\"standard\">📄 Standard</option>\n              <option value=\"gallery\">🖼️ Galeria (gallery)</option>\n              <option value=\"quote\">💬 Cytat (quote)</option>\n            </select>\n            <p className=\"text-xs text-gray-600 mt-1\">Domyślnie: Film — optymalny dla treści video SEO</p>\n          </div>\n\n          <button\n            onClick={handlePublish}\n            disabled={publishing || (!isManual && !selectedPortalId && selectedYtChannelIds.length === 0) || (isManual && !wpUrl && selectedYtChannelIds.length === 0)}\n            className=\"w-full py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-xl font-semibold text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2\"\n          >\n            {publishing ? (\n              <><span className=\"animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full\" /> Publikowanie...</>\n            ) : (\n              <>🚀 Opublikuj na portalu</>\n            )}\n          </button>\n\n          {publishResult && (\n            <div\n              className={`p-4 rounded-xl text-sm ${\n                publishResult.error\n                  ? 'bg-red-500/10 border border-red-500/20 text-red-400'\n                  : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'\n              }`}\n            >\n              {publishResult.error ? (\n                <><span className=\"font-medium\">⚠️ Błąd:</span> {publishResult.error}</>\n              ) : (\n                <div className=\"space-y-1\">\n                  <p><span className=\"font-medium\">✔️ Sukces!</span>\n                    {publishResult.created ? ' Utworzono nowy artykuł' : ' Zaktualizowano artykuł'}\n                    {publishResult.wp_post_id && ` (ID: ${publishResult.wp_post_id})`}\n                  </p>\n                  {publishResult.post_url && (\n                    <a\n                      href={publishResult.post_url}\n                      target=\"_blank\"\n                      rel=\"noopener noreferrer\"\n                      className=\"inline-flex items-center gap-1 text-emerald-300 hover:text-emerald-200 underline underline-offset-2\"\n                    >\n                      Otwórz artykuł na portalu →\n                    </a>\n                  )}\n                  {publishResult.ytError && (\n                    <div className=\"mt-2 pt-2 border-t border-emerald-500/20 text-amber-300 text-xs\">\n                      ⚠️ Portal OK, ale wystąpił błąd YouTube: <span className=\"font-mono text-amber-200\">{publishResult.ytError}</span>\n                    </div>\n                  )}\n                  {publishResult.youtube_updated && !publishResult.ytError && selectedYtChannelIds.length > 0 && (\n                    <p className=\"text-xs text-emerald-300 mt-1\">\n                      🎬 Opis na kanale YouTube został pomyślnie zaktualizowany.\n                    </p>\n                  )}\n                </div>\n              )}\n            </div>\n          )}\n\n          <p className=\"text-xs text-gray-600 text-center\">\n            {isManual ? 'Dane logowania zapamiętane w przeglądarce (localStorage)' : 'Credentials pobrane z zapisanego portalu'}\n          </p>\n        </div>\n      </div>\n    </div>\n  )\n}\n\nexport default InjectModal\n