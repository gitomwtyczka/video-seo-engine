"use client";

import { useState, useEffect } from "react";



interface Channel { channel_id: string; channel_title: string; footer_text?: string; }



interface Props {

  isOpen: boolean;

  onClose: () => void;

  videoId: string;

  schemaData: any;

  wpUrl: string;

  channels: Channel[];

  accessToken: string;

  apiUrl: string;

  publishAt?: string;

  privacyStatus?: string;

  playlistId?: string;

}

export function YouTubePublishModal({ isOpen, onClose, videoId, schemaData, wpUrl, channels, accessToken, apiUrl, publishAt, privacyStatus, playlistId }: Props) {

  const [selected, setSelected] = useState<string[]>([])

  useEffect(() => {
    if (channels.length === 1 && selected.length === 0) {
      setSelected([channels[0].channel_id])
    }
  }, [channels]);

  const [status, setStatus] = useState<"idle"|"loading"|"done"|"error">("idle");

  const [result, setResult] = useState<Record<string,string>>({});

  

  const [previewText, setPreviewText] = useState<string>('');

  const [showPreview, setShowPreview] = useState<boolean>(false);



  if (!isOpen) return null;



  const toggle = (id: string) => setSelected(p => p.includes(id) ? p.filter(c=>c!==id) : [...p,id]);



  const buildPreview = (): string => {
    const parts: string[] = []

    // M1 body
    const body = schemaData?.youtube_description_body ?? schemaData?.youtube_description_hook ?? schemaData?.video_description ?? '';
    if (body) parts.push(body as string);

    // M2 link do artykułu
    if (wpUrl) {
      parts.push(`🔗 Artykuł: ${wpUrl}`)
    } else {
      parts.push('🔗 Artykuł: [WSTAW LINK]')
    }

    // M3 mid CTA
    if (schemaData?.youtube_mid_cta) {
      parts.push(schemaData.youtube_mid_cta)
    }

    // M4 rozdziały — ZAWSZE formatuj jako string, nigdy nie pushuj array!
    const rawChapters = schemaData?.chapters
    if (Array.isArray(rawChapters) && rawChapters.length > 0) {
      const lines = rawChapters.map((c: any) => {
        const sec = c.time ?? c.startOffset ?? 0
        const m = Math.floor(sec / 60).toString().padStart(2, '0')
        const s = Math.floor(sec % 60).toString().padStart(2, '0')
        const title = c.label ?? c.name ?? ''
        return `${m}:${s} ${title}`.trim()
      })
      parts.push('ROZDZIAŁY:\n' + lines.join('\n'))
    }

    // M5 credits
    if (schemaData?.youtube_credits) {
      parts.push(schemaData.youtube_credits)
    }

    // M7 stopka kanału (jeśli dostępna na wybranym kanale)
    const firstChannel = channels.find(ch => selected.includes(ch.channel_id))
    if (firstChannel?.footer_text) {
      parts.push(firstChannel.footer_text)
    }

    // M8 hashtagi — array → join w string
    const hashtags = schemaData?.youtube_hashtags
    if (hashtags) {
      if (Array.isArray(hashtags)) {
        const tags = hashtags
          .map((t: string) => t.startsWith('#') ? t : `#${t}`)
          .join(',')  // bez spacji, YouTube preferuje przecinki
        if (tags) parts.push(tags)
      } else if (typeof hashtags === 'string') {
        parts.push(hashtags)
      }
    }

    return parts.join('\n\n')
  }

  useEffect(() => {
    if (showPreview) {
      setPreviewText(buildPreview())
    }
  }, [selected, schemaData, wpUrl])
  const handlePreviewClick = () => {

    setPreviewText(buildPreview())

    setShowPreview(true)

  }



  const publish = async () => {

    if (!selected.length) return;

    setStatus("loading");

    console.log('[YT-DEBUG] videoId:', videoId, 'schemaData keys:', Object.keys(schemaData).length);

    try {

      const bodyPayload: any = { channel_ids: selected, video_id: videoId, schema_data: schemaData, wp_article_url: wpUrl }

      if (showPreview && previewText) {

        bodyPayload.override_description = previewText

      }

      if (publishAt) bodyPayload.publish_at = new Date(publishAt).toISOString();

      if (privacyStatus) bodyPayload.privacy_status = privacyStatus;

      if (playlistId) bodyPayload.playlist_id = playlistId;

      

      const res = await fetch(`${apiUrl}/v1/youtube/publish-description`, {

        method: "POST",

        headers: { "Content-Type": "application/json", ...(accessToken && { Authorization: `Bearer ${accessToken}` }) },

        body: JSON.stringify(bodyPayload),

      });

      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Błąd");

      setResult(data.results || {});

      setStatus("done");

    } catch (e: any) { setResult({ error: e.message }); setStatus("error"); }

  };



  return (

    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.7)",zIndex:50,display:"flex",alignItems:"center",justifyContent:"center"}}>

      <div style={{background:"#1a1a2e",borderRadius:12,padding:24,width: showPreview ? 600 : 420, maxWidth:"90vw", maxHeight:"90vh", overflowY:"auto"}}>

        <h3 style={{marginBottom:8}}>Wyślij opis na YouTube</h3>

        <p style={{fontSize:12,opacity:0.5,marginBottom:16}}>Video: {videoId}</p>

        

        {!showPreview && channels && channels.length > 0 ? channels.map(ch => (

          <label key={ch.channel_id} style={{display:"flex",gap:8,alignItems:"center",marginBottom:8,cursor:"pointer"}}>

            <input type="checkbox" checked={selected.includes(ch.channel_id)} onChange={()=>toggle(ch.channel_id)} />

            {ch.channel_title}

          </label>

        )) : !showPreview && (

          <div style={{color:"#f59e0b",marginBottom:16,fontSize:14}}>

            ⚠️ Brak podłączonych kanałów. <a href="/ustawienia" style={{textDecoration:"underline",color:"#f59e0b"}}>Przejdź do ustawień</a>

          </div>

        )}

        

        {showPreview && (

          <div style={{marginBottom:16}}>

            <label style={{display:"block",fontSize:12,color:"#9ca3af",marginBottom:6}}>

              Podgląd opisu YouTube <span style={{color:"#6b7280"}}>(edytowalny)</span>

            </label>

            <textarea

              value={previewText}

              onChange={(e) => setPreviewText(e.target.value)}

              rows={12}

              style={{width:"100%",background:"#1f2937",border:"1px solid #374151",borderRadius:8,padding:"8px 12px",fontSize:12,color:"#d1d5db",fontFamily:"monospace",outline:"none",resize:"vertical"}}

              placeholder="Edytuj opis przed wysłaniem..."

            />

          </div>

        )}



        {status==="done" && (
          <div style={{marginBottom:8}}>
            {Object.entries(result).map(([k,v]) => {
              const isError = String(v).toLowerCase().includes('error') || String(k).toLowerCase().includes('error');
              const isWarning = String(v).toLowerCase().includes('warning');
              const color = isError ? '#f87171' : isWarning ? '#fbbf24' : '#4ade80';
              return <div key={k} style={{color, fontSize: 13, marginBottom: 4}}>{k}: {v}</div>;
            })}
          </div>
        )}

        {status==="error" && <div style={{color:"#f87171",marginBottom:8}}>Błąd: {result.error}</div>}

        

        <div style={{display:"flex",gap:8,justifyContent:"flex-end",marginTop:16}}>

          <button onClick={onClose}>Anuluj</button>

          

          {!showPreview ? (

            <button onClick={handlePreviewClick} disabled={!selected.length}

              style={{background:"#7c3aed",color:"white",padding:"8px 16px",borderRadius:6}}>

              Podgląd opisu

            </button>

          ) : (

            <button onClick={publish} disabled={status==="loading"||!selected.length}

              style={{background:"#7c3aed",color:"white",padding:"8px 16px",borderRadius:6}}>

              {status==="loading" ? "Wysyłam..." : "Wyślij na YouTube"}

            </button>

          )}

        </div>

      </div>

    </div>

  );

}
