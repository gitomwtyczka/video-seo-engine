# DISPATCH — vse-dev | Fix: zakładka + body + override

**Data:** 2026-07-13  
**Od:** Supervisor 01  
**Do:** vse-dev  
**Zakres:** 3 precyzyjne zmiany w 3 plikach + deploy

---

## ⚡ KROK 0

```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: sonic-void
  branch: master
  path: .agents/protocols/dispatch-system-block.md
```
Heartbeat do `video-seo-engine/.agents/heartbeat.json`.

---

## ⚠️ ZNANE PUŁAPKI

1. `dashboard-inner.tsx` to ~88KB i 5000+ linii. GitHub MCP (`get_file_contents`) może go obrać.
   **Jeśli plik jest obcięty** — użyj `gh api` lub pobierz przez `download_url`:
   ```powershell
   ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
     "grep -n 'youtube\|tabs\|TabKey' /home/ubuntu/video-seo-engine/web/src/app/dashboard/dashboard-inner.tsx | head -50"
   ```
   To da ci kontekst bez ładowania całego pliku.

2. Przed każdą edycją: pobierz SHA przez `get_file_contents`
3. Commit przez GitHub MCP, nie git push

---

## 🎯 FIX 1 — Zakładka (dashboard-inner.tsx, ~L1217)

**Diagnoza:** `TabKey` zawiera `'youtube'` (L357), render block istnieje (L7091), ale tablica `tabs` w `TabBar` **nie ma wpisu** (L1217).

**Działanie:**

Znajdź w pliku tablicę `tabs` (około linii 1217). Wygląda mniej więcej tak:
```typescript
const tabs = [
  { key: 'schema', label: 'Schemat' },
  { key: 'article', label: 'Artykuł', badge: ... },
  { key: 'chapters', label: 'Rozdziały', badge: ... },
]
```

Dodaj na końcu tablicy:
```typescript
  { key: 'youtube', label: 'Opis YouTube' },
```

Sposobób weryfikacji przed edycją (SSH grep):
```powershell
ssh ... "grep -n \"key: 'schema'\|key: 'article'\|key: 'chapters'\|key: 'youtube'\" /home/ubuntu/video-seo-engine/web/src/app/dashboard/dashboard-inner.tsx"
```
Jeśli `youtube` już jest — nie dodawaj. Jeśli nie ma — dodaj.

---

## 🎯 FIX 2 — Body w podglądzie (YouTubePublishModal.tsx + buildYtDescription)

**Diagnoza:** Backend generuje `video_description` (nie `youtube_description_body`). Frontend szuka `youtube_description_body` które jest `undefined`.

**Działanie — 2 miejsca:**

### A) W `YouTubePublishModal.tsx` — funkcja `buildPreview`

Zmień M1 — jeśli `youtube_description_body` jest undefined, fallback na `video_description`:
```typescript
// PRZED:
if (schemaData?.youtube_description_body) parts.push(schemaData.youtube_description_body)

// PO:
const body = schemaData?.youtube_description_body
  ?? schemaData?.youtube_description_hook
  ?? schemaData?.video_description
  ?? ''
if (body) parts.push(body as string)
```

Analogicznie dla mid_cta i credits — jeśli są puste, po prostu ich nie dodawaj (już jest `if`).

### B) W `dashboard-inner.tsx` — funkcja `buildYtDescription`

Ta sama zmiana M1:
```typescript
const body = schema?.youtube_description_body
  ?? schema?.youtube_description_hook
  ?? schema?.video_description
  ?? ''
if (body) parts.push(body as string)
```

---

## 🎯 FIX 3 — Override nie trafia na YouTube (youtube.py)

**Diagnoza:** Frontend wysyła `override_description` (linia 146 w modalu) ale backend go gubi.

**Działanie:**

Sprawdź w `api/routers/youtube.py` endpoint `POST /v1/youtube/publish-description`:

```python
# Znajdź funkcję publish_description (lub podobną)
# Sprawdź czy override_description jest w modelu requestu
# Sprawdź czy jest używane przy budowaniu opisu

# Jeśli nie — dodaj:
if req.override_description:
    description = req.override_description
else:
    description = build_yt_description(...)  # istniejąca logika
```

Sprawdź też model `YouTubePublishRequest` w `api/models/request.py`:
```python
class YouTubePublishRequest(BaseModel):
    # ...
    override_description: Optional[str] = None  # czy istnieje?
```
Jeśli nie istnieje — dodaj.

---

## 🚀 DEPLOY (po WSZYSTKICH commitach)

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build"
```

Sprawdź logi:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "docker logs vse-web --tail 10 && docker logs vse-api --tail 10"
```

---

## ✅ DEFINITION OF DONE

- [ ] Zakładka "Opis YouTube" widoczna po wygenerowaniu
- [ ] Body (M1) pojawia się w podglądzie (z fallback na `video_description`)
- [ ] Opis wysłany na YouTube = to co było w podglądzie (override działa)
- [ ] Deploy bez błędów

---

## 📨 RAPORT

```
video-seo-engine/.agents/reports/2026-07-13_vse-dev_fix-tab-body-override.md
sonic-void/.agents/reports/inbox/2026-07-13_vse-dev_fix-tab-body-override.md
```

Zawartość: SHA commitów, co dokładnie zmieniono w każdym pliku, wynik deploy.

---

*Supervisor 01 | sonic-void | 2026-07-13*
