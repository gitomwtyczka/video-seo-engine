# Raport: vse-dev-13 — Format "Film" + VTT badge link

**Agent:** vse-dev-13 | video-seo-engine  
**Data:** 2026-06-17  
**Status:** ✅ Zakończone  

---

## Wykonane zadania

### Zadanie 1: Format "Film" w modalu publikacji

**CO:** Dodano dropdown "Format wpisu WordPress" w `InjectModal` na dashboardzie.

**PO CO:** WordPress rozróżnia formaty postów (standard, video, gallery, quote).
Artykuły video SEO powinny mieć format `video` — wpływa to na motyw i prezentację.
Dashboard domyślnie ustawia "Film (video)" jako optymalny format.

**JAK:**
- Frontend: nowy `postFormat` state w `InjectModal` + dropdown z 4 opcjami
- API: pole `post_format` w `InjectRequest` (default: `video`)
- Pipeline: `run_inject()` → `_create_wp_post()` → `"format": post_format` w WP REST API payload
- Logowanie: format widoczny w logach inject pipeline

**Pliki:**
- `web/src/app/dashboard/dashboard-inner.tsx` — dropdown + state + payload
- `api/models/request.py` — `post_format: str = "video"`
- `api/routers/inject.py` — przekazanie `post_format` do `run_inject()`
- `api/services/pipeline.py` — `_create_wp_post()` + `run_inject()` + format w WP payload

### Zadanie 2: VTT badge → klikalny link

**CO:** Badge VTT w `/historia` jest teraz klikalnym linkiem do pobrania pliku transkrypcji.

**PO CO:** Użytkownik widział badge VTT ale nie mógł zobaczyć zawartości transkryptu.
Teraz kliknięcie badge'a otwiera plik VTT w nowej karcie — można go przeczytać
lub pobrać.

**JAK:**
- Nowy endpoint: `GET /v1/jobs/{id}/vtt` w `api/routers/jobs.py`
- Konwertuje __VTT__ runner format → prawdziwy WebVTT (reużycie `_vtt_runner_to_webvtt`)
- Plain text transkrypty serwowane jako `text/plain`
- Content-Disposition: inline z filename bazowanym na video_id
- Frontend: badge zmieniony z `<span>` na `<a>` z ikoną download i hover effectem

**Pliki:**
- `api/routers/jobs.py` — nowy endpoint `get_job_vtt()`
- `web/src/app/historia/page.tsx` — badge VTT jako `<a>` link

---

## Commity

| SHA | Opis |
|-----|------|
| `1fd9416` | feat: add Film post format selector + VTT badge link (backend) |
| `49d4784` | feat: VTT download endpoint + VTT badge clickable link |
| `63a1c08` | feat: Film format selector in InjectModal |

---

## Weryfikacja

- Deploy Docker: ✅ oba kontenery (vse-api + vse-web) przebudowane i działają
- Endpoint `/v1/jobs/{job_id}/vtt`: ✅ widoczny w OpenAPI
- Pole `post_format` w `/v1/inject`: ✅ widoczne w OpenAPI schema
- Kompatybilność wsteczna: ✅ — `post_format` ma default value `"video"`
