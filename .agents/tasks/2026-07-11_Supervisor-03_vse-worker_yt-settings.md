# Dispatch: Sekcja YouTube Channels w /ustawienia
**Od:** Supervisor-03  
**Do:** vse-worker (Flash)  
**Data:** 2026-07-11

---

## ⚠️ ZNANE PUŁAPKI
1. Plik `ustawienia/page.tsx` ma 29KB — po zapisie zweryfikuj rozmiar (nie może być mniejszy niż 29KB).
2. SHA do `create_or_update_file`: `426cc2f3fbc0de666a0a80c8b8927ebb4d9ad65e` — pobierz aktualny SHA przez `get_file_contents` tuż przed zapisem.
3. Nie ruszaj istniejących sekcji (Konto, Portale WordPress, Plan subskrypcji).

---

## CEL

Dodać sekcję **Kanały YouTube** do strony `/ustawienia`. Link "Podłącz kanał →" z InjectModal prowadzi na tę stronę ale sekcji nie było.

**Backend endpoints (już istnieją):**
- `GET /v1/youtube/oauth/login` → `{ authorization_url: "https://accounts.google.com/..." }` — inicjuje OAuth
- `GET /v1/youtube/channels` → lista podłączonych kanałów użytkownika
- `DELETE /v1/youtube/channels/{channel_id}` → odłączenie kanału

---

## KROK 1 — Przeczytaj plik ustawienia/page.tsx

Pobierz przez GitHub MCP:
- repo: gitomwtyczka/video-seo-engine, branch: main
- path: web/src/app/ustawienia/page.tsx

Zwraca to SHA i pełną treść. Przeanalizuj:
- Jak wygląda sekcja "Portale WordPress" (wzorzec do replikacji)
- Gdzie kończy się treść komponentu (gdzie dodać nową sekcję)
- Jak strona pobiera `accessToken` (przez `useSession` lub inaczej)

---

## KROK 2 — Dodaj sekcję YouTube

Dodaj w pliku nową sekcję **po sekcji "Portale WordPress"**, wzorując się na jej strukturę wizualną.

### Stan do dodania (wewnątrz komponentu, przy innych useState):
```typescript
const [ytChannels, setYtChannels] = useState<YtChannel[]>([])
const [ytLoading, setYtLoading] = useState(false)
const [ytConnecting, setYtConnecting] = useState(false)
```

### Interface do dodania (przy innych interface'ach):
```typescript
interface YtChannel {
  id: string
  channel_id: string
  channel_title: string
  channel_thumbnail?: string
}
```

### useEffect do fetchowania kanałów (przy innych useEffect):
```typescript
useEffect(() => {
  if (!session?.accessToken) return
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
  setYtLoading(true)
  fetch(`${apiUrl}/v1/youtube/channels`, {
    headers: { Authorization: `Bearer ${session.accessToken as string}` },
  })
    .then((r) => r.ok ? r.json() : [])
    .then((data) => setYtChannels(Array.isArray(data) ? data : []))
    .catch(() => {})
    .finally(() => setYtLoading(false))
}, [session?.accessToken])
```

### Handler podłączania kanału:
```typescript
const handleConnectYoutube = async () => {
  if (!session?.accessToken) return
  setYtConnecting(true)
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
    const res = await fetch(`${apiUrl}/v1/youtube/oauth/login`, {
      headers: { Authorization: `Bearer ${session.accessToken as string}` },
    })
    if (res.ok) {
      const { authorization_url } = await res.json()
      window.location.href = authorization_url
    }
  } catch {}
  finally { setYtConnecting(false) }
}
```

### Handler odłączania kanału:
```typescript
const handleDisconnectYoutube = async (channelId: string) => {
  if (!session?.accessToken) return
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
  await fetch(`${apiUrl}/v1/youtube/channels/${channelId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${session.accessToken as string}` },
  })
  setYtChannels((prev) => prev.filter((c) => c.id !== channelId))
}
```

### JSX sekcji (wstaw PO sekcji Portale WordPress):
```tsx
{/* YouTube Channels */}
<div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-4">
  <div className="flex items-center justify-between">
    <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-lg bg-red-600/20 flex items-center justify-center text-sm">
        📺
      </div>
      <div>
        <h2 className="font-semibold text-white">Kanały YouTube</h2>
        <p className="text-xs text-gray-500">Podłączone kanały do wysyłki SEO</p>
      </div>
    </div>
    <button
      onClick={handleConnectYoutube}
      disabled={ytConnecting}
      className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
    >
      {ytConnecting ? '...' : '+ Podłącz kanał'}
    </button>
  </div>

  {ytLoading && <p className="text-sm text-gray-500">Ładowanie...</p>}

  {!ytLoading && ytChannels.length === 0 && (
    <p className="text-sm text-gray-600">Brak podłączonych kanałów YouTube.</p>
  )}

  {!ytLoading && ytChannels.map((ch) => (
    <div key={ch.id} className="flex items-center justify-between py-3 border-b border-gray-800 last:border-0">
      <div className="flex items-center gap-3">
        {ch.channel_thumbnail && (
          <img src={ch.channel_thumbnail} alt="" className="w-8 h-8 rounded-full" />
        )}
        <div>
          <p className="text-sm font-medium text-white">{ch.channel_title}</p>
          <p className="text-xs text-gray-500">{ch.channel_id}</p>
        </div>
      </div>
      <button
        onClick={() => handleDisconnectYoutube(ch.id)}
        className="text-gray-500 hover:text-red-400 transition-colors p-1"
        title="Odłącz kanał"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      </button>
    </div>
  ))}
</div>
```

---

## KROK 3 — Wgraj i zweryfikuj

1. Wgraj plik przez `create_or_update_file` z aktualnym SHA
2. Zweryfikuj `get_file_contents` że `ytChannels` i `handleConnectYoutube` są w pliku
3. SSH rebuild:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web 2>&1 | tail -5"
```
4. Logi po 30s:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker logs --tail 10 vse-web 2>&1"
```

---

## RAPORT — dual-write

1. `video-seo-engine/.agents/reports/2026-07-11_vse-worker_yt-settings.md`
2. `sonic-void/.agents/reports/inbox/2026-07-11_vse-worker_yt-settings.md`

Raport: commit SHA + `✓ Compiled successfully` + rozmiar pliku po zapisie.

---
*[Supervisor-03 | sonic-void 11.07.2026]*