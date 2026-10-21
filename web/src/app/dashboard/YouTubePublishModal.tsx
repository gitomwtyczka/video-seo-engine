"use client";

import { useState, useEffect } from "react";

interface Channel {
  channel_id: string;
  channel_title: string;
  footer_text?: string;
}

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
  overrideDescription?: string;
}

export function YouTubePublishModal({
  isOpen,
  onClose,
  videoId,
  schemaData,
  wpUrl,
  channels,
  accessToken,
  apiUrl,
  publishAt,
  privacyStatus,
  playlistId,
  overrideDescription,
}: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [result, setResult] = useState<Record<string, string>>({});
  const [previewText, setPreviewText] = useState<string>(overrideDescription || '');
  const [showPreview, setShowPreview] = useState<boolean>(!!overrideDescription);

  // Preselekcja kanału właściciela wideo
  const videoOwnerChannelId = schemaData?.channel_id || schemaData?.youtube_channel_id || schemaData?.video_channel_id || '';

  useEffect(() => {
    if (selected.length === 0 && channels && channels.length > 0) {
      if (videoOwnerChannelId) {
        const ownerMatch = channels.find(c => c.channel_id === videoOwnerChannelId);
        if (ownerMatch) {
          setSelected([ownerMatch.channel_id]);
          return;
        }
      }
      if (channels.length === 1) {
        setSelected([channels[0].channel_id]);
      }
      // Jeśli kanałów > 1 i brak dopasowania właściciela: NIE zaznaczaj losowo, czekaj na wybór użytkownika
    }
  }, [channels, videoOwnerChannelId]);

  useEffect(() => {
    if (overrideDescription) {
      setPreviewText(overrideDescription);
      setShowPreview(true);
    }
  }, [overrideDescription]);

  if (!isOpen) return null;

  const toggle = (id: string) => setSelected(p => p.includes(id) ? p.filter(c => c !== id) : [...p, id]);

  const buildPreview = (): string => {
    const parts: string[] = [];

    // M1 body
    const body = schemaData?.youtube_description_body ?? schemaData?.youtube_description_hook ?? schemaData?.video_description ?? '';
    if (body) parts.push(body as string);

    // M2 link do artykułu
    if (wpUrl) {
      parts.push(`🔗 Artykuł: ${wpUrl}`);
    } else {
      parts.push('🔗 Artykuł: [WSTAW LINK]');
    }

    // M3 mid CTA
    if (schemaData?.youtube_mid_cta) {
      parts.push(schemaData.youtube_mid_cta);
    }

    // M4 rozdziały — formatuj jako string
    const rawChapters = schemaData?.chapters;
    if (Array.isArray(rawChapters) && rawChapters.length > 0) {
      const lines = rawChapters.map((c: any) => {
        const sec = c.time ?? c.startOffset ?? 0;
        const m = Math.floor(sec / 60).toString().padStart(2, '0');
        const s = Math.floor(sec % 60).toString().padStart(2, '0');
        const title = c.label ?? c.name ?? '';
        return `${m}:${s} ${title}`.trim();
      });
      parts.push('ROZDZIAŁY:\n' + lines.join('\n'));
    }

    // M5 credits
    if (schemaData?.youtube_credits) {
      parts.push(schemaData.youtube_credits);
    }

    // M7 stopka kanału (jeśli dostępna na wybranym kanale)
    const firstChannel = channels.find(ch => selected.includes(ch.channel_id));
    if (firstChannel?.footer_text) {
      parts.push(firstChannel.footer_text);
    }

    // M8 hashtagi — array → join w string
    const hashtags = schemaData?.youtube_hashtags;
    if (hashtags) {
      if (Array.isArray(hashtags)) {
        const tags = hashtags
          .map((t: string) => t.startsWith('#') ? t : `#${t}`)
          .join(',');
        if (tags) parts.push(tags);
      } else if (typeof hashtags === 'string') {
        parts.push(hashtags);
      }
    }

    return parts.join('\n\n');
  };

  useEffect(() => {
    if (showPreview && !overrideDescription) {
      setPreviewText(buildPreview());
    }
  }, [selected, schemaData, wpUrl, overrideDescription]);

  const handlePreviewClick = () => {
    if (!previewText) {
      setPreviewText(overrideDescription || buildPreview());
    }
    setShowPreview(true);
  };

  const publish = async () => {
    if (!selected.length) return;
    setStatus("loading");
    setResult({});
    try {
      const bodyPayload: any = { channel_ids: selected, video_id: videoId, schema_data: schemaData, wp_article_url: wpUrl };
      const finalDesc = (showPreview && previewText) ? previewText : (overrideDescription || (previewText || undefined));
      if (finalDesc) {
        bodyPayload.override_description = finalDesc;
      }

      if (publishAt) bodyPayload.publish_at = new Date(publishAt).toISOString();
      if (privacyStatus) bodyPayload.privacy_status = privacyStatus;
      if (playlistId) bodyPayload.playlist_id = playlistId;

      const res = await fetch(`${apiUrl}/v1/youtube/publish-description`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(accessToken && { Authorization: `Bearer ${accessToken}` }) },
        body: JSON.stringify(bodyPayload),
      });

      let data: any = {};
      try {
        data = await res.json();
      } catch {
        data = { error: `Błąd serwera (HTTP ${res.status})` };
      }

      if (!res.ok) {
        throw new Error(data.detail || data.error || `Błąd serwera HTTP ${res.status}`);
      }

      const resMap = data.results || {};
      setResult(resMap);

      const hasErrors = Object.values(resMap).some((v: any) => String(v).toLowerCase().includes('error'));
      setStatus(hasErrors ? "error" : "done");
    } catch (e: any) {
      setResult({ error: e.message || 'Błąd połączenia z API' });
      setStatus("error");
    }
  };

  const hasOwnerChannelMatch = videoOwnerChannelId && channels.some(c => c.channel_id === videoOwnerChannelId);

  return (
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.7)",zIndex:50,display:"flex",alignItems:"center",justifyContent:"center"}}>
      <div style={{background:"#1a1a2e",borderRadius:12,padding:24,width: showPreview ? 640 : 440, maxWidth:"90vw", maxHeight:"90vh", overflowY:"auto"}}>
        <h3 style={{marginBottom:8, fontSize: 18, fontWeight: "bold", color: "#fff"}}>Wyślij opis na YouTube</h3>
        <p style={{fontSize:12,opacity:0.6,marginBottom:16}}>Video ID: <span style={{fontFamily:"monospace"}}>{videoId}</span></p>

        {/* Lista kanałów — ZAWSZE widoczna */}
        <div style={{marginBottom: 16, padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: 8, border: "1px solid #374151"}}>
          <label style={{display: "block", fontSize: 12, fontWeight: 600, color: "#9ca3af", marginBottom: 8}}>
            Docelowy kanał YouTube:
          </label>
          {channels && channels.length > 0 ? (
            <div style={{display: "flex", flexDirection: "column", gap: 6}}>
              {channels.map(ch => {
                const isOwner = videoOwnerChannelId && ch.channel_id === videoOwnerChannelId;
                return (
                  <label key={ch.channel_id} style={{display:"flex",gap:8,alignItems:"center",cursor:"pointer",fontSize:13,color:"#e5e7eb"}}>
                    <input type="checkbox" checked={selected.includes(ch.channel_id)} onChange={()=>toggle(ch.channel_id)} />
                    <span>{ch.channel_title}</span>
                    {isOwner && (
                      <span style={{fontSize: 10, background: "rgba(16,185,129,0.2)", color: "#34d399", padding: "1px 6px", borderRadius: 4, border: "1px solid rgba(16,185,129,0.3)"}}>
                        Właściciel wideo
                      </span>
                    )}
                  </label>
                );
              })}
            </div>
          ) : (
            <div style={{color:"#f59e0b",fontSize:13}}>
              ⚠️ Brak podłączonych kanałów YouTube. <a href="/ustawienia" target="_blank" rel="noreferrer" style={{textDecoration:"underline",color:"#f59e0b"}}>Przejdź do ustawień</a>
            </div>
          )}

          {/* Ostrzeżenie gdy brak zaznaczenia */}
          {channels && channels.length > 1 && selected.length === 0 && (
            <div style={{marginTop: 8, color: "#f59e0b", fontSize: 12, display: "flex", alignItems: "center", gap: 6}}>
              <span>⚠️</span>
              <span>Wybierz kanał powyżej, aby móc wysłać opis na YouTube.</span>
            </div>
          )}
          {videoOwnerChannelId && !hasOwnerChannelMatch && channels.length > 0 && (
            <div style={{marginTop: 8, color: "#9ca3af", fontSize: 11}}>
              ℹ️ Wideo należy do kanału <span style={{fontFamily: "monospace"}}>{videoOwnerChannelId}</span>. Upewnij się, że wybrany kanał ma uprawnienia do edycji tego filmu.
            </div>
          )}
        </div>

        {/* Podgląd opisu */}
        {showPreview && (
          <div style={{marginBottom:16}}>
            <label style={{display:"block",fontSize:12,color:"#9ca3af",marginBottom:6}}>
              Podgląd opisu YouTube <span style={{color:"#6b7280"}}>(edytowalny)</span>
            </label>
            <textarea
              value={previewText}
              onChange={(e) => setPreviewText(e.target.value)}
              rows={10}
              style={{width:"100%",background:"#1f2937",border:"1px solid #374151",borderRadius:8,padding:"8px 12px",fontSize:12,color:"#d1d5db",fontFamily:"monospace",outline:"none",resize:"vertical"}}
              placeholder="Edytuj opis przed wysłaniem..."
            />
          </div>
        )}

        {/* Komunikaty statusu / wyniki */}
        {(status==="done" || status==="error") && result && Object.keys(result).length > 0 && !result.error && (
          <div style={{marginBottom:12, padding:"8px 12px", background:"rgba(255,255,255,0.03)", borderRadius:6, border:"1px solid #374151"}}>
            {Object.entries(result).map(([k,v]) => {
              const isError = String(v).toLowerCase().includes('error');
              const isWarning = String(v).toLowerCase().includes('warning');
              const color = isError ? '#f87171' : isWarning ? '#fbbf24' : '#4ade80';
              return (
                <div key={k} style={{color, fontSize: 13, marginBottom: 4, display: "flex", alignItems: "flex-start", gap: 6}}>
                  <span>{isError ? '❌' : isWarning ? '⚠️' : '✔️'}</span>
                  <span><strong>{channels.find(c => c.channel_id === k)?.channel_title || k}:</strong> {v}</span>
                </div>
              );
            })}
          </div>
        )}

        {status==="error" && result.error && (
          <div style={{color:"#f87171",marginBottom:12,padding:"8px 12px",background:"rgba(239,68,68,0.1)",borderRadius:6,border:"1px solid rgba(239,68,68,0.3)",fontSize:13}}>
            ⚠️ Błąd publikacji: {result.error}
          </div>
        )}

        <div style={{display:"flex",gap:8,justifyContent:"flex-end",marginTop:16}}>
          <button
            onClick={onClose}
            style={{background:"transparent",color:"#9ca3af",padding:"8px 16px",borderRadius:6,border:"1px solid #374151",cursor:"pointer"}}
          >
            {status === "done" ? "Zamknij" : "Anuluj"}
          </button>

          {!showPreview ? (
            <button
              onClick={handlePreviewClick}
              disabled={!selected.length}
              title={!selected.length ? "Najpierw wybierz kanał YouTube" : undefined}
              style={{
                background: !selected.length ? "#374151" : "#7c3aed",
                color: !selected.length ? "#9ca3af" : "white",
                padding:"8px 16px",
                borderRadius:6,
                cursor: !selected.length ? "not-allowed" : "pointer",
                border: "none",
              }}
            >
              Podgląd opisu
            </button>
          ) : (
            <button
              onClick={publish}
              disabled={status==="loading" || !selected.length}
              title={!selected.length ? "Wybierz przynajmniej jeden kanał YouTube" : undefined}
              style={{
                background: (!selected.length || status==="loading") ? "#374151" : "#7c3aed",
                color: (!selected.length || status==="loading") ? "#9ca3af" : "white",
                padding:"8px 16px",
                borderRadius:6,
                cursor: (!selected.length || status==="loading") ? "not-allowed" : "pointer",
                border: "none",
              }}
            >
              {status==="loading" ? "Wysyłam..." : "Wyślij na YouTube"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
