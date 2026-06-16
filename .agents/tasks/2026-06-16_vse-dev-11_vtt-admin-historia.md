## ⚡ KROK 0

**Callsign:** `[vse-dev-11 | video-seo-engine]` | Model: Claude Sonnet

---

# TASK: vse-dev-11 — VTT Fix + Admin 500 + Historia UX

**Data:** 2026-06-16 | **Dispatch:** Supervisor 03

---

## 📚 KROK 0b — Kontekst projektu (OBOWIĄZKOWE)

Przeczytaj przez GitHub MCP przed star tem:
1. `docs/ARCHITECTURE.md`
2. `ROADMAP.md`

---

## Deliverables:

1. Rozdziały: `(bez tytułu)` → prawdziwe tytuły i czasy
2. Admin panel: HTTP 500 → działająca lista użytkowników
3. Historia: klikalne linki + działający `YT →` button

---

## ETAP 1 — VTT: rozdziały `(bez tytułu)`

### Kontekst (nie odkrywaj ponownie):
Backend poprawnie wykrywa 14 rozdziałów (badge pokazuje `Rozdziały 14`), ale frontend renderuje `?` i `(bez tytułu)` zamiast tytułów i timestampów.

### Diagnoza — krok 1: sprawdz co jest w DB

```powershell
# Ustal nazwy kontenerów:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker ps --format '{{.Names}}'"

# Sprawdź schema_data.chapters w ostatnim gotowym jobie:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker exec [DB_CONTAINER] psql -U [USER] -d [DB] -c \"SELECT id, schema_data->'chapters' FROM transcript_jobs WHERE status='completed' ORDER BY created_at DESC LIMIT 1;\""
```

**Przypadek A:** DB ma puste `title`/`start_time` → bug w backend pipeline.py
**Przypadek B:** DB ma dane ale frontend źle parsuje → bug w page.tsx

### Diagnoza — krok 2: sprawdź format chapter w DB

Oczekiwany format chapter w `schema_data.chapters`:
```json
{"start_time": 135, "title": "Tytuł rozdziału"}
```

Jeśli masz `{"start_time": 0, "title": ""}` → pipeline.py nie parsuje VTT poprawnie.

### Sprawdź `api/services/pipeline.py` (GitHub MCP):
- Sekcja parsowania `__VTT__` — czy regex wyciąga czas i tytuł
- Format runnerów: `00:15 Tytuł` lub `00:00:15 Tytuł` — obsłuż oba

### Sprawdź `web/src/app/dashboard/page.tsx` (GitHub MCP):
- Sekcja renderowania zakładki Rozdziały
- Czy pole `chapter.title` i `chapter.start_time` są poprawnie odczytywane
- Konwersja `start_time` (sekundy?) na `MM:SS`

---

## ETAP 2 — Admin panel HTTP 500

### Kontekst:
Panel administracyjny ładuje się (HTML dziaa, redirect do /login bez sesji działa). Po zalogowaniu: `Users API: HTTP 500`.

### Diagnoza:

```powershell
# Logi api podczas requesta:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker logs vse-api --tail 50 2>&1"

# Test endpointu bezpośrednio z tokenem (pobierz token z /v1/auth/google/token-exchange lub zrób test bez):
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "curl -s https://vse.impresjapr.pl/v1/admin/users -H 'Authorization: Bearer TEST' | head -200"
```

Sprawdź `api/routers/admin.py` (GitHub MCP) — czy endpoint używa lazy loading który może powodować `MissingGreenlet` (ten sam bug co w dev-08 z `get_current_user`).

Jeśli tak — dodaj `selectinload(User.plan)` analogicznie do fixa dev-08 w `api/auth.py`.

---

## ETAP 3 — Historia: klikalne linki + YT button

### Problem:
- Link pod tytułem nie klika
- `YT →` button prawdopodobnie nie ma href

### Fix w `web/src/app/historia/page.tsx` (GitHub MCP):

```tsx
// Link pod tytułem:
<a href={job.youtube_url} target="_blank" rel="noopener">
  {job.youtube_url}
</a>

// YT → button:
<a href={job.youtube_url} target="_blank" className="yt-button">
  YT →
</a>
```

---

## ETAP 4 — Deploy i weryfikacja

```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "cd /opt/vse && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-api vse-web"
```

Weryfikacja:
1. Rozdziały: tytuły i czasy `[02:15]` zamiast `(bez tytułu)`
2. Admin: lista użytkowników ładuje się
3. Historia: link i YT button klikalne

---

## Dostęp

- GitHub MCP: `gitomwtyczka/video-seo-engine` branch `main`
- SSH: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100`
- **FILE BRIDGE/Wetty: ZAKAZ**

---

## Raport (dual-write):

1. `video-seo-engine/.agents/reports/2026-06-16_vse-dev-11_vtt-admin-historia.md`
2. `sonic-void/.agents/reports/inbox/2026-06-16_vse-dev-11_vtt-admin-historia.md`

```
[vse-dev-11 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[vse-dev-11 | video-seo-engine DD.MM.YYYY HH:MM] — status
```

*Supervisor 03 | sonic-void | 2026-06-16 22:35*
