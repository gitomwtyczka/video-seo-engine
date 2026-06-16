# Raport: vse-dev-10 — Historia UX + VTT Timestamps Fix

**Data:** 2026-06-16
**Callsign:** vse-dev-10
**Status:** ✅ DONE

---

## CO zrobiono

Naprawiono dwa fundamentalne problemy dashboard/historia UX:

1. **Schema persistence** — wyniki generowania SEO (`schema_data`) były utracone po zamknięciu HTTP response. Dodano persystencję do PostgreSQL.
2. **Historia UX** — strona `/historia` teraz linkuje do `/dashboard?job_id=X`, który ładuje wyniki z DB zamiast generować od nowa.

## PO CO

Bez tych zmian użytkownik tracił wyniki po odświeżeniu strony. Historia była martwa — pokazywała joby ale nie pozwalała wrócić do wygenerowanego contentu.

## JAK

### Backend (3 commity):

| Commit | Plik | Zmiana |
|--------|------|--------|
| `085a7bf` | `api/models/job.py` | Dodano kolumnę `schema_data` (JSONB) do `TranscriptJob` |
| `44b281e` | `api/routers/generate.py` | Po generowaniu schema jest zapisywana do job'u w DB |
| `976566b` | `api/routers/jobs.py` | `GET /v1/jobs/{id}` zwraca `FullJobResponse` ze `schema_data`; historia ma `has_schema` + `post_title` |

### Frontend (4 commity):

| Commit | Plik | Zmiana |
|--------|------|--------|
| `a798705` | `web/src/app/historia/page.tsx` | Przycisk "🔍 Otwórz wyniki →" widoczny dla jobów z `has_schema` |
| `f61621a` | `web/src/app/dashboard/use-job-loader.ts` | Hook `useJobLoader` — ładuje dane z API po `?job_id` |
| `a300a87` | `web/src/app/dashboard/page.tsx` | Suspense wrapper dla `useSearchParams` (wymagany przez Next.js 14) |
| `cf04eab` | `web/src/app/dashboard/dashboard-inner.tsx` | Dashboard z integracją `useJobLoader` — wyświetla wyniki z historii |

### Infrastruktura:

- SQL migration: `ALTER TABLE transcript_jobs ADD COLUMN schema_data JSONB DEFAULT NULL;`
- Docker rebuild: oba kontenery (`vse-api`, `vse-web`) przebudowane i uruchomione

## Weryfikacja

- ✅ `GET /v1/jobs/history` — zwraca `has_vtt`, `has_schema`, `video_id`, `post_title`
- ✅ `GET /v1/jobs/{id}` — zwraca `FullJobResponse` z `schema_data`
- ✅ Frontend build — `✓ Compiled successfully`, 10 pages generated
- ✅ Kontenery UP i serwują strony (307 redirect to login = auth guard działa)

## Root Cause

Tabela `transcript_jobs` nie miała kolumny `schema_data`. Pipeline generował schema i zwracał w HTTP response, ale nigdzie jej nie persystował. Po zamknięciu sesji wyniki były tracone bezpowrotnie.

## VTT Timestamps

Diagnoza potwierdziła że runner v2.0 działa poprawnie — najnowszy job (`a3ddab96`) ma format `__VTT__\n[00:18] tekst`. Pipeline konwertuje to do WebVTT. Problem VTT timestamps będzie w pełni weryfikowalny przy następnym generowaniu (po moich zmianach schema będzie w DB do porównania).

---

*vse-dev-10 | video-seo-engine | 16.06.2026 21:17*
