"use client";
import { useState, useRef, useEffect } from "react";

interface Channel {
  id: string; // w ytChannels z dashboard to jest id a nie channel_id
  title: string; // upewnijmy sie jak ytChannels sa zdefiniowane w dashboard-inner: type YtChannel = { id: string, title: string, thumbnail: string }
}

interface YouTubePublishModalProps {
  isOpen: boolean;
  onClose: () => void;
  videoId: string;
  description: string;
  channels: Channel[];
  accessToken: string;
  apiUrl: string;
}

export function YouTubePublishModal({
  isOpen, onClose, videoId, description, channels, accessToken, apiUrl
}: YouTubePublishModalProps) {
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [result, setResult] = useState<Record<string, string>>({});
  const modalRef = useRef<HTMLDivElement>(null);

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

  if (!isOpen) return null;

  const toggleChannel = (id: string) => {
    setSelectedChannels(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    );
  };

  const handlePublish = async () => {
    if (selectedChannels.length === 0) return;
    setStatus("loading");
    try {
      const res = await fetch(`${apiUrl}/v1/youtube/publish-description`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(accessToken && { Authorization: `Bearer ${accessToken}` }),
        },
        body: JSON.stringify({
          channel_ids: selectedChannels,
          video_id: videoId,
          description: description,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Błąd publikacji");
      setResult(data.results || {});
      setStatus("done");
    } catch (err: any) {
      setResult({ error: err.message });
      setStatus("error");
    }
  };

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
        <div className="p-6">
          <h3 className="text-xl font-bold text-white mb-2">Wyślij opis na YouTube</h3>
          <p className="text-xs text-gray-400 mb-6 font-mono">Video ID: {videoId}</p>

          <div className="space-y-3 mb-6 max-h-64 overflow-y-auto pr-2">
            {channels.map(ch => (
              <label key={ch.id} className="flex items-center gap-3 p-3 rounded-xl border border-gray-800 bg-gray-900 hover:bg-gray-800/50 cursor-pointer transition-colors group">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded border-gray-700 text-violet-600 focus:ring-violet-600 focus:ring-offset-gray-900 bg-gray-800"
                  checked={selectedChannels.includes(ch.id)}
                  onChange={() => toggleChannel(ch.id)}
                />
                <span className="text-sm font-medium text-gray-200 group-hover:text-white transition-colors">{ch.title}</span>
              </label>
            ))}
            {channels.length === 0 && (
              <p className="text-sm text-gray-500 italic">Brak podłączonych kanałów YouTube.</p>
            )}
          </div>

          {status === "done" && (
            <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
              {Object.entries(result).map(([ch, st]) => (
                <div key={ch} className="font-mono text-xs">{ch}: {st}</div>
              ))}
            </div>
          )}
          {status === "error" && (
            <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              Błąd: {result.error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 bg-gray-900/50 border-t border-gray-800">
          <button
            onClick={onClose}
            disabled={status === "loading"}
            className="px-5 py-2.5 text-sm font-medium text-gray-400 hover:text-white transition-colors disabled:opacity-50"
          >
            Anuluj
          </button>
          <button
            onClick={handlePublish}
            disabled={status === "loading" || selectedChannels.length === 0}
            className="px-5 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-sm font-medium text-white rounded-xl hover:opacity-90 transition-all disabled:opacity-50 flex items-center gap-2"
          >
            {status === "loading" ? "Wysyłanie..." : "Wyślij na YouTube"}
          </button>
        </div>
      </div>
    </div>
  );
}
