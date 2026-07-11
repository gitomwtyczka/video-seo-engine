# Audyt: Zakładka YouTube w dashboardzie

**vse-analyst-01 | 2026-07-11**

---

## Status implementacji

- [ ] Nie istnieje — trzeba zbudować od zera
- [ ] Częściowo — backend jest, frontend brakuje
- [ ] Częściowo — frontend jest, backend brakuje
- [ ] Istnieje ale nie jest widoczne w nawigacji
- [x] **Zakładka YouTube (harmonogram/kolejka/historia) NIE ISTNIEJE — trzeba zbudować od zera**

**Uwaga:** Istnieje częściowa integracja YT jako element `InjectModal` w dashboard (checkbox wyboru kanału YouTube przy publikacji na WP), ale nie jest to osobna zakładka YT.

---

## Frontend — znalezione pliki i komponenty

### Struktura stron (web/src/app/)
- `/dashboard` — główna strona dashboardu
- `/historia` — historia jobów SEO (transcript_jobs)
- `/ustawienia` — ustawienia użytkownika (zawiera integracja YouTube OAuth)
- `/cennik`, `/platnosci`, `/regulamin`, `/polityka-prywatnosci`, `/login`, `/register`, `/admin`

**Brak katalogu:** `web/src/app/youtube/` lub podobnego

### Sidebar nawigacji (dashboard-inner.tsx, linia 2505–2513)
```tsx
<NavItem icon="grid" label="Dashboard" href="/dashboard" active />
<NavItem icon="clock" label="Historia" href="/historia" />
<NavItem icon="settings" label="Ustawienia" href="/ustawienia" />
```
**Brak pozycji YouTube w nawigacji.**

### Istniejące elementy YT w dashboard-inner.tsx
- `InjectModal` (linia 742–1145): lista checkboxów podłączonych kanałów YouTube jako opcjonalny element przy publikacji na WP
  - Fetchuje `GET /v1/youtube/channels` — działa
  - Wyświetla kanały z opcją zaznaczenia
  - **Nie wysła jednak danych YT channels do backendu** (selectedYtChannelIds nie jest przekazywane do `handlePublish`)
- Placeholder w sidebardzie (linia 3662): ‘{ icon: '🚀', label: 'Auto-publish', desc: 'Plan Pro/Agency' }‘ — jest w liście feature preview, ale NIE jest pozycją nav

---

## Backend — znalezione endpointy

### api/routers/youtube.py
| Endpoint | Metoda | Opis |
|---|---|---|
| `/v1/youtube/oauth/login` | GET | Inicjuje OAuth flow Google |
| `/v1/youtube/oauth/callback` | GET | Callback OAuth — zapisuje refresh_token |
| `/v1/youtube/channels` | GET | Lista aktywnych kanałów usera |
| `/v1/youtube/channels/{channel_id}` | DELETE | Rozłączenie kanału |

**Brak endpointów dla:**
- Harmonogramu publikacji YT
- Kolejki materiałów YT
- Historii publikacji na YT
- Statusu pipeline YT
- Upload wideo na YT
- Aktualizacji opisu/metas na YT

### Inne routery (pełna lista api/routers/)
`admin.py`, `auth.py`, `generate.py`, `inject.py`, `jobs.py`, `monitor.py`, `payments.py`, `portals.py`, `process.py`, `profiles.py`, `sitemap.py`, `users.py`, `youtube.py`

**Brak plików:** `youtube_schedule.py`, `youtube_queue.py`, `youtube_history.py`

### Grep: schedule/publish/queue w codebase
- `api/core/fetcher.py` — ma wzmianki o “publish” (YouTube API data fetch)
- `api/services/pipeline.py` — “publish” w kontekście WP inject
- `api/routers/monitor.py` — monitoring kanału YT (RSS, nie scheduling)
- `api/routers/profiles.py` — `schedule` jako typ publikacji SEO (nie YT scheduling)
- `api/models/request.py` — modele request zawierają pola publikacji WP

---

## DB — tabele powiązane z YT

### Wszystkie tabele (PostgreSQL — zweryfikowane live SSH)
```
 api_keys         | table
 app_settings     | table
 oauth_states     | table
 plans            | table
 transcript_jobs  | table
 usage_logs       | table
 users            | table
 wp_portals       | table
 youtube_channels | table
```

**youtube_channels** — istnieje, zawiera:
- `id`, `user_id`, `youtube_channel_id`, `title`, `refresh_token` (zaszyfrowany), `is_active`, `created_at`
- **Cel:** tylko OAuth — przechowuje połączenie kanału do integracji WP inject
- **Brak tabel:** `youtube_schedule`, `youtube_queue`, `youtube_publish_history`, `youtube_videos`

---

## Dashboard — aktualne sekcje

### Sidebar (3 pozycje)
1. **Dashboard** (`/dashboard`) — generator SEO z URL YouTube
2. **Historia** (`/historia`) — historia wygenerowanych jobów
3. **Ustawienia** (`/ustawienia`) — YouTube OAuth connect, WP portale

### Zawartość /dashboard
- Input URL YouTube + przycisk “Generuj”
- Wyniki w 3 zakładkach: **Schemat** (JSON-LD), **Artykuł** (tekst), **Rozdziały** (timestamps)
- Sekcja publikacji (Pro/Agency): dropdown portalów WP + `InjectModal`
- W `InjectModal`: opcjonalna lista kanałów YouTube do zaznaczenia

### /ustawienia (pośrednio YT)
- Integracja YouTube: OAuth login, lista podłączonych kanałów, rozłączanie

---

## Wniosek

Zakładka YouTube (harmonogram, kolejka, historia publikacji YT) **nie istnieje** na żadnym poziomie stosu:

| Warstwa | Status |
|---|---|
| Frontend — osobna strona/zakładka YT | ❌ Brak |
| Frontend — pozycja w sidebar | ❌ Brak |
| Backend — endpointy scheduling/queue/history YT | ❌ Brak |
| DB — tabele dla YT schedule/history | ❌ Brak |
| Frontend — wyświetlanie kanałów YT (w InjectModal) | ✅ Istnieje |
| Backend — OAuth + CRUD kanałów YT | ✅ Istnieje |
| DB — tabela youtube_channels | ✅ Istnieje |

**Istniejąca integracja YT** ogranicza się do:
1. OAuth — podłączanie kanału YouTube konta Google
2. Lista kanałów w `InjectModal` (checkbox — bez funkcjonalnego działania, `selectedYtChannelIds` nie trafia do backendu)

---

## Szacunek zakresu pracy

**Rozmiar: DUZY** (nowa funkcjonalność end-to-end)

### Co trzeba zbudować

#### Backend
- `api/routers/youtube_publish.py` — endpoint `POST /v1/youtube/publish` (update opisu/metas na YT)
- `api/routers/youtube_schedule.py` — harmonogram publikacji
- `api/models/youtube_publish_job.py` — model tabeli
- Migracja DB: tabela `youtube_publish_jobs` (video_id, channel_id, status, scheduled_at, published_at)
- Integracja z YouTube Data API v3 (videos.update — scope `youtube.force-ssl` już jest)

#### Frontend
- `web/src/app/youtube/page.tsx` — nowa strona
- Komponenty: harmonogram, kolejka, historia
- Pozycja “YouTube” w sidebar
- Podpięcie `selectedYtChannelIds` w `handlePublish` (InjectModal)

### Główne pliki do stworzenia
```
api/routers/youtube_publish.py (NOWY)
api/models/youtube_publish_job.py (NOWY)
alembic/versions/xxx_add_youtube_publish_jobs.py (NOWY)
web/src/app/youtube/page.tsx (NOWY)
web/src/app/youtube/dashboard-inner.tsx (NOWY)
web/src/app/dashboard/dashboard-inner.tsx (MODYFIKACJA — sidebar + InjectModal fix)
```

### Czas szacunkowy
- Backend (endpointy + migracja): ~1 sesja agenta
- Frontend (strona + komponenty): ~1-2 sesje agenta
- Integracja + testy: ~0.5 sesji

---

## Bug zidentyfikowany (bonus)

`selectedYtChannelIds` w `InjectModal` jest zbierany przez checkboxy, ale **nie jest przekazywany do `body` w `handlePublish`** (brak `youtube_channel_ids: selectedYtChannelIds` w body payloadu do `/v1/inject`). Integracja YT w InjectModal jest wizualnie gotowa, ale niedłączona do backendu.

---

*[vse-analyst-01 | video-seo-engine 2026-07-11] raport kompletny*
