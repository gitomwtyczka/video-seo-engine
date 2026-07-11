# Dispatch: YouTube channels — 3 bugi UX
**Od:** Supervisor-03  
**Do:** vse-worker (Flash)  
**Data:** 2026-07-11  
**Priorytet:** WYSOKI

---

## ⚠️ ZNANE PUŁAPKI
1. Plik `ustawienia/page.tsx` ~30KB, `youtube.py` duży — SHA pobierz przed każdym zapisem.
2. Nie ruszaj logiki poza opisanymi zmianami.
3. Rebuild po WSZYSTKICH commitach — jeden deploy na końcu.

---

## BUG 1 — Diagnostyka: channel w DB ale brak tytułu

### KROK 1a — sprawdź DB
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker exec vse-postgres psql -U postgres -d vse -c 'SELECT id, user_id, channel_id, channel_title, created_at FROM youtube_channels ORDER BY created_at DESC LIMIT 10;'"
```

Jeśli `channel_title` = NULL lub pusty string — problem jest w backendzie podczas zapisu. Przejdź do KROK 1b.

### KROK 1b — sprawdź callback handler w `api/routers/youtube.py`

Grep:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "grep -n 'channel_title\|channel_id\|snippet\|items\|channels\|Failed to fetch' /home/ubuntu/video-seo-engine/api/routers/youtube.py"
```

Jeśli backend używa `YOUTUBE_API_KEY` do pobierania info o kanale (zamiast OAuth token) — może zwracać błąd gdy klucz jest z innego projektu. Fix: użyj access_token z OAuth do zapytania YouTube API o channel info.

Zapisz surowe wyniki i przejdź do BUG 2.

---

## BUG 2 — Backend: redirect po OAuth callback zamiast JSON

### Plik: `api/routers/youtube.py` — funkcja callback

Obecnie: zwraca JSON `{"status":"ok",...}`
Po zmianie: redirect na frontend `/ustawienia?yt=connected`

```python
# Zamień return {"status": "ok", ...} na:
from fastapi.responses import RedirectResponse
return RedirectResponse(url="https://vse.impresjapr.pl/ustawienia?yt=connected", status_code=302)
```

Jeśli callback zwraca błąd (np. "Failed to fetch channel info") — redirect na:
`https://vse.impresjapr.pl/ustawienia?yt=error`

---

## BUG 3 — Frontend: toast po powrocie z OAuth + "already connected"

### Plik: `web/src/app/ustawienia/page.tsx`

Dodaj `useEffect` który czyta query param `?yt=connected` lub `?yt=error` i wyświetla toast/komunikat.

Dodaj wśród importów:
```typescript
import { useSearchParams } from 'next/navigation'
```

Dodaj useState:
```typescript
const [ytStatus, setYtStatus] = useState<string | null>(null)
```

Dodaj useEffect:
```typescript
const searchParams = useSearchParams()
useEffect(() => {
  const yt = searchParams.get('yt')
  if (yt) {
    setYtStatus(yt)
    // wyczyść param z URL bez reload
    window.history.replaceState({}, '', '/ustawienia')
  }
}, [searchParams])
```

Dodaj JSX nad sekcją YouTube:
```tsx
{ytStatus === 'connected' && (
  <div className="bg-green-900/30 border border-green-500/30 rounded-xl px-4 py-3 text-sm text-green-400 flex items-center gap-2">
    <span>✅</span> Kanał YouTube został pomyślnie podłączony!
  </div>
)}
{ytStatus === 'error' && (
  <div className="bg-red-900/30 border border-red-500/30 rounded-xl px-4 py-3 text-sm text-red-400 flex items-center gap-2">
    <span>⚠️</span> Błąd podczas podłączania kanału. Spróbuj ponownie.
  </div>
)}
```

### Handler "already connected" w `handleConnectYoutube`:

Jeśli fetch `/v1/youtube/oauth/login` zwraca 409 lub podobny kod:
```typescript
const res = await fetch(`${apiUrl}/v1/youtube/oauth/login`, { headers: {...} })
if (res.status === 409) {
  alert('Ten kanał jest już podłączony.')
  return
}
```

---

## KOLEJNOŚĆ

1. Diagnostyka DB + grep youtube.py → zapisz wyniki
2. Fix BUG 1 (jeśli channel_title NULL — popraw zapis w backendzie)
3. Fix BUG 2 (redirect w callback)
4. Fix BUG 3 (toast + already connected)
5. Jeden rebuild:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-api vse-web 2>&1 | tail -8"
```

---

## RAPORT — dual-write

1. `video-seo-engine/.agents/reports/2026-07-11_vse-worker_yt-ux-fixes.md`
2. `sonic-void/.agents/reports/inbox/2026-07-11_vse-worker_yt-ux-fixes.md`

Raport: wyniki diagnostyki DB + commit SHA per bug + logi po deployu.

---
*[Supervisor-03 | sonic-void 11.07.2026]*