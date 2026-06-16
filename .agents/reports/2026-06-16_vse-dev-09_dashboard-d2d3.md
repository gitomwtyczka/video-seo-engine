# Raport: vse-dev-09 — Dashboard UI D2+D3 + API URL Fix

**Data:** 2026-06-16  
**Callsign:** vse-dev-09  
**Workspace:** video-seo-engine  
**Status:** ✅ KOMPLETNY

---

## Deliverable

### ETAP 1 — Fix NEXT_PUBLIC_API_URL
**Commit:** `69e4196`  
**Problem:** `docker-compose.vse.yml` miał `NEXT_PUBLIC_API_URL=https://vse.impresjapr.pl/api` — fetch frontend szło na `/api/v1/generate` co nginx nie routował do FastAPI poprawnie (404).  
**Fix:** Usunięcie sufiksu `/api` → `NEXT_PUBLIC_API_URL=https://vse.impresjapr.pl`  
**Weryfikacja:** `curl /v1/admin/users` zwraca `401` (zamiast `404`) — poprawne, endpoint jest osiągalny.

### ETAP 2 — D2: Zakładki Schemat / Artykuł / Rozdziały
**Commit:** `9832cac`  
**Co zmieniono:**
- Dodano 3-zakładkowy system tabów: **Schemat** | **Artykuł** | **Rozdziały**
- **Tab Schemat:** Tytuł, Meta description, pełny JSON-LD z przyciskiem Kopiuj
- **Tab Artykuł:** Lead/Wstęp, Treść artykułu, Cytaty (blockquote), FAQ (rozwijane) + "Kopiuj cały artykuł"
- **Tab Rozdziały:** Lista [MM:SS] z tytułami + sekcja "Format YouTube" (do wklejenia w opis YT)
- Badge z liczbą elementów na każdej zakładce

### ETAP 3 — D3: Inject One-Click Modal
**Commit:** `9832cac`  
**Co zmieniono:**
- Zastąpiono inline `PublishSection` modalem `InjectModal` z overlay + backdrop blur
- Pola: WP URL, User, Application Password, opcjonalny Post ID, status draft/publish
- **localStorage persist** — credentials zapamiętywane między sesjami
- `wp_post_id = null` → tworzenie nowego posta (POST), podany ID → aktualizacja
- Wynik z linkiem do opublikowanego posta WP
- Zamykanie modala: Escape, klik poza, przycisk X
- Przycisk "🚀 Wyślij do portalu" w nagłówku wyników i w pasku akcji na dole

### ETAP 4 — Deploy + Weryfikacja
**Deploy:** `git pull origin main && docker compose up -d --build vse-web` na VPS  
**Wyniki:**
- ✅ Kontenery `vse-web`, `vse-api`, `vse-postgres` — Up, Healthy
- ✅ `/dashboard` — ładuje poprawnie, formularz widoczny, plan Agency
- ✅ `/admin` — redirect do /login (poprawne bez sesji)
- ✅ `/v1/admin/users` — HTTP 401 (fix działa! było 404)
- ✅ Landing page — bez błędów

---

## Pliki zmienione

| Plik | Zmiana |
|------|--------|
| `docker-compose.vse.yml` | NEXT_PUBLIC_API_URL: usunięcie `/api` |
| `web/src/app/dashboard/page.tsx` | 3 taby, InjectModal, localStorage, nowe typy |

## Commity

- `69e4196` — fix: NEXT_PUBLIC_API_URL remove /api suffix
- `9832cac` — feat: D2 tabbed dashboard + D3 inject modal with localStorage

---

*[vse-dev-09 | video-seo-engine 16.06.2026 20:02] — raport kompletny*
