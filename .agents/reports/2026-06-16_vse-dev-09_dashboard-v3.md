# Raport: vse-dev-09 — Dashboard UI v3

**Data:** 2026-06-16  
**Callsign:** vse-dev-09  
**Temat:** Dashboard UI — v2+v3 (zakładki, historia, ustawienia, WP panel)  
**Status:** ✅ Wszystkie zadania zakończone, deploy live

---

## Co zrobiono

### Commity

| SHA | Opis |
|-----|------|
| `69e4196` | fix: NEXT_PUBLIC_API_URL in docker-compose |
| `9832cac` | feat: dashboard tabs (Schemat/Artykuł/Rozdziały) + InjectModal |
| `fee9f94` | feat: GET /v1/jobs/history endpoint |
| `dbe6b53` | feat: /historia page — job history from PostgreSQL |
| `d18ea62` | feat: /ustawienia placeholder page |
| `4a0ab25` | feat: middleware protects /historia and /ustawienia routes |
| `2ba71f3` | feat: sidebar Link navigation + WP panel always visible |

### Szczegóły implementacji

1. **Endpoint GET /v1/jobs/history** (`api/routers/jobs.py`):
   - Paginacja: `limit` (max 200) + `offset`
   - Ekstrakcja `video_id` z URL (thumbnail YT na froncie)
   - Flaga `has_vtt` — czy transkrypt w formacie VTT
   - Sortowanie: najnowsze pierwsze

2. **Strona /historia** (`web/src/app/historia/page.tsx`):
   - Fetch z GET /v1/jobs/history
   - Thumbnail YT, badge statusu, daty, link do YouTube
   - Sidebar spójny z dashboardem

3. **Strona /ustawienia** (`web/src/app/ustawienia/page.tsx`):
   - Placeholder "W trakcie budowy" z info o Fazie 5 (WP) i 7 (YouTube OAuth)

4. **Dashboard** (`web/src/app/dashboard/page.tsx`):
   - NavItem `<button>` → `<Link href>` (działająca nawigacja)
   - `WpQuickPanel` — collapsible panel konfiguracji WP widoczny OD RAZU
   - Credentials zapamiętane w localStorage, status połączenia

5. **Middleware** (`web/src/middleware.ts`):
   - Dodane `/historia/:path*` i `/ustawienia/:path*` do matcher

### Diagnoza VTT timestamps
- `pipeline.py` poprawnie konwertuje format `__VTT__` na WebVTT
- Starsze joby (bez VTT) to artefakt starego runnera przed v2.0
- Nowe joby mają `has_vtt: true` — potwierdzono w produkcji

## Weryfikacja

- ✅ Kontenery: vse-web, vse-api, vse-postgres — UP
- ✅ GET /v1/jobs/history — zwraca dane z `video_id`, `has_vtt`
- ✅ Deploy live na https://vse.impresjapr.pl

---

*[vse-dev-09 | video-seo-engine 16.06.2026 20:42] — raport kompletny*
