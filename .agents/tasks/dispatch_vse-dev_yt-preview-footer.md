# DISPATCH — vse-dev | YT Description Preview + footer_text UI

**Data:** 2026-07-13  
**Od:** Supervisor 01  
**Do:** vse-dev (Gemini Pro worker)  
**Repo:** video-seo-engine | branch: main  
**Priorytet:** HIGH

---

## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**0. Wczytaj blok systemowy:**
```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: sonic-void
  branch: master
  path: .agents/protocols/dispatch-system-block.md
```

**1. Wyślij heartbeat** do `video-seo-engine/.agents/heartbeat.json`

---

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)

1. **Dwa modale YT** — `YouTubePublishModal.tsx` (zakładka YT) i `InjectModal` (w `dashboard-inner.tsx`) — oba wymagają zmian
2. **GitHub MCP**: po `create_or_update_file` ZAWSZE pobierz SHA przez `get_file_contents` przed kolejnym update tego samego pliku
3. **Nie używaj lokalnego klonu** — czytaj i pisz przez GitHub MCP
4. **deploy po commit**: SSH → `cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web`
5. **SCP na Windows** — NIGDY `~` w lokalnej ścieżce. Pełna ścieżka: `C:\Users\tomas2\.ssh\oracle-crimson.key`

---

## 🎯 CEL ZADANIA

Dodać do frontendu dwie funkcjonalności:

### A) Podgląd opisu YT przed wysłaniem (w OBU modalach)
Zamiast wysyłać opis "w ciemno", user widzi textarea z gotowym opisem,  
może go edytować (jednorazowy override), i WTEDY klika "Wyślij".

### B) Pole footer_text w Ustawieniach → Kanały YouTube
W ustawieniach → Kanały YouTube, przy każdym kanale: edytowalne pole tekstowe  
ze stopką kanału. Ustawienia = kanon. Override w podglądzie = jednorazowy.

---

## 📋 IMPLEMENTACJA SZCZEGÓŁOWA

### PLIK 1: `web/src/app/dashboard/YouTubePublishModal.tsx`

**SHA pliku:** `3f0051d27cc7a24e96ed516ac99dae3a43c5feda`

**Co zmienić:**

1. Rozszerz interfejs `Channel` o pole `footer_text?: string`:
```typescript
interface Channel { channel_id: string; channel_title: string; footer_text?: string; }
```

2. Dodaj stan podglądu opisu:
```typescript
const [previewText, setPreviewText] = useState<string>('')
const [showPreview, setShowPreview] = useState<boolean>(false)
```

3. Przed wysłaniem: krok 1 = "Podgląd", krok 2 = "Wyślij". Flow:
   - User zaznacza kanały → klika "Podgląd opisu" → pobiera z backendu gotowy opis
   - Endpoint do pobrania gotowego opisu: `POST /v1/youtube/preview-description` LUB buduj lokalnie z `schemaData`
   - Jeśli endpoint preview nie istnieje — **buduj opis lokalnie** z `schemaData` (użyj pól: `youtube_description_body`, `youtube_mid_cta`, `youtube_credits`, `youtube_hashtags` z `schemaData`)
   - User może edytować textarea z podglądem
   - Przycisk "Wyślij na YouTube" wysyła `overrideDescription` zamiast budowania przez backend

4. Uproszczona implementacja bez dodatkowego endpointu:
```typescript
// Zbierz preview z schemaData
const buildPreview = () => {
  const parts = []
  if (schemaData?.youtube_description_body) parts.push(schemaData.youtube_description_body)
  if (schemaData?.youtube_mid_cta) parts.push(schemaData.youtube_mid_cta)
  if (schemaData?.youtube_credits) parts.push(schemaData.youtube_credits)
  if (schemaData?.youtube_hashtags) parts.push(schemaData.youtube_hashtags)
  return parts.join('\n\n') || '(brak wygenerowanego opisu — uruchom generowanie SEO)
}

// Przy kliknięciu "Podgląd":
setPreviewText(buildPreview())
setShowPreview(true)
```

5. UI w podglądzie: `<textarea>` z `value={previewText}` + `onChange`, min-height: 200px

6. Wyślij z overridem: do body POST dodaj `override_description: previewText` (jeśli preview był otwarty)

7. **Stopka w podglądzie**: przy pierwszym wybranym kanale, jeśli `channels[0].footer_text` — dołącz go na końcu `previewText`:
```typescript
const firstChannel = channels.find(ch => selected.includes(ch.channel_id))
if (firstChannel?.footer_text) {
  preview += '\n\n' + firstChannel.footer_text
}
```

---

### PLIK 2: `web/src/app/dashboard/dashboard-inner.tsx` — InjectModal

**SHA pliku:** `b1f447eb901a975fc9dcf67bc67f7ac22ccf52c8`

**Co zmienić:**

W `InjectModal`, w sekcji `{/* YouTube Channels */}` (po checkboxach kanałów), dodaj:

```tsx
{/* YT Description Preview */}
{selectedYtChannelIds.length > 0 && (
  <div className="mt-3">
    <label className="block text-xs text-gray-400 mb-1.5">
      Podgląd opisu YouTube <span className="text-gray-600">(edytowalny)</span>
    </label>
    <textarea
      value={ytDescPreview}
      onChange={(e) => setYtDescPreview(e.target.value)}
      rows={6}
      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 font-mono focus:outline-none focus:border-violet-500 resize-y"
      placeholder="Podgląd załaduje się automatycznie po wybraniu kanału..."
    />
  </div>
)}
```

Dodaj stany:
```typescript
const [ytDescPreview, setYtDescPreview] = useState<string>('')
```

Wypełnij podgląd przy `useEffect` gdy `selectedYtChannelIds` się zmienia:
```typescript
useEffect(() => {
  if (selectedYtChannelIds.length === 0) { setYtDescPreview(''); return }
  const parts = []
  if (schemaData?.youtube_description_body) parts.push(schemaData.youtube_description_body)
  if (schemaData?.youtube_mid_cta) parts.push(schemaData.youtube_mid_cta)
  if (schemaData?.youtube_credits) parts.push(schemaData.youtube_credits)
  if (schemaData?.youtube_hashtags) parts.push(schemaData.youtube_hashtags)
  // Stopka z pierwszego kanału
  const firstCh = ytChannels?.find(ch => selectedYtChannelIds.includes(ch.channel_id))
  if (firstCh?.footer_text) parts.push(firstCh.footer_text)
  setYtDescPreview(parts.join('\n\n'))
}, [selectedYtChannelIds, schemaData, ytChannels])
```

W `handlePublish`, gdy wysyłasz do `/v1/inject`, dodaj `yt_override_description: ytDescPreview` do body (jeśli ytDescPreview niepuste):
```typescript
if (selectedYtChannelIds.length > 0 && ytDescPreview) {
  body.yt_override_description = ytDescPreview
}
```

---

### PLIK 3: `web/src/app/ustawienia/page.tsx`

**Co zmienić:**

W sekcji renderowania kanałów YouTube (ok. linia 680-712 per raport analityka), przy każdym `ch` w mapowaniu:

```tsx
{/* footer_text — stopka kanału */}
<div className="mt-2">
  <label className="block text-xs text-gray-400 mb-1">Stopka kanału (footer)</label>
  <FooterTextEditor channel={ch} apiUrl={apiUrl} accessToken={accessToken} />
</div>
```

Dodaj helper komponent `FooterTextEditor` (w tym samym pliku):
```tsx
function FooterTextEditor({ channel, apiUrl, accessToken }: { channel: any, apiUrl: string, accessToken?: string }) {
  const [text, setText] = useState<string>(channel.footer_text || '')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      await fetch(`${apiUrl}/v1/youtube/channels/${channel.channel_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...(accessToken && { Authorization: `Bearer ${accessToken}` }) },
        body: JSON.stringify({ footer_text: text })
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        rows={3}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-violet-500 resize-y"
        placeholder="np. 📌 Obserwuj kanał | Instagram: @kanał | Linktree: ..."
      />
      <button
        onClick={save}
        disabled={saving}
        className="mt-1 px-3 py-1 text-xs bg-violet-600 text-white rounded-lg hover:bg-violet-500 disabled:opacity-50"
      >
        {saving ? 'Zapisuję...' : saved ? '✔ Zapisano' : 'Zapisz stopkę'}
      </button>
    </div>
  )
}
```

> **Uwaga:** Sprawdź jak `apiUrl` i `accessToken` są dostępne w scope strony ustawień — może być przez `useSession()` lub props. Dostosuj.

---

### PLIK 4 (opcjonalny): backend `api/routers/youtube.py`

Zweryfikuj czy endpoint `PUT /v1/youtube/channels/{id}` akceptuje `footer_text` w body.  
Jeśli tak — nie rób nic. Jeśli nie — sprawdź model Pydantic i dodaj pole.  
Nie refaktoruj — minimalna zmiana.

Zweryfikuj też czy `GET /v1/youtube/channels` zwraca `footer_text` — jeśli nie, dodaj do response schema.

Zweryfikuj czy `/v1/inject` akceptuje `yt_override_description` i przekazuje je do `update_youtube_metadata`.  
Jeśli nie — dodaj obsługę: jeśli `yt_override_description` w body, użyj tej wartości zamiast budowania przez `build_yt_description()`.

---

## 📦 KOLEJNOŚĆ WYKONANIA

1. Przeczytaj aktualne SHAs z GitHub MCP (podane wyżej mogą być nieaktualne — zawsze pobierz świeże)
2. Zaimplementuj PLIK 3 (ustawienia) — najprostszy, bez zależności
3. Zaimplementuj PLIK 1 (YouTubePublishModal) — standalone
4. Zaimplementuj PLIK 2 (InjectModal w dashboard-inner.tsx) — największy plik, ostrożnie z SHA
5. Zweryfikuj backend PLIK 4 — read-only jeśli wszystko OK
6. Deploy: git pull + docker compose build vse-web
7. Weryfikacja: SSH → `docker logs vse-web --tail 20`

---

## ✅ DEFINITION OF DONE

- [ ] W ustawieniach → Kanały YouTube: textarea na stopkę + przycisk Zapisz (wywołuje PUT)
- [ ] W YouTubePublishModal: textarea z podglądem opisu (edytowalny), pojawia się po wybraniu kanału
- [ ] W InjectModal: textarea z podglądem opisu YT (auto-fill, edytowalny), pojawia się gdy kanały wybrane
- [ ] Stopka z ustawień jest dołączona do podglądu automatycznie
- [ ] Deploy na VPS — kontener przebudowany
- [ ] Brak błędów TypeScript w commicie

---

## 📨 RAPORT

Po zakończeniu:
1. Raport do `video-seo-engine/.agents/reports/2026-07-13_vse-dev_yt-preview-footer.md`
2. Kopia do `sonic-void/.agents/reports/inbox/2026-07-13_vse-dev_yt-preview-footer.md`
3. Heartbeat `status: "done"` + commit SHAs w `last_completed[]`

---

*Supervisor 01 | sonic-void | 2026-07-13*
