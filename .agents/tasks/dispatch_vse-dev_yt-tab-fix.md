# DISPATCH — vse-dev | YT Tab + Preview Fix

**Data:** 2026-07-13  
**Od:** Supervisor 01  
**Do:** vse-dev  
**Priorytet:** HIGH — bugfix + UX redesign

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

## ⚠️ ZNANE PUŁAPKI

1. `dashboard-inner.tsx` jest duży (~88KB) — pobieraj fragmenty, nie cały plik przez MCP
2. SHA pliku zmienia się po każdym commicie — przed UPDATE zawsze pobierz świeże SHA
3. `[object Object]` = array wpadł do string template bez `.join()` lub formatowania
4. NIE buduj opisu po raz drugi w frontendzie — czytaj go ze źródła (patrz Analiza poniżej)

---

## 🔍 ANALIZA PROBLEMU (przeczytaj zanim zaczniesz kodować)

### Problem 1: `[object Object]` w podglądzie

W `buildPreview()` (dodanym przez poprzedni dispatch) rozdziały są pushowane jako array:
```js
if (schemaData?.youtube_chapters) parts.push(schemaData.youtube_chapters) // ❌
```
Zamiast być sformatowane jako stringi `MM:SS Tytuł`.

### Problem 2: Podgląd ≠ YouTube

Frontend buduje opis z pól `schemaData.youtube_*` lokalnie.
Backend buduje opis przez `build_yt_description()` w `inject.py`.
Są to **dwa różne miejsca** — stąd rozbieżność.

**Rozwiązanie:** Użyj pola które backend już buduje i zwraca.
Sprawdź w `schemaData` czy istnieje pole `youtube_format` lub `youtube_description`
(szukaj w odpowiedzi `/v1/generate` — jest tam `Format YouTube (do opisu wideo)` w UI,
co sugeruje że pole już istnieje w response).

**Krok 1 researchu:** Sprawdź w `dashboard-inner.tsx` jak obsługiwane jest
`Format YouTube (do opisu wideo)` / `Wklej do opisu YT` — to wskaże dokładną nazwę pola.

---

## 🎯 CEL ZADANIA

### A) Nowa zakładka "Opis YouTube" w panelu wyników

**Docelowy UX:**
```
[Schemat] [Artykuł] [Rozdziały] [Opis YouTube]  ← NOWA zakładka
```

- Pojawia się po wygenerowaniu SEO (obok Schemat/Artykuł/Rozdziały)
- Zawiera edytowalną `<textarea>` z pełnym opisem YT
- Treść = dokładnie to co trafi na YouTube (patrz źródło poniżej)
- Użytkownik może edytować PRZED wysłaniem
- Przycisk "Wyślij na YouTube" (istniejący) czyta z tej zakładki

### B) Uproszczenie modalu wysyłania

Obecny popup `YouTubePublishModal` zawiera textarea z podglądem —
po tej zmianie modal wraca do prostej formy:
- Lista kanałów z checkboxami
- Przycisk "Wyślij na YouTube"
- NIE duplikuje textarea (opis jest już edytowany w zakładce)
- Wysyła `override_description` = zawartość pola z zakładki "Opis YouTube"

### C) Bugfix [object Object]

Naprawa formatowania rozdziałów w podglądzie.

---

## 📋 IMPLEMENTACJA

### KROK 1: Znajdź właściwe pole opisu

W `dashboard-inner.tsx` znajdź obsługę sekcji "Format YouTube" (szukaj `youtube_format`,
`youtube_description`, `Wklej do opisu YT`, `format_youtube` itp.).

To pole jest źródłem prawdy dla zakładki. Zanotuj jego nazwę.

Jeśli pole nie istnieje — użyj fallback:
```typescript
const buildYtDescription = (schema: any): string => {
  const parts: string[] = []
  if (schema?.youtube_description_body) parts.push(schema.youtube_description_body)
  if (schema?.youtube_mid_cta) parts.push(schema.youtube_mid_cta)
  // Rozdziały — ZAWSZE formatuj jako string, nigdy nie pushuj array!
  if (Array.isArray(schema?.chapters) && schema.chapters.length > 0) {
    const lines = schema.chapters.map((c: any) => {
      const sec = c.time ?? c.startOffset ?? 0
      const m = Math.floor(sec / 60).toString().padStart(2, '0')
      const s = Math.floor(sec % 60).toString().padStart(2, '0')
      return `${m}:${s} ${c.label ?? c.name ?? ''}`.trim()
    })
    parts.push('ROZDZIAŁY:\n' + lines.join('\n'))
  }
  if (schema?.youtube_credits) parts.push(schema.youtube_credits)
  if (schema?.youtube_hashtags) {
    const tags = Array.isArray(schema.youtube_hashtags)
      ? schema.youtube_hashtags.join(',')
      : schema.youtube_hashtags
    parts.push(tags)
  }
  return parts.join('\n\n')
}
```

### KROK 2: Dodaj zakładkę w TabBar

W `TabBar` (komponent w `dashboard-inner.tsx`):
```typescript
// Typ TabKey — dodaj 'youtube'
type TabKey = 'schema' | 'article' | 'chapters' | 'youtube'

// W tablicy tabs dodaj:
{ key: 'youtube', label: 'Opis YouTube' }
// Zakładka widoczna tylko gdy result istnieje (tak samo jak pozostałe)
```

### KROK 3: Stan edytowalnego opisu

W `DashboardInner`:
```typescript
const [ytDescription, setYtDescription] = useState<string>('')

// Gdy result się pojawi (useEffect na result):
useEffect(() => {
  if (result?.raw) {
    setYtDescription(buildYtDescription(result.raw))
    // lub: result.raw.youtube_format jeśli pole istnieje
  }
}, [result])
```

### KROK 4: Renderowanie zakładki

W sekcji renderowania zakładek (gdzie jest `active === 'schema'` itp.):
```tsx
{active === 'youtube' && (
  <div>
    <div className="flex items-center justify-between mb-3">
      <span className="text-sm text-gray-400">
        Edytuj opis przed wysłaniem na YouTube
      </span>
      <CopyButton text={ytDescription} id="yt-desc" copiedKey={copiedKey} onCopy={handleCopy} />
    </div>
    <textarea
      value={ytDescription}
      onChange={(e) => setYtDescription(e.target.value)}
      rows={20}
      className="w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-3 text-sm text-gray-300 font-mono focus:outline-none focus:border-violet-500 resize-y leading-relaxed"
      placeholder="Wygeneruj SEO aby zobaczyć podgląd opisu YouTube..."
    />
    <p className="text-xs text-gray-600 mt-2">
      Zmiany tutaj zostaną wysłane na YouTube — nie nadpisują wygenerowanego opisu.
    </p>
  </div>
)}
```

### KROK 5: Przekazanie do YouTubePublishModal

Przycisk "Wyślij na YouTube" otwiera modal — przekaż `ytDescription` jako prop:
```tsx
// W miejscu gdzie renderowany jest YouTubePublishModal:
<YouTubePublishModal
  ...
  overrideDescription={ytDescription}  // NOWY PROP
/>
```

W `YouTubePublishModal.tsx`:
1. Dodaj prop `overrideDescription?: string`
2. Usuń textarea z podglądem (lub zostaw jako readonly info)
3. W `publish()` użyj `overrideDescription` w body:
```typescript
body: JSON.stringify({
  channel_ids: selected,
  video_id: videoId,
  schema_data: schemaData,
  wp_article_url: wpUrl,
  ...(overrideDescription && { override_description: overrideDescription })
})
```

### KROK 6: InjectModal — analogicznie

W `InjectModal` — textarea z podglądem YT też powinna czytać z `ytDescription`
przekazanego jako prop, a nie budować lokalnie. Usuń lokalny `useEffect` budujący opis,
dodaj prop `ytDescription` i użyj go bezpośrednio.

---

## ✅ DEFINITION OF DONE

- [ ] Zakładka "Opis YouTube" widoczna w panelu po wygenerowaniu
- [ ] Textarea w zakładce jest edytowalna, pełna treść opisu YT
- [ ] Brak `[object Object]` — rozdziały sformatowane jako `MM:SS Tytuł`
- [ ] "Wyślij na YouTube" wysyła zawartość zakładki (override)
- [ ] Zawartość zakładki = to co ląduje na YouTube (parity)
- [ ] Deploy na VPS + rebuild vse-web
- [ ] Brak błędów TypeScript

---

## 📨 RAPORT

1. `video-seo-engine/.agents/reports/2026-07-13_vse-dev_yt-tab-fix.md`
2. `sonic-void/.agents/reports/inbox/2026-07-13_vse-dev_yt-tab-fix.md`
3. Heartbeat `status: "done"`

---

*Supervisor 01 | sonic-void | 2026-07-13*
