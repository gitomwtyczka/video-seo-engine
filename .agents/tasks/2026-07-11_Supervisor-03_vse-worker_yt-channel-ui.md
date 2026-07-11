# Dispatch: YouTube Channel Selection w InjectModal
**Od:** Supervisor-03  
**Do:** vse-worker (Flash)  
**Data:** 2026-07-11  
**Plik:** `web/src/app/dashboard/dashboard-inner.tsx`  
**SHA:** `b6eba368a25a44bc2df8fa2f71fffbbed562f15f`

---

## ⚠️ ZNANE PUŁAPKI — PRZECZYTAJ ZANIM ZACZNIESZ

1. **Rules of Hooks** — NIGDY nie dodawaj `return` przed hookami. Ten błąd był root causem wcześniejszej awarii.
2. **NIE dodawaj `useSession()`** wewnątrz InjectModal — token przekaż jako prop z DashboardInner.
3. **Nie ruszaj** niczego poza opisanymi sekcjami.
4. **SHA do create_or_update_file:** `b6eba368a25a44bc2df8fa2f71fffbbed562f15f`
5. Po commicie zrób `get_file_contents` i zweryfikuj że zmiany są w pliku.

---

## CEL

Dodać wybór kanałów YouTube do `InjectModal`. Użytkownik po wygenerowaniu SEO może:
1. Opublikować artykuł na WordPress (istniejące)
2. **[NOWE]** Wybrać kanały YouTube do których artykuł zostanie wysłany

Backend endpoint już istnieje: `GET /v1/youtube/channels` → zwraca listę podłączonych kanałów usera.

---

## ZMIANY — 4 precyzyjne bloki

### ZMIANA 1: Dodaj interface YtChannel (po istniejących interfejsach, ok. linia 75 przed `type CopiedKey`)

```typescript
interface YtChannel {
  id: string
  channel_id: string
  channel_title: string
  channel_thumbnail?: string
}
```

---

### ZMIANA 2: Dodaj `accessToken` do propsów InjectModal

Znajdź:
```typescript
function InjectModal({
  schemaData,
  videoUrl,
  selectedPortalId,
  portalName,
  portalUrl,
  onClose,
}: {
  schemaData: SchemaData
  videoUrl: string
  selectedPortalId: string
  portalName?: string
  portalUrl?: string
  onClose: () => void
})
```

Zastąp na:
```typescript
function InjectModal({
  schemaData,
  videoUrl,
  selectedPortalId,
  portalName,
  portalUrl,
  accessToken,
  onClose,
}: {
  schemaData: SchemaData
  videoUrl: string
  selectedPortalId: string
  portalName?: string
  portalUrl?: string
  accessToken?: string
  onClose: () => void
})
```

---

### ZMIANA 3: Dodaj stan i fetch kanałów YT wewnątrz InjectModal

Znajdź blok inicjalizacji stanu w InjectModal (zaraz po `const modalRef = useRef...`):
```typescript
  const modalRef = useRef<HTMLDivElement>(null)

  // Close on Escape
```

Zastąp na:
```typescript
  const modalRef = useRef<HTMLDivElement>(null)

  // YouTube channels
  const [ytChannels, setYtChannels] = useState<YtChannel[]>([])
  const [selectedYtChannelIds, setSelectedYtChannelIds] = useState<string[]>([])
  const [ytLoading, setYtLoading] = useState(false)

  useEffect(() => {
    if (!accessToken) return
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
    setYtLoading(true)
    fetch(`${apiUrl}/v1/youtube/channels`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => r.ok ? r.json() : [])
      .then((data) => setYtChannels(Array.isArray(data) ? data : []))
      .catch(() => setYtChannels([]))
      .finally(() => setYtLoading(false))
  }, [accessToken])

  const toggleYtChannel = (channelId: string) => {
    setSelectedYtChannelIds((prev) =>
      prev.includes(channelId)
        ? prev.filter((id) => id !== channelId)
        : [...prev, channelId]
    )
  }

  // Close on Escape
```

---

### ZMIANA 4: Dodaj `yt_channel_ids` do body w handlePublish

Znajdź w `handlePublish`:
```typescript
      if (wpPostId.trim()) {
        body.wp_post_id = parseInt(wpPostId, 10)
      }
```

Zastąp na:
```typescript
      if (wpPostId.trim()) {
        body.wp_post_id = parseInt(wpPostId, 10)
      }
      if (selectedYtChannelIds.length > 0) {
        body.yt_channel_ids = selectedYtChannelIds
      }
```

---

### ZMIANA 5: Dodaj UI wyboru kanałów YT w JSX InjectModal

Znajdź w JSX InjectModal komentarz i sekcję przed "Post ID + Status + Format":
```tsx
          {/* Post ID + Status + Format */}
```

Zastąp na:
```tsx
          {/* YouTube channels */}
          {ytLoading && (
            <p className="text-xs text-gray-500">Ładowanie kanałów YouTube...</p>
          )}
          {!ytLoading && ytChannels.length > 0 && (
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Kanały YouTube (opcjonalnie)</label>
              <div className="space-y-2 max-h-32 overflow-y-auto">
                {ytChannels.map((ch) => (
                  <label key={ch.id} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedYtChannelIds.includes(ch.channel_id)}
                      onChange={() => toggleYtChannel(ch.channel_id)}
                      className="accent-red-500"
                    />
                    {ch.channel_thumbnail && (
                      <img src={ch.channel_thumbnail} alt="" className="w-5 h-5 rounded-full" />
                    )}
                    <span className="text-sm text-gray-300">{ch.channel_title}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
          {!ytLoading && ytChannels.length === 0 && accessToken && (
            <p className="text-xs text-gray-600">Brak podłączonych kanałów YouTube. <a href="/ustawienia" className="text-violet-400 hover:underline">Podłącz kanał →</a></p>
          )}

          {/* Post ID + Status + Format */}
```

---

### ZMIANA 6: Przekaż `accessToken` do InjectModal w DashboardInner

Znajdź render InjectModal w DashboardInner (ok. linia 1713):
```tsx
          <InjectModal
```

Dodaj prop `accessToken={accessToken}` do tego komponentu. Całe wywołanie wygląda mniej więcej tak — dodaj jeden prop:
```tsx
            <InjectModal
              ...
              accessToken={accessToken}
              ...
            />
```

Szukaj w kodzie dokładnego miejsca gdzie InjectModal jest renderowany i dodaj `accessToken={accessToken}` do jego propsów.

---

## KROKI WYKONANIA

1. Pobierz plik przez GitHub MCP (`get_file_contents`) — upewnij się że masz aktualne SHA
2. Wprowadź **wszystkie 6 zmian** do pełnej treści pliku
3. Wgraj przez `create_or_update_file` (SHA: `b6eba368a25a44bc2df8fa2f71fffbbed562f15f`)
4. Zweryfikuj `get_file_contents` że `YtChannel`, `accessToken`, `ytChannels` są w pliku
5. SSH — git pull + rebuild:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web 2>&1 | tail -5"
```
6. Sprawdź logi po 30s:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker logs --tail 10 vse-web 2>&1"
```
7. Dual-write raport:
   - `video-seo-engine/.agents/reports/2026-07-11_vse-worker_yt-channel-ui.md`
   - `sonic-void/.agents/reports/inbox/2026-07-11_vse-worker_yt-channel-ui.md`

Raport: commit SHA + czy `✓ Compiled successfully` + czy `YtChannel` widoczny po get_file_contents.

---
*[Supervisor-03 | sonic-void 11.07.2026]*