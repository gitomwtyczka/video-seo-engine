# DISPATCH 3/4 — vse-dev | Nowa zakładka "Opis YouTube" w panelu wyników

**Data:** 2026-07-13  
**Od:** Supervisor 01  
**Do:** vse-dev  
**Zakres:** TYLKO `dashboard-inner.tsx` — nowa zakładka. Zero deploy. Zero innych plików.

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

1. `dashboard-inner.tsx` to ~88KB — pobieraj przez `get_file_contents`, SHA zmienia się po każdym commicie
2. Plik był już edytowany w tej sesji — **zawsze pobierz świeże SHA** przed update
3. Zakres: TYLKO zmiany dotyczące zakładki. Nie ruszaj InjectModal, YouTubePublishModal, logiki generowania
4. BEZ DEPLOY

---

## 🎯 ZADANIE

Dodaj zakładkę **"Opis YouTube"** do panelu wyników obok Schemat / Artykuł / Rozdziały.

### Kontekst (z raportu analityka)

OpisYT nie żyje w jednym polu — to kompozycja:
- `schemaData.youtube_description_body` (M1)
- `[WSTAW LINK]` lub `wpUrl` (M2)
- `schemaData.youtube_mid_cta` (M3)
- `schemaData.chapters` → format `MM:SS Tytuł` (M4)
- `schemaData.youtube_credits` (M5)
- `schemaData.youtube_hashtags` → array → join (M8)

Funkcja `buildYtDescription` musi być identyczna z tą w `YouTubePublishModal.tsx` (naprawioną w dispatch 2/4 — commit `fe650a8`).

---

## 📋 IMPLEMENTACJA

### Zmiana 1 — typ TabKey

Znajdź definicję:
```typescript
type TabKey = 'schema' | 'article' | 'chapters'
```
Zmień na:
```typescript
type TabKey = 'schema' | 'article' | 'chapters' | 'youtube'
```

### Zmiana 2 — funkcja buildYtDescription

Dodaj **przed** komponentem `DashboardInner` (lub jako helper obok innych helperów):

```typescript
/** Buduje podgląd opisu YouTube z pól schemaData — musi być spójny z buildPreview() w YouTubePublishModal */
function buildYtDescription(schema: SchemaData | null | undefined, wpUrl?: string): string {
  if (!schema) return ''
  const parts: string[] = []

  if (schema.youtube_description_body) parts.push(schema.youtube_description_body as string)

  parts.push(`🔗 Artykuł: ${wpUrl || '[WSTAW LINK]'}`)

  if (schema.youtube_mid_cta) parts.push(schema.youtube_mid_cta as string)

  const rawChapters = schema.chapters
  if (Array.isArray(rawChapters) && rawChapters.length > 0) {
    const lines = rawChapters.map((c: ChapterItem) => {
      const sec = c.time ?? c.startOffset ?? 0
      const m = Math.floor(sec / 60).toString().padStart(2, '0')
      const s = Math.floor(sec % 60).toString().padStart(2, '0')
      const title = c.label ?? c.name ?? ''
      return `${m}:${s} ${title}`.trim()
    })
    parts.push('ROZDZIAŁY:\n' + lines.join('\n'))
  }

  if (schema.youtube_credits) parts.push(schema.youtube_credits as string)

  const hashtags = schema.youtube_hashtags
  if (hashtags) {
    if (Array.isArray(hashtags)) {
      const tags = (hashtags as string[])
        .map(t => t.startsWith('#') ? t : `#${t}`)
        .join(',')
      if (tags) parts.push(tags)
    } else if (typeof hashtags === 'string') {
      parts.push(hashtags)
    }
  }

  return parts.join('\n\n')
}
```

### Zmiana 3 — stan ytDescription w DashboardInner

W `DashboardInner`, obok innych stanów (`url`, `loading`, `result` itd.), dodaj:

```typescript
const [ytDescription, setYtDescription] = useState<string>('')
```

### Zmiana 4 — useEffect wypełniający ytDescription

Dodaj `useEffect` który odpala się gdy pojawi się wynik generowania:

```typescript
useEffect(() => {
  if (result?.raw) {
    // wpUrl — pobierz ze stanu credentials lub z result jeśli dostępny
    const wpLink = result.raw?.wp_url as string | undefined
    setYtDescription(buildYtDescription(result.raw as SchemaData, wpLink))
  }
}, [result])
```

> Uwaga: `wpUrl` może być też z localStorage lub stanu formularza. Sprawdź jak jest przechowywany w istniejącym kodzie i użyj tej samej zmiennej.

### Zmiana 5 — dodanie zakładki w TabBar

Znajdź tablicę `tabs` w komponencie `TabBar`:
```typescript
const tabs: { key: TabKey; label: string; badge?: number }[] = [
  { key: 'schema', label: 'Schemat' },
  { key: 'article', label: 'Artykuł', badge: ... },
  { key: 'chapters', label: 'Rozdziały', badge: ... },
]
```
Dodaj na końcu:
```typescript
  { key: 'youtube', label: 'Opis YouTube' },
```

### Zmiana 6 — renderowanie zawartości zakładki

Znajdź blok warunkowy gdzie renderowane są zakładki (np. `{activeTab === 'schema' && ...}`).
Dodaj analogiczny blok dla `youtube`:

```tsx
{activeTab === 'youtube' && (
  <div className="space-y-3">
    <div className="flex items-center justify-between">
      <p className="text-xs text-gray-500">
        Edytowalny podgląd — zmiany zostaną wysłane na YouTube zamiast wygenerowanego opisu
      </p>
      <CopyButton
        text={ytDescription}
        id="yt-desc-tab"
        copiedKey={copiedKey}
        onCopy={handleCopy}
      />
    </div>
    <textarea
      value={ytDescription}
      onChange={(e) => setYtDescription(e.target.value)}
      rows={22}
      className="w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-3 text-sm text-gray-300 font-mono focus:outline-none focus:border-violet-500 resize-y leading-relaxed"
      placeholder="Wygeneruj SEO aby zobaczyć podgląd opisu YouTube..."
    />
  </div>
)}
```

### Zmiana 7 — przekazanie ytDescription do YouTubePublishModal

Znajdź miejsce gdzie renderowany jest `<YouTubePublishModal ... />`.
Dodaj prop `overrideDescription`:

```tsx
<YouTubePublishModal
  ...
  overrideDescription={ytDescription}
/>
```

> UWAGA: Jeśli `YouTubePublishModal` nie ma jeszcze tego propa — nie dodawaj go teraz do modalu. To zrobi dispatch 4/4. Przekaż tylko prop, a modal go zignoruje do czasu dispatchu 4.

---

## ✅ DEFINITION OF DONE

- [ ] Typ `TabKey` rozszerzony o `'youtube'`
- [ ] Funkcja `buildYtDescription` dodana jako helper
- [ ] Stan `ytDescription` w `DashboardInner`
- [ ] `useEffect` wypełniający `ytDescription` gdy pojawi się `result`
- [ ] Zakładka "Opis YouTube" widoczna w `TabBar`
- [ ] Renderowanie: edytowalna `textarea` + `CopyButton`
- [ ] Prop `overrideDescription={ytDescription}` przekazany do `YouTubePublishModal`
- [ ] Commit na GitHub MCP
- [ ] BEZ DEPLOY
- [ ] Brak nowych błędów TypeScript

---

## 📨 RAPORT

```
video-seo-engine/.agents/reports/2026-07-13_vse-dev_yt-tab.md
sonic-void/.agents/reports/inbox/2026-07-13_vse-dev_yt-tab.md
```

Zawartość: SHA commitu, lista zmian (przed/po dla każdej), błędy TS jeśli były.

---

*Supervisor 01 | sonic-void | 2026-07-13 | dispatch 3/4*
