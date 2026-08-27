'use client'

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { extractYoutubeId } from '../utils'
import { YouTubePublishModal } from '../YouTubePublishModal'

interface ShortMachineTabProps {
  ytChannels: any[]
  initialYoutubeId?: string
  accessToken?: string
  session?: any
  source?: string
  isAudio?: boolean
}

export function ShortMachineTab({ ytChannels, initialYoutubeId, accessToken, session, source, isAudio }: ShortMachineTabProps) {
  const isAudioSource = isAudio || source === 'audio' || (initialYoutubeId ? (initialYoutubeId.startsWith('audio_') || initialYoutubeId.startsWith('audio://')) : false)

  // ShortMachine state
  const [smYoutubeId, setSmYoutubeId] = useState(initialYoutubeId || '')
  const [smCustomQuery, setSmCustomQuery] = useState('')
  const [smCountEmotional, setSmCountEmotional] = useState(2)
  const [smCountProfessional, setSmCountProfessional] = useState(2)
  const [smCountCustom, setSmCountCustom] = useState(3)
  const [shortLocalPath, setShortLocalPath] = useState<string>('')
  const [smCandidates, setSmCandidates] = useState<any[]>([])
  const [smPreviewIdx, setSmPreviewIdx] = useState<number | null>(null)
  const ytPlayerRef = useRef<any>(null)
  const ytIntervalRef = useRef<any>(null)
  const [smTitles, setSmTitles] = useState<Record<number, string>>({})
  const [smTags, setSmTags] = useState<Record<number, string[]>>({})
  const [smTitleLoading, setSmTitleLoading] = useState<Record<number, boolean>>({})

  // Auto-populate smYoutubeId from current video URL or initialYoutubeId
  useEffect(() => {
    if (initialYoutubeId && !smYoutubeId) {
      setSmYoutubeId(initialYoutubeId)
      return
    }
    if (!smYoutubeId && typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search)
      const jobVideoUrl = urlParams.get('video_url') || ''
      if (jobVideoUrl) {
        if (jobVideoUrl.startsWith('audio://')) {
          setSmYoutubeId(jobVideoUrl.replace('audio://', ''))
        } else {
          const match = jobVideoUrl.match(/(?:v=|youtu\.be\/|shorts\/)([a-zA-Z0-9_-]{11})/)
          if (match) setSmYoutubeId(match[1])
          else if (jobVideoUrl.length === 11 || jobVideoUrl.startsWith('audio_')) setSmYoutubeId(jobVideoUrl)
        }
      }
    }
  }, [initialYoutubeId])

  useEffect(() => {
    if (!smYoutubeId) return
    const cleanId = extractYoutubeId(smYoutubeId) || smYoutubeId
    if (!cleanId) return
    const apiBase = process.env.NEXT_PUBLIC_API_URL || ''
    fetch(`${apiBase}/v1/shorts/history/${cleanId}`)
      .then(r => r.json())
      .then(data => {
        if (data.candidates?.length > 0 && smCandidates.length === 0) {
          setSmCandidates(data.candidates)
          const newTitles: Record<number, string> = {}
          const newTags: Record<number, string[]> = {}
          data.candidates.forEach((c: any, i: number) => {
            newTitles[i] = c.suggested_title || c.title || ''
            newTags[i] = c.tags || []
          })
          setSmTitles(newTitles)
          setSmTags(newTags)
        }
        if (data.jobs?.length > 0 && data.candidates?.length > 0) {
          const restoredStatus: Record<number, any> = {}
          data.jobs.forEach((job: any) => {
            const idx = data.candidates.findIndex(
              (c: any) => Math.abs(c.start_sec - job.start_sec) < 1 &&
                          Math.abs(c.end_sec - job.end_sec) < 1
            )
            if (idx >= 0) {
              restoredStatus[idx] = {
                status: job.status,
                result_paths: job.result_paths,
                job_id: job.id,
                error: job.error,
              }
            }
          })
          if (Object.keys(restoredStatus).length > 0) {
            setSmJobStatus(prev => ({ ...restoredStatus, ...prev }))
          }
        }
      })
      .catch(err => console.warn('Failed to restore ShortMachine state:', err))
  }, [smYoutubeId])

  const [smLoading, setSmLoading] = useState(false)
  const [smError, setSmError] = useState<string | null>(null)
  const [smRenderConfig, setSmRenderConfig] = useState<Record<number, {format: string, subtitles: string}>>({})
  const [smJobStatus, setSmJobStatus] = useState<Record<number, any>>({})
  const [smTrimAdj, setSmTrimAdj] = useState<Record<number, {startDelta: number; endDelta: number}>>({})
  const [smExpandedIdx, setSmExpandedIdx] = useState<number | null>(null)
  const [smTrimMode, setSmTrimMode] = useState<'start' | 'end'>('start')
  const [smSelected, setSmSelected] = useState<Set<number>>(new Set())
  const [smFormat, setSmFormat] = useState<'raw' | 'short'>('raw')

  const toggleSmSelected = (idx: number) => setSmSelected(prev => {
    const next = new Set(prev)
    if (next.has(idx)) next.delete(idx); else next.add(idx)
    return next
  })

  const [smTargetYtId, setSmTargetYtId] = useState<Record<number, string>>({})
  const [smGlobalChannelId, setSmGlobalChannelId] = useState<string>('')
  const [smChannelOverride, setSmChannelOverride] = useState<Record<number, string>>({})
  const [smPublishAt, setSmPublishAt] = useState<Record<number, string>>({})
  const [smPrivacyStatus, setSmPrivacyStatus] = useState<Record<number, string>>({})
  const [smSelectedPlaylist, setSmSelectedPlaylist] = useState<Record<number, string>>({})
  const [smPlaylists, setSmPlaylists] = useState<{id: string, title: string}[]>([])
  const [smPlaylistsByChannel, setSmPlaylistsByChannel] = useState<Record<string, {id: string, title: string}[]>>({})
  const [playlistsLoading, setPlaylistsLoading] = useState(false)
  const [smModalOpenFor, setSmModalOpenFor] = useState<number | null>(null)
  const [srtLoading, setSrtLoading] = useState(false)
  const [srtPackage, setSrtPackage] = useState<any>(null)
  const [srtError, setSrtError] = useState<string | null>(null)

  const fetchPlaylistsForChannel = useCallback(async (channelId: string) => {
    if (!channelId) return
    const apiBase = process.env.NEXT_PUBLIC_API_URL || ''
    const effectiveToken = accessToken || session?.accessToken
    setPlaylistsLoading(true)
    try {
      const res = await fetch(`${apiBase}/v1/youtube/channels/${channelId}/playlists`, {
        headers: {
          'Content-Type': 'application/json',
          ...(effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {})
        }
      })
      if (!res.ok) {
        console.warn(`Failed to load playlists for channel ${channelId}: HTTP ${res.status}`)
        return
      }
      const data = await res.json()
      if (Array.isArray(data)) {
        setSmPlaylistsByChannel(prev => ({ ...prev, [channelId]: data }))
        setSmPlaylists(data)
      } else {
        console.warn('Playlists response is not an array:', data)
      }
    } catch (err) {
      console.warn('Failed to load playlists:', err)
    } finally {
      setPlaylistsLoading(false)
    }
  }, [accessToken, session])

  const handleGenerateSrt = async () => {
    if (!smYoutubeId) return
    const cleanId = extractYoutubeId(smYoutubeId) || smYoutubeId
    setSrtLoading(true)
    setSrtError(null)
    setSrtPackage(null)
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || ''
      const effectiveToken = accessToken || session?.accessToken
      const res = await fetch(`${apiBase}/v1/shorts/generate-srt/${cleanId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {})
        }
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setSrtPackage(data)
    } catch (e: any) {
      setSrtError(e.message)
    } finally {
      setSrtLoading(false)
    }
  }

  const downloadSrtFile = (filename: string, content: string) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  // Set default global channel if not set
  useEffect(() => {
    if (ytChannels.length > 0 && !smGlobalChannelId) {
      const defaultCh = ytChannels.find((ch: any) => ch.is_default) ?? ytChannels[0]
      if (defaultCh?.channel_id) {
        setSmGlobalChannelId(defaultCh.channel_id)
      }
    }
  }, [ytChannels, smGlobalChannelId])

  // Fetch playlists whenever active global channel changes or tokens are updated
  useEffect(() => {
    const activeChId = smGlobalChannelId || (ytChannels.find((ch: any) => ch.is_default) ?? ytChannels[0])?.channel_id
    if (activeChId) {
      fetchPlaylistsForChannel(activeChId)
    } else {
      setSmPlaylists([])
    }
  }, [smGlobalChannelId, ytChannels, fetchPlaylistsForChannel])

  const fmtSec = (sec: number) => `${Math.floor(sec/60)}:${String(Math.floor(sec%60)).padStart(2,'0')}`
  const getAdj = (idx: number, c: any) => ({ start: (c.start_sec??0)+(smTrimAdj[idx]?.startDelta??0), end: (c.end_sec??0)+(smTrimAdj[idx]?.endDelta??0) })

  const handleRegenerateTitle = async (i: number, c: any) => {
    const adj = getAdj(i, c)
    const apiBase = process.env.NEXT_PUBLIC_API_URL || ''
    setSmTitleLoading(p => ({...p, [i]: true}))
    try {
      const res = await fetch(`${apiBase}/v1/shorts/title`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({youtube_id: smYoutubeId, start_sec: adj.start, end_sec: adj.end})
      })
      const data = await res.json()
      if (data.title) setSmTitles(p => ({...p, [i]: data.title}))
      if (data.tags?.length) setSmTags(p => ({...p, [i]: data.tags}))
    } finally {
      setSmTitleLoading(p => ({...p, [i]: false}))
    }
  }

  useEffect(() => {
    if (typeof window === 'undefined') return
    if ((window as any).YT) return
    const tag = document.createElement('script')
    tag.src = 'https://www.youtube.com/iframe_api'
    document.head.appendChild(tag)
  }, [])

  const handleGetCandidates = async () => {
    setSmLoading(true)
    setSmError(null)
    setSmCandidates([])
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const effectiveToken = accessToken || session?.accessToken
      const cleanId = extractYoutubeId(smYoutubeId) || smYoutubeId
      const res = await fetch(`${apiUrl}/v1/shorts/candidates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {}) },
        body: JSON.stringify({
          youtube_id: cleanId,
          youtube_url: smYoutubeId.startsWith('http') ? smYoutubeId : undefined,
          custom_query: smCustomQuery,
          count_emotional: smCountEmotional,
          count_professional: smCountProfessional,
          count_custom: smCustomQuery ? smCountCustom : 0,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setSmCandidates(data.candidates || [])
      const newTitles: Record<number, string> = {}
      const newTags: Record<number, string[]> = {}
      ;(data.candidates || []).forEach((c: any, i: number) => {
        newTitles[i] = c.suggested_title || ''
        newTags[i] = c.tags || []
      })
      setSmTitles(newTitles)
      setSmTags(newTags)
    } catch (e: any) {
      setSmError(e.message)
    } finally {
      setSmLoading(false)
    }
  }

  const handleRenderShort = async (candidate: any, index: number) => {
    try {
      const cfg = smRenderConfig[index] || {}
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const effectiveToken = accessToken || session?.accessToken
      const res = await fetch(`${apiUrl}/v1/shorts/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {}) },
        body: JSON.stringify({
          youtube_url: smYoutubeId.startsWith('http') ? smYoutubeId : `https://www.youtube.com/watch?v=${smYoutubeId}`,
          youtube_id: extractYoutubeId(smYoutubeId) || smYoutubeId,
          start_sec: candidate.start_sec,
          end_sec: candidate.end_sec,
          candidate_data: candidate,
          format: smFormat,
          render_format: cfg.format || '9:16',
          subtitles: cfg.subtitles || 'srt',
          output_dir: 'C:\\VSE\\Shorts',
          ...(shortLocalPath ? { local_path: shortLocalPath } : {}),
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const renderJobId = data.job_id
      setSmJobStatus(prev => ({...prev, [index]: {status: 'pending'}}))
      
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        if (attempts > 40) { clearInterval(poll); return }
        try {
          const statusRes = await fetch(`${apiUrl}/v1/shorts/${renderJobId}`, {
            headers: { ...(effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {}) }
          })
          const statusData = await statusRes.json()
          setSmJobStatus(prev => ({...prev, [index]: statusData}))
          if (statusData.status === 'done' || statusData.status === 'error') {
            clearInterval(poll)
          }
        } catch {}
      }, 3000)
    } catch (e: any) {
      setSmError(`Render error: ${e.message}`)
    }
  }

  return (
    <>
      <div className="space-y-6">
        <h2 className="text-xl font-semibold text-white">✂️ ShortMachine</h2>
        
        <div className="bg-gray-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-white">Propozycje kandydatów</h3>
          
          <div>
            <label className="block text-sm text-gray-400 mb-1">Źródło wideo/audio (ID lub URL)</label>
            <input
              id="sm-youtube-id"
              type="text"
              value={smYoutubeId}
              onChange={e => setSmYoutubeId(e.target.value)}
              placeholder="np. dQw4w9WgXcQ lub audio_1234abcd"
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="flex items-center gap-2 mt-2 mb-4">
            <label className="text-sm text-gray-400 whitespace-nowrap">Plik lokalny</label>
            <input
              type="text"
              value={shortLocalPath}
              onChange={e => setShortLocalPath(e.target.value)}
              placeholder="C:\Users\...\video.mp4 (opcjonalny)"
              className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-gray-200 placeholder-gray-500"
            />
            <label className="cursor-pointer bg-gray-700 hover:bg-gray-600 border border-gray-500 rounded px-3 py-1 text-sm text-gray-200 flex items-center gap-1">
              📁 Browse
              <input
                type="file"
                accept="video/*,.mp4,.mov,.mkv,.avi,audio/*,.mp3,.wav,.m4a"
                className="hidden"
                onChange={e => {
                  const file = e.target.files?.[0]
                  if (file) setShortLocalPath(file.name)
                }}
              />
            </label>
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-1">Custom query (opcjonalny)</label>
            <input
              id="sm-custom-query"
              type="text"
              value={smCustomQuery}
              onChange={e => setSmCustomQuery(e.target.value)}
              placeholder="np. najważniejsze wnioski"
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Emotional</label>
              <input id="sm-count-emotional" type="number" min="0" max="5" value={smCountEmotional}
                onChange={e => setSmCountEmotional(Number(e.target.value))}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Professional</label>
              <input id="sm-count-professional" type="number" min="0" max="5" value={smCountProfessional}
                onChange={e => setSmCountProfessional(Number(e.target.value))}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Custom</label>
              <input id="sm-count-custom" type="number" min="0" max="5" value={smCountCustom}
                onChange={e => setSmCountCustom(Number(e.target.value))}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
          </div>
          
          <style>{`@keyframes sm-spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
          <button
            id="sm-get-candidates-btn"
            onClick={handleGetCandidates}
            disabled={smLoading || !smYoutubeId}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 px-4 rounded-lg transition-colors"
          >
            {smLoading ? (
              <>
                <svg style={{display:'inline-block',width:'16px',height:'16px',animation:'sm-spin 0.8s linear infinite',marginRight:'8px',verticalAlign:'middle'}} viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.3)" strokeWidth="3"/>
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="white" strokeWidth="3" strokeLinecap="round"/>
                </svg>
                Analizuję transkrypt AI...
              </>
            ) : '🎯 Analizuj materiał'}
          </button>
        </div>
        
        <div className="flex items-center gap-3 py-2 px-3 bg-gray-800/50 rounded-lg border border-gray-700/50">
          <span className="text-xs text-gray-400">Format renderowania:</span>
          {(['raw', 'short'] as const).map((fmt) => (
            <button
              key={fmt}
              onClick={() => setSmFormat(fmt)}
              className={`px-3 py-1 text-xs rounded border transition-all ${
                smFormat === fmt
                  ? 'bg-violet-600/20 border-violet-500/40 text-violet-400'
                  : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white'
              }`}
            >
              {fmt === 'raw' ? '📼 Raw (szybki cut)' : '✂️ Short (9:16)'}
            </button>
          ))}
          <span className="text-xs text-gray-600 ml-auto">
            {smFormat === 'raw' ? 'ffmpeg -c copy, bez re-encode' : 'Przetwarzanie 9:16 + SRT'}
          </span>
        </div>

        {/* Globalny selektor kanału YT */}
        {ytChannels.length > 0 && !isAudioSource && (
          <div className="flex items-center gap-3 mb-4 px-1">
            <span className="text-xs text-gray-400 whitespace-nowrap">Kanał YT:</span>
            <select
              className="flex-1 bg-gray-800 border border-gray-700 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-violet-500"
              value={smGlobalChannelId}
              onChange={e => setSmGlobalChannelId(e.target.value)}
            >
              {ytChannels.map((ch: any) => (\
                <option key={ch.channel_id} value={ch.channel_id}>
                  {ch.is_default ? '★ ' : ''}{ch.channel_title}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* SRT Package Generator */}
        {smYoutubeId && smCandidates.length > 0 && (
          <div className="bg-gray-800/60 border border-gray-700 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">📄 Pakiet SRT</h3>
                <p className="text-xs text-gray-400 mt-0.5">Pobierz pakiet SRT + rozdziały do montażu w Premiere/DaVinci lub publikacji</p>
              </div>
              <button
                onClick={handleGenerateSrt}
                disabled={srtLoading}
                className="bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors whitespace-nowrap"
              >
                {srtLoading ? '⏳ Generuję...' : '📥 Generuj pakiet SRT'}
              </button>
            </div>
            {srtError && (
              <p className="text-xs text-red-400">{srtError}</p>
            )}
            {srtPackage && (
              <div className="space-y-2">
                <p className="text-xs text-green-400">✅ Pakiet gotowy ({srtPackage.candidate_count} kandydatów)</p>
                <div className="grid grid-cols-1 gap-2">
                  {Object.entries(srtPackage.files as Record<string, {filename: string, content: string, size_bytes: number}>).map(([key, file]) => (
                    <div key={key} className="flex items-center justify-between bg-gray-900 rounded-lg px-3 py-2">
                      <div>
                        <p className="text-xs text-white font-mono">{file.filename}</p>
                        <p className="text-xs text-gray-500">{(file.size_bytes / 1024).toFixed(1)} KB</p>
                      </div>
                      <button
                        onClick={() => downloadSrtFile(file.filename, file.content)}
                        className="text-xs text-violet-400 hover:text-violet-300 border border-violet-500/30 rounded px-2 py-1 transition-colors"
                      >
                        ↓ Pobierz
                      </button>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-500">Przeciągnij <span className="font-mono text-gray-400">shorts_markers.srt</span> na ścieżkę Captions w Premiere → wizualne markery cięć</p>
              </div>
            )}
          </div>
        )}

        {smCandidates.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-lg font-medium text-white">Kandydaci ({smCandidates.length})</h3>
            <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-700">
              <input
                type="checkbox"
                id="selectAllCandidates"
                checked={smCandidates.length > 0 && smSelected.size === smCandidates.length}
                onChange={(e) => {
                  if (e.target.checked) setSmSelected(new Set(smCandidates.map((_: any, idx: number) => idx)))
                  else setSmSelected(new Set())
                }}
                style={{cursor:'pointer',accentColor:'#3b82f6'}}
              />
              <label htmlFor="selectAllCandidates" className="text-xs text-gray-400 cursor-pointer">
                Zaznacz wszystkie ({smCandidates.length})
              </label>
            </div>
            {smCandidates.map((c, i) => (
              <div key={i} className="bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <input type="checkbox" checked={smSelected.has(i)} onChange={() => toggleSmSelected(i)} style={{cursor:'pointer',accentColor:'#3b82f6'}} />
                    <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                      c.type === 'emotional' ? 'bg-red-900 text-red-300' :
                      c.type === 'professional' ? 'bg-blue-900 text-blue-300' :
                      'bg-purple-900 text-purple-300'
                    }`}>{c.type}</span>
                    <span className="text-sm text-gray-400">
                      {Math.floor(c.start_sec / 60)}:{String(Math.floor(c.start_sec % 60)).padStart(2,'0')} - 
                      {Math.floor(c.end_sec / 60)}:{String(Math.floor(c.end_sec % 60)).padStart(2,'0')}
                      &nbsp;({c.duration_sec}s)
                    </span>
                  </div>
                  <div style={{display:'flex', gap:'8px', alignItems:'center'}}>
                    <span className="text-yellow-400 text-sm">
                      {'★'.repeat(Math.round(c.score * 5))}{'☆'.repeat(5 - Math.round(c.score * 5))}
                    </span>
                    <button onClick={() => setSmExpandedIdx(smExpandedIdx === i ? null : i)} style={{padding:'2px 8px',fontSize:'11px',background: smExpandedIdx===i ? '#1e40af' : '#1e293b',border:'1px solid '+(smExpandedIdx===i?'#3b82f6':'#334155'),borderRadius:'4px',color: smExpandedIdx===i?'#93c5fd':'#94a3b8',cursor:'pointer'}}>
                      {smExpandedIdx === i ? '▲ Transkrypt' : '✏ Transkrypt'}
                    </button>
                  </div>
                </div>
                
                <div className="text-sm space-y-1">
                  <p><span className="text-gray-400">Hook:</span> <span className="text-white">{c.hook_text}</span></p>
                  <p><span className="text-gray-400">Puenta:</span> <span className="text-white">{c.punchline_text}</span></p>
                  {c.query_match && (
                    <p><span className="text-gray-400">Match:</span> <span className="text-green-400">{c.query_match}</span></p>
                  )}
                </div>
                
                {smExpandedIdx === i && (
                  <div style={{marginBottom:'12px',border:'1px solid #334155',borderRadius:'8px',overflow:'hidden',background:'#0f172a'}}>
                    {isAudioSource ? (
                      <div className="bg-gray-800/50 rounded-xl p-6 text-center text-gray-400 m-3 border border-gray-700/50">
                        <span className="text-3xl block mb-2">🎤</span>
                        <p className="font-medium text-gray-200 text-sm">Analiza oparta na transkrypcji audio</p>
                        <p className="text-xs text-gray-400 mt-1">Timing i kandydaci shortów wyliczone z Whisper — brak podglądu wideo</p>
                      </div>
                    ) : (() => {
                      const ytMatch = (c.youtube_url||'').match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/)
                      const ytId = ytMatch ? ytMatch[1] : null
                      const adjStart = getAdj(i, c).start
                      return ytId ? (
                        <div style={{position:'relative',paddingBottom:'56.25%',height:0,overflow:'hidden'}}>
                          <iframe key={`yt-${i}-${Math.floor(adjStart)}`} src={`https://www.youtube.com/embed/${ytId}?start=${Math.floor(adjStart)}&autoplay=0&rel=0`} style={{position:'absolute',top:0,left:0,width:'100%',height:'100%',border:'none'}} allowFullScreen />
                        </div>
                      ) : <div style={{padding:'8px',color:'#64748b',fontSize:'12px'}}>Brak YouTube URL dla podglądu</div>
                    })()}
                    <div style={{maxHeight:'220px',overflowY:'auto',padding:'8px'}}>
                      <div style={{display:'flex',gap:'6px',marginBottom:'8px',alignItems:'center'}}>
                        <span style={{fontSize:'11px',color:'#94a3b8'}}>Klik ustawia:</span>
                        <button onClick={()=>setSmTrimMode('start')} style={{padding:'2px 8px',fontSize:'11px',borderRadius:'4px',border:'none',cursor:'pointer',background:smTrimMode==='start'?'#3b82f6':'#1e293b',color:smTrimMode==='start'?'#fff':'#94a3b8'}}>◀ Start</button>
                        <button onClick={()=>setSmTrimMode('end')} style={{padding:'2px 8px',fontSize:'11px',borderRadius:'4px',border:'none',cursor:'pointer',background:smTrimMode==='end'?'#f59e0b':'#1e293b',color:smTrimMode==='end'?'#fff':'#94a3b8'}}>Koniec ▶</button>
                        <span style={{marginLeft:'auto',fontSize:'11px',color:'#64748b'}}>{(c.vtt_segments||[]).length} segmentów</span>
                      </div>
                      {(c.vtt_segments||[]).map((seg: any, si: number) => {
                        const adj = getAdj(i, c)
                        const isInRange = seg.ts >= adj.start && seg.ts <= adj.end
                        return (
                          <div key={si} onClick={() => { if (smTrimMode === 'start') { setSmTrimAdj((p: any) => ({...p, [i]: {startDelta: seg.ts - (c.start_sec??0), endDelta: p[i]?.endDelta??0}})); } else { setSmTrimAdj((p: any) => ({...p, [i]: {startDelta: p[i]?.startDelta??0, endDelta: seg.ts - (c.end_sec??0) + 2}})); } }} style={{padding:'4px 8px',marginBottom:'2px',borderRadius:'4px',cursor:'pointer',fontSize:'12px',lineHeight:'1.4',background: isInRange ? 'rgba(59,130,246,0.15)' : 'transparent',borderLeft: isInRange ? '3px solid #3b82f6' : '3px solid transparent',color: isInRange ? '#e2e8f0' : '#64748b',transition: 'background 0.1s'}}>
                            <span style={{color:'#475569',marginRight:'8px',fontFamily:'monospace',fontSize:'11px'}}>{seg.time_str}</span>
                            {seg.text}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                <div className="space-y-1 mb-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={smTitles[i] || ''}
                      onChange={e => setSmTitles(p => ({...p, [i]: e.target.value}))}
                      placeholder="Tytuł shorta..."
                      className="flex-1 bg-gray-900 border border-gray-600 rounded px-2 py-1 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500"
                    />
                    {(smTrimAdj[i]?.startDelta || smTrimAdj[i]?.endDelta) && (
                      <button
                        onClick={() => handleRegenerateTitle(i, c)}
                        disabled={smTitleLoading[i]}
                        className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 border border-gray-600 rounded text-gray-300 disabled:opacity-50"
                        title="Odśwież tytuł i tagi na podstawie nowego zakresu"
                      >
                        {smTitleLoading[i] ? '...' : '🔄'}
                      </button>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {(smTags[i] || []).map((tag, ti) => (
                      <span key={ti} className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-700 border border-gray-600 rounded-full text-xs text-gray-300">
                        {tag}
                        <button onClick={() => setSmTags(p => ({...p, [i]: (p[i]||[]).filter((_,j)=>j!==ti)}))} className="text-gray-500 hover:text-red-400 leading-none">×</button>
                      </span>
                    ))}
                  </div>
                </div>

                {!isAudioSource && (
                  <div className="mb-2">
                    <button
                      onClick={() => {
                        if (smPreviewIdx === i) {
                          setSmPreviewIdx(null)
                          if (ytIntervalRef.current) clearInterval(ytIntervalRef.current)
                          return
                        }
                        setSmPreviewIdx(i)
                        const adj2 = getAdj(i, c)
                        const videoId2 = smYoutubeId.length === 11 ? smYoutubeId : smYoutubeId.match(/[a-zA-Z0-9_-]{11}/)?.[0] || ''
                        setTimeout(() => {
                          if (!(window as any).YT?.Player) return
                          if (ytPlayerRef.current?.destroy) ytPlayerRef.current.destroy()
                          if (ytIntervalRef.current) clearInterval(ytIntervalRef.current)
                          ytPlayerRef.current = new (window as any).YT.Player(`yt-preview-${i}`, {
                            height: '100%',
                            width: '100%',
                            videoId: videoId2,
                            playerVars: { start: Math.floor(adj2.start), autoplay: 1, rel: 0, modestbranding: 1 },
                            events: {
                              onReady: (e: any) => {
                                e.target.seekTo(adj2.start, true)
                                e.target.playVideo()
                                ytIntervalRef.current = setInterval(() => {
                                  const t = e.target.getCurrentTime()
                                  if (t >= adj2.end) {
                                    e.target.pauseVideo()
                                    clearInterval(ytIntervalRef.current)
                                  }
                                }, 250)
                              }
                            }
                          })
                        }, 100)
                      }}
                      className="text-xs text-blue-400 hover:text-blue-300 underline cursor-pointer"
                    >
                      {smPreviewIdx === i ? '▼ Zamknij podgląd' : '▶ Podgląd'}
                    </button>

                    {smPreviewIdx === i && (
                      <div className="mt-2 rounded-lg overflow-hidden w-full max-w-2xl border border-gray-700 bg-black">
                        <div className="relative w-full aspect-video min-h-[220px] sm:min-h-[315px]">
                          <div id={`yt-preview-${i}`} className="w-full h-full" />
                        </div>
                        <div className="text-xs text-gray-400 px-3 py-1.5 bg-gray-900 border-t border-gray-800 flex items-center justify-between">
                          <span>Zakres: {fmtSec(getAdj(i,c).start)} → {fmtSec(getAdj(i,c).end)}</span>
                          <span>{Math.round(getAdj(i,c).end-getAdj(i,c).start)}s</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div style={{display:'flex',alignItems:'center',gap:'6px',flexWrap:'wrap',marginBottom:'8px',fontSize:'12px',color:'#888'}}>
                  <span>✂ Start:</span>
                  {([-5,-2,-1] as number[]).map(d=>(\
                    <button key={d} onClick={()=>setSmTrimAdj(p=>({...p,[i]:{startDelta:(p[i]?.startDelta??0)+d,endDelta:p[i]?.endDelta??0}}))} style={{padding:'1px 5px',fontSize:'11px',background:'#1e293b',border:'1px solid #334155',borderRadius:'3px',color:'#94a3b8',cursor:'pointer'}}>{d}s</button>
                  ))}
                  <span style={{color:'#e2e8f0',minWidth:'36px',textAlign:'center'}}>{fmtSec(getAdj(i,c).start)}</span>
                  {([1,2,5] as number[]).map(d=>(\
                    <button key={d} onClick={()=>setSmTrimAdj(p=>({...p,[i]:{startDelta:(p[i]?.startDelta??0)+d,endDelta:p[i]?.endDelta??0}}))} style={{padding:'1px 5px',fontSize:'11px',background:'#1e293b',border:'1px solid #334155',borderRadius:'3px',color:'#94a3b8',cursor:'pointer'}}>+{d}s</button>
                  ))}
                  <span style={{marginLeft:'8px'}}>Koniec:</span>
                  {([-5,-2,-1] as number[]).map(d=>(\
                    <button key={d} onClick={()=>setSmTrimAdj(p=>({...p,[i]:{startDelta:p[i]?.startDelta??0,endDelta:(p[i]?.endDelta??0)+d}}))} style={{padding:'1px 5px',fontSize:'11px',background:'#1e293b',border:'1px solid #334155',borderRadius:'3px',color:'#94a3b8',cursor:'pointer'}}>{d}s</button>
                  ))}
                  <span style={{color:'#e2e8f0',minWidth:'36px',textAlign:'center'}}>{fmtSec(getAdj(i,c).end)}</span>
                  {([1,2,5] as number[]).map(d=>(\
                    <button key={d} onClick={()=>setSmTrimAdj(p=>({...p,[i]:{startDelta:p[i]?.startDelta??0,endDelta:(p[i]?.endDelta??0)+d}}))} style={{padding:'1px 5px',fontSize:'11px',background:'#1e293b',border:'1px solid #334155',borderRadius:'3px',color:'#94a3b8',cursor:'pointer'}}>+{d}s</button>
                  ))}
                  <span style={{marginLeft:'6px',color:'#64748b'}}>{Math.round(getAdj(i,c).end-getAdj(i,c).start)}s</span>
                  {(smTrimAdj[i]?.startDelta||smTrimAdj[i]?.endDelta)?<button onClick={()=>setSmTrimAdj(p=>({...p,[i]:{startDelta:0,endDelta:0}}))} style={{padding:'1px 5px',fontSize:'10px',background:'transparent',border:'1px solid #475569',borderRadius:'3px',color:'#64748b',cursor:'pointer',marginLeft:'auto'}}>↺</button>:null}
                </div>

                <div className="grid grid-cols-3 gap-2 pt-2 border-t border-gray-700">
                  <select
                    value={smRenderConfig[i]?.format || '9:16'}
                    onChange={e => setSmRenderConfig(prev => ({...prev, [i]: {...(prev[i]||{}), format: e.target.value}}))}
                    className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-xs"
                  >
                    <option value="9:16">9:16 (Shorts)</option>
                    <option value="16:9">16:9 (YT)</option>
                  </select>
                  <select
                    value={smRenderConfig[i]?.subtitles || 'srt'}
                    onChange={e => setSmRenderConfig(prev => ({...prev, [i]: {...(prev[i]||{}), subtitles: e.target.value}}))}
                    className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-xs"
                  >
                    <option value="none">Bez napisów</option>
                    <option value="srt">Export SRT</option>
                  </select>
                  <button
                    id={`sm-render-btn-${i}`}
                    onClick={() => { const a = getAdj(i, c); handleRenderShort({ ...c, start_sec: a.start, end_sec: a.end }, i); }}
                    className="bg-green-700 hover:bg-green-600 text-white text-xs font-medium px-3 py-1 rounded transition-colors"
                  >
                    ▶ Renderuj
                  </button>
                </div>
                
                {smJobStatus[i] && (
                  <div className={`text-xs px-2 py-1 rounded ${
                    smJobStatus[i].status === 'done' ? 'bg-green-900 text-green-300' :
                    smJobStatus[i].status === 'error' ? 'bg-red-900 text-red-300' :
                    'bg-yellow-900 text-yellow-300'
                  }`}>
                    {smJobStatus[i].status === 'done' ? (
                      <div className="flex flex-col gap-1">
                        <span>Gotowe: {smJobStatus[i].result_paths?.raw || 'plik zapisany'}</span>
                        {smJobStatus[i].result_paths?.raw && (
                          <button
                            onClick={() => {
                              const rawPath = smJobStatus[i].result_paths?.raw || ''
                              const folderPath = rawPath.includes('\\') || rawPath.includes('/')
                                ? rawPath.substring(0, Math.max(rawPath.lastIndexOf('\\'), rawPath.lastIndexOf('/')))
                                : rawPath
                              navigator.clipboard.writeText(folderPath).then(() => {})
                            }}
                            className="mt-1 text-xs text-violet-400 hover:text-violet-300 border border-violet-500/30 rounded px-2 py-0.5 transition-colors self-start"
                            title="Kopiuj ścieżkę folderu do schowka"
                          >
                            📋 Kopiuj ścieżkę folderu
                          </button>
                        )}
                      </div>
                    ) : smJobStatus[i].status === 'error' ? (
                      <span>Błąd: {smJobStatus[i].error}</span>
                    ) : (
                      <span>Przetwarzam... ({smJobStatus[i].status})</span>
                    )}
                  </div>
                )}
                
                {/* YouTube Inject Block */}
                {!isAudioSource && (
                  <div className="border-t border-gray-600 pt-3 mt-1">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">► Wstrzyknij metadane na YouTube</p>
                    {ytChannels.length > 1 && (
                      <select
                        className="w-full bg-gray-700 text-white text-xs rounded px-2 py-1 border border-gray-600 mb-2 focus:outline-none focus:border-blue-500"
                        value={smChannelOverride[i] ?? ''}
                        onChange={e => {
                          const val = e.target.value
                          setSmChannelOverride(prev => ({...prev, [i]: val}))
                          const targetCh = val || smGlobalChannelId
                          if (targetCh && !smPlaylistsByChannel[targetCh]) {
                            fetchPlaylistsForChannel(targetCh)
                          }
                        }}
                      >
                        <option value="">🌐 {ytChannels.find((ch: any) => ch.channel_id === smGlobalChannelId)?.channel_title || 'Kanał globalny'}</option>
                        {ytChannels.filter((ch: any) => ch.channel_id !== smGlobalChannelId).map((ch: any) => (\
                          <option key={ch.channel_id} value={ch.channel_id}>{ch.channel_title}</option>
                        ))}
                      </select>
                    )}
                    <input
                      type="text"
                      placeholder="URL lub ID YouTube (wgrany z Premiere Pro)"
                      className="w-full bg-gray-700 text-white text-sm rounded px-3 py-2 border border-gray-600 focus:border-blue-500 focus:outline-none mb-2"
                      value={smTargetYtId[i] || ''}
                      onChange={e => setSmTargetYtId(prev => ({...prev, [i]: e.target.value}))}
                    />
                    <div className="grid grid-cols-3 gap-2 mb-2">
                      {(() => {
                        const candidateChannelId = smChannelOverride[i] || smGlobalChannelId || ytChannels[0]?.channel_id
                        const channelPlaylistsList = (candidateChannelId ? smPlaylistsByChannel[candidateChannelId] : null) || smPlaylists || []
                        return (
                          <select
                            className="bg-gray-700 text-white text-sm rounded px-2 py-2 border border-gray-600 focus:outline-none focus:border-blue-500"
                            value={smSelectedPlaylist[i] || ''}
                            onChange={e => setSmSelectedPlaylist(prev => ({...prev, [i]: e.target.value}))}
                          >
                            <option value="">
                              {playlistsLoading && channelPlaylistsList.length === 0 ? 'Ładowanie playlist...' : 'Playlista (opcj.)'}
                            </option>
                            {channelPlaylistsList.map(pl => <option key={pl.id} value={pl.id}>{pl.title}</option>)}
                          </select>
                        )
                      })()}
                      <input
                        type="datetime-local"
                        className="bg-gray-700 text-white text-sm rounded px-2 py-2 border border-gray-600"
                        value={smPublishAt[i] || ''}
                        onChange={e => setSmPublishAt(prev => ({...prev, [i]: e.target.value}))}
                      />
                      <select
                        className="bg-gray-700 text-white text-sm rounded px-2 py-2 border border-gray-600"
                        value={smPrivacyStatus[i] || 'private'}
                        onChange={e => setSmPrivacyStatus(prev => ({...prev, [i]: e.target.value}))}
                      >
                        <option value="private">Prywatny</option>
                        <option value="unlisted">Niepubliczny</option>
                        <option value="public">Publiczny</option>
                      </select>
                    </div>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => setSmModalOpenFor(i)}
                        disabled={!smTargetYtId[i]}
                        className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded transition-colors"
                      >
                        ► Podgląd i publikacja
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {smSelected.size > 0 && (
              <div style={{position:'sticky',bottom:'8px',textAlign:'center',marginTop:'8px',zIndex:10}}>
                <button onClick={() => { smSelected.forEach((selIdx: number) => { const c = smCandidates[selIdx]; const a = getAdj(selIdx, c); handleRenderShort({...c, start_sec: a.start, end_sec: a.end}, selIdx); }); setSmSelected(new Set()); }} style={{padding:'10px 24px',background:'linear-gradient(135deg,#059669,#10b981)',border:'none',borderRadius:'8px',color:'#fff',fontWeight:'600',fontSize:'14px',cursor:'pointer',boxShadow:'0 4px 12px rgba(16,185,129,0.3)'}}>
                  ► Renderuj zaznaczone ({smSelected.size})
                </button>
              </div>
            )}
          </div>
        )}
        
        {smError && (
          <div className="bg-red-900 border border-red-700 text-red-300 rounded-lg p-3 text-sm">
            {smError}
          </div>
        )}
      </div>

      {/* ShortMachine YouTube Inject Modal */}
      {smModalOpenFor !== null && smCandidates[smModalOpenFor] && (() => {
        const i = smModalOpenFor
        const c = smCandidates[i]
        const hookTxt = c.hook_text || c.hook || ''
        const bodySum = c.body_summary || ''
        const punchTxt = c.punchline_text || c.puenta || ''
        const combinedBody = [hookTxt, bodySum, punchTxt].filter(Boolean).join('\n\n')

        const smSchemaData = {
          youtube_description_body: combinedBody,
          youtube_description_hook: combinedBody || smTitles[i] || c.suggested_title || c.title || '',
          youtube_hashtags: smTags[i] || c.tags || [],
          yt_title: smTitles[i] || c.suggested_title || c.title || ''
        }
        const rawInput = smTargetYtId[i] || ''
        const smVideoId = rawInput.match(/(?:v=|youtu\.be\/|\/shorts\/)([A-Za-z0-9_-]{11})/)?.[1] || rawInput

        return (
          <YouTubePublishModal
            isOpen={true}
            onClose={() => setSmModalOpenFor(null)}
            videoId={smVideoId}
            schemaData={smSchemaData}
            wpUrl=""
            channels={(smChannelOverride[i] || smGlobalChannelId) ? [ytChannels.find((ch: any) => ch.channel_id === (smChannelOverride[i] || smGlobalChannelId)) ?? ytChannels[0]].filter(Boolean) : ytChannels}
            accessToken={accessToken || ""}
            apiUrl={process.env.NEXT_PUBLIC_API_URL || ''}
            publishAt={smPublishAt[i]}
            privacyStatus={smPrivacyStatus[i]}
            playlistId={smSelectedPlaylist[i]}
          />
        )
      })()}
    </>
  )
}

export default ShortMachineTab
