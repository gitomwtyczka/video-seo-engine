"use client";
import { useState } from "react";

interface Channel { channel_id: string; channel_title: string; }

interface Props {
  isOpen: boolean;
  onClose: () => void;
  videoId: string;
  description: string;
  channels: Channel[];
  accessToken: string;
  apiUrl: string;
}

export function YouTubePublishModal({ isOpen, onClose, videoId, description, channels, accessToken, apiUrl }: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const [status, setStatus] = useState<"idle"|"loading"|"done"|"error">("idle");
  const [result, setResult] = useState<Record<string,string>>({});

  if (!isOpen) return null;

  const toggle = (id: string) => setSelected(p => p.includes(id) ? p.filter(c=>c!==id) : [...p,id]);

  const publish = async () => {
    if (!selected.length) return;
    setStatus("loading");
    try {
      const res = await fetch(`${apiUrl}/v1/youtube/publish-description`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(accessToken && { Authorization: `Bearer ${accessToken}` }) },
        body: JSON.stringify({ channel_ids: selected, video_id: videoId, description }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Blad");
      setResult(data.results || {});
      setStatus("done");
    } catch (e: any) { setResult({ error: e.message }); setStatus("error"); }
  };

  return (
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.7)",zIndex:50,display:"flex",alignItems:"center",justifyContent:"center"}}>
      <div style={{background:"#1a1a2e",borderRadius:12,padding:24,width:420,maxWidth:"90vw"}}>
        <h3 style={{marginBottom:8}}>Wyslij opis na YouTube</h3>
        <p style={{fontSize:12,opacity:0.5,marginBottom:16}}>Video: {videoId}</p>
        {channels.map(ch => (
          <label key={ch.channel_id} style={{display:"flex",gap:8,alignItems:"center",marginBottom:8,cursor:"pointer"}}>
            <input type="checkbox" checked={selected.includes(ch.channel_id)} onChange={()=>toggle(ch.channel_id)} />
            {ch.channel_title}
          </label>
        ))}
        {status==="done" && <div style={{color:"#4ade80",marginBottom:8}}>{Object.entries(result).map(([k,v])=><div key={k}>{k}: {v}</div>)}</div>}
        {status==="error" && <div style={{color:"#f87171",marginBottom:8}}>Blad: {result.error}</div>}
        <div style={{display:"flex",gap:8,justifyContent:"flex-end",marginTop:16}}>
          <button onClick={onClose}>Anuluj</button>
          <button onClick={publish} disabled={status==="loading"||!selected.length}
            style={{background:"#7c3aed",color:"white",padding:"8px 16px",borderRadius:6}}>
            {status==="loading" ? "Wysylam..." : "Wyslij na YouTube"}
          </button>
        </div>
      </div>
    </div>
  );
}
