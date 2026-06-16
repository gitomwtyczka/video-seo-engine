# Raport Implementacyjny: VTT Rozdziały / Admin 500 / Historia / Debug Logging

**Agent:** `vse-dev-11` | **Data:** 2026-06-16  
**Dispatch:** Supervisor 03 | **Rola:** Implementacja  
**Na podstawie diagnozy:** vse-analyst-02

---

## Podsumowanie

| Fix | Commit | Plik | Status |
|-----|--------|------|--------|
| 1. Rozdziały (label/time mapping) | `9753aa9` | `dashboard-inner.tsx` | ✅ |
| 2. Admin HTTP 500 (selectinload) | `5557f5e` | `admin.py` | ✅ |
| 3. Historia tytuł klikalny | `4e274b9` | `historia/page.tsx` | ✅ |
| 4. Debug middleware + model | `0d2aedc` `639b106` | `app_settings.py` + `error_logging.py` | ✅ |
| 5. Admin debug-mode endpoints | `a855377` | `admin.py` | ✅ |
| 6. Main.py rejestracja middleware | `f551d9a` | `main.py` | ✅ |
| 7. Admin UI debug toggle | `bb2de3d` | `admin/page.tsx` | ✅ |

Deploy: `git pull + docker compose up -d --build vse-api vse-web`

---

## Fix 1 — Rozdziały

**Zmiana:** `extractChapters()` w `dashboard-inner.tsx` teraz mapuje `label→name`, `time→startOffset`.

Dodano do `ChapterItem` interface pola `label?` i `time?` (backward-compatible).
Rendering: `ch.startOffset ?? ch.time` i `ch.name ?? ch.label`.
`chaptersToText()` i format YT również zaktualizowane.

**Efekt:** Istniejące joby z 14 rozdziałami pokazują prawidłowe tytuły i timestampy.

---

## Fix 2 — Admin HTTP 500

**Zmiana:** `api/routers/admin.py` — dodano `from sqlalchemy.orm import selectinload`
i `.options(selectinload(User.plan))` do 3 queries: `list_users()`, `get_user()`, `change_user_plan()`.

**Efekt:** `/v1/admin/users` zwraca 200 zamiast 500.

---

## Fix 3 — Historia tytuł klikalny

**Zmiana:** `web/src/app/historia/page.tsx` — tytuł joba zamieniony z `<p>` na `<a href={job.video_url}>`
z `target="_blank"` i `hover:text-violet-400` efektem.

**Efekt:** Kliknięcie tytułu otwiera YouTube w nowej karcie.

---

## Fix 4 — Debug Logging + Toggle

### Nowe pliki:
- `api/models/app_settings.py` — model tabeli `app_settings` (key/value)
- `api/middleware/error_logging.py` — `ErrorLoggingMiddleware` logujący 5xx + tryb debug

### Zmiany:
- `api/routers/admin.py` — nowe endpointy `GET/POST /v1/admin/debug-mode`
- `api/main.py` — rejestracja `ErrorLoggingMiddleware` + import `AppSettings` w startup
- `web/src/app/admin/page.tsx` — sekcja "Ustawienia systemu" z `DebugModeToggle`

### Zachowanie:
- Middleware loguje ERROR dla każdego 5xx z pełną traceback
- Gdy `DEBUG_MODE=true` (env lub BD) — loguje każdy request (INFO)
- Toggle w panelu admina: `GET debug-mode` przy mount, `POST` przy kliknięciu
- `os.environ["DEBUG_MODE"]` ustawiany live (działa bez restartu kontenera)
- Tabela `app_settings` tworzona automatycznie przez `create_all` przy starcie

---

## Deploy

```
cd /home/ubuntu/video-seo-engine
git pull origin main
docker compose -f docker-compose.vse.yml up -d --build vse-api vse-web
```

---

*[vse-dev-11 | video-seo-engine 16.06.2026 23:40] — raport kompletny*