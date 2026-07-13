# DISPATCH 2/4 — vse-dev | Bugfix: [object Object] w podglądzie YT

**Data:** 2026-07-13  
**Od:** Supervisor 01  
**Do:** vse-dev  
**Zakres:** TYLKO naprawa [object Object] w istniejącym podglądzie. Zero nowych featureów. Zero deploy.

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

1. Pobierz SHA pliku przed edycją (`get_file_contents` → pole `sha`)
2. Zmieniaj TYLKO funkcję `buildPreview` — nic poza nią
3. `youtube_hashtags` to **array** — join przed pushem do stringa

---

## 🔍 CO NAPRAWIAĆ I GDZIE

### Plik: `web/src/app/dashboard/YouTubePublishModal.tsx`

W funkcji `buildPreview` (dodanej przez poprzedni dispatch) występuje `[object Object]`
ponieważ:
- Rozdziały (`chapters`) są pushowane jako array zamiast jako sformatowany string
- Hashtagi (`youtube_hashtags`) są array i też nie są joinowane

### Poprawna implementacja `buildPreview`

Zastąp całą funkcję `buildPreview` (i/lub `useEffect` który ją woła) tym kodem:

```typescript
const buildPreview = (): string => {
  const parts: string[] = []

  // M1 body
  if (schemaData?.youtube_description_body) {
    parts.push(schemaData.youtube_description_body)
  }

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
```

### Gdzie to wywolać

Funkcja `buildPreview` powinna być wywołana w momencie gdy user kliknie "Podgląd"
LUB gdy `selected` się zmieni (useEffect).

Sprawdź jak jest wywoływana w aktualnym kodzie i dostosuj — nie zmieniaj logiki włączania/wyłączania podglądu, tylko zastąp implementację funkcji.

---

## ✅ DEFINITION OF DONE

- [ ] Brak `[object Object]` w podglądzie
- [ ] Rozdziały wyświetlane jako `MM:SS Tytuł` (jeden per linia, poprzedzone `ROZDZIAŁY:`)
- [ ] Hashtagi jako `#tag1,#tag2,...` (string)
- [ ] Commit na GitHub MCP
- [ ] **BEZ DEPLOY** — deploy dopiero po dispatchu 4/4
- [ ] Brak błędów TypeScript

---

## 📨 RAPORT

```
video-seo-engine/.agents/reports/2026-07-13_vse-dev_bugfix-object-object.md
sonic-void/.agents/reports/inbox/2026-07-13_vse-dev_bugfix-object-object.md
```

Raport musi zawierać:
- SHA commitu
- Czy pojawiły się błędy TypeScript
- Co dokładnie zmieniono (linie przed/po)

---

*Supervisor 01 | sonic-void | 2026-07-13 | dispatch 2/4*
