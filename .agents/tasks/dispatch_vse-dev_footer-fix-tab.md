# DISPATCH B — vse-dev | Fix stopki + zakładka + deploy

**Data:** 2026-07-13  
**Od:** Supervisor 01  
**Do:** vse-dev  
**Zakres:** 2 pliki + deploy. Zmiany małe i precyzyjne.

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

1. Przed edycją każdego pliku pobierz SHA przez `get_file_contents`
2. `dashboard-inner.tsx` jest duży (~88KB) — sprawdzaj fragmenty, nie cały plik
3. Deploy dopiero po OBU commitach
4. SSH deploy: `ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100`

---

## 🎯 ZADANIE 1 — Fix stopki (root cause z diagnostyki)

### Plik: `web/src/app/ustawienia/page.tsx`

**Problem:** `FooterTextEditor` wysyła PUT na `channel.channel_id` (YouTube UC... ID),
a backend szuka po `channel.id` (wewnętrznym UUID bazy). 404, zapis nie trafia do DB.
Frontend nie sprawdza `res.ok` więc pokazuje "✔ Zapisano" mimo błędu.

**Fix 1 — zły URL:**
```typescript
// PRZED:
await fetch(`${apiUrl}/v1/youtube/channels/${channel.channel_id}`, {

// PO:
await fetch(`${apiUrl}/v1/youtube/channels/${channel.id}`, {
```

**Fix 2 — brak walidacji odpowiedzi:**
```typescript
// PRZED (brak sprawdzenia):
const res = await fetch(...)
setSaved(true)

// PO:
const res = await fetch(...)
if (!res.ok) {
  const err = await res.json().catch(() => ({}))
  throw new Error(err.detail || `HTTP ${res.status}`)
}
setSaved(true)
```

**Dodaj obsługę błędu w UI:**
```typescript
// Dodaj stan:
const [error, setError] = useState<string>('')

// W catch:
} catch (e: any) {
  setError(e.message || 'Błąd zapisu')
} finally {
  setSaving(false)
}

// W JSX, pod przyciskiem "Zapisz stopkę":
{error && <p className="text-xs text-red-400 mt-1">{error}</p>}
```

> Uwaga: Sprawdź czy `channel.id` (UUID) jest zwracany przez GET /v1/youtube/channels.
> Z raportu analityka wynika że TAK — widoczne jako `"id"` w słowniku:
> `{"id": str(ch.id), "channel_id": ch.youtube_channel_id, ...}`
> Więc frontend musi mieć `channel.id` w obiekcie. Jeśli typ `Channel` go nie zawiera — dodaj pole.

---

## 🎯 ZADANIE 2 — Zakładka "Opis YouTube" (dispatch 3/4 nie został wdrożony)

### Plik: `web/src/app/dashboard/dashboard-inner.tsx`

Zacznij od przeczytania dispatcha 3/4 który zawiera pełną specyfikację:
```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: video-seo-engine
  branch: main
  path: .agents/tasks/dispatch_vse-dev_yt-tab.md
```

Zaimplementuj wszystkie 7 zmian z tego dispatcha.
Sprawdź aktualny stan pliku przez `get_file_contents` — część zmian mogła już być dodana.
Nie nadpisuj tego co już jest — dopisuj tylko brakujące elementy.

**Kluczowy warunek:** Zakładka "Opis YouTube" musi być widoczna obok Schemat/Artykuł/Rozdziały po wygenerowaniu.

---

## 🚀 DEPLOY (po OBIE commitach)

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web"
```

Po deployu sprawdź logi:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "docker logs vse-web --tail 20"
```

---

## ✅ DEFINITION OF DONE

- [ ] `channel.id` zamiast `channel.channel_id` w URL PUT
- [ ] Walidacja `res.ok` + komunikat błędu w UI
- [ ] Zakładka "Opis YouTube" widoczna w panelu po wygenerowaniu
- [ ] Deploy zakończony bez błędów
- [ ] Logi nie pokazują ERROR

---

## 📨 RAPORT

```
video-seo-engine/.agents/reports/2026-07-13_vse-dev_footer-fix-tab.md
sonic-void/.agents/reports/inbox/2026-07-13_vse-dev_footer-fix-tab.md
```

Zawartość: SHA commitów obu plików, wynik deploy, logi.

---

*Supervisor 01 | sonic-void | 2026-07-13*
