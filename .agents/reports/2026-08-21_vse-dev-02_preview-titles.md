# Raport: DISPATCH 1 — ShortMachine Preview YT + Tytuły/Tagi AI

**Callsign:** vse-dev-02  
**Data:** 2026-08-21  
**Status:** done ✅

## Commity

| Krok | Plik | Commit SHA |
|------|------|------|
| KROK 1 | `core/shorts.py` | `8cff52d4b4571c9d1fc9d22168ae1108b25ef008` |
| KROK 2 | `api/routers/shorts.py` | `4685a6ee5314de0b62ef0820e8b71b11ce5d84da` |
| KROK 3 | `web/src/app/dashboard/dashboard-inner.tsx` | `9571bb81c14e57f2ebe12f70ad0838ae78571c90` |
| Heartbeat | `.agents/heartbeat.json` | `5533e5982f5daf09dba2eb6ca453cb28baea1afa` |

## Zmiany techniczne

### core/shorts.py
- Dodano pola `suggested_title: str = ""` i `tags: list = field(default_factory=list)` do `ShortCandidate`
- Rozszerzono `to_dict()` o nowe pola
- Rozszerzono `SHORTS_SELECTION_PROMPT` o sekcję TYTUŁ I TAGI z instrukcjami AI
- Parsing `suggested_title` i `tags` w `propose_shorts()`
- Nowy helper `get_segments_for_range()` używany przez /title endpoint

### api/routers/shorts.py
- Nowy model `TitleRequest` (youtube_id, start_sec, end_sec)
- Nowy endpoint `POST /v1/shorts/title` — regeneracja tytułu+tagów po zmianie trimowania
- Helper `_resolve_vtt_path()` — wspólna logika szukania VTT (dysk VPS + TranscriptJob DB)
- Odpowiedź: `{"title": "...", "tags": ["#tag1", ...]}`

### dashboard-inner.tsx (+123 linii, 8050 linii total, 130040 bytes)
- Nowe stany: `smPreviewIdx`, `smTitles`, `smTags`, `smTitleLoading`, `ytPlayerRef`, `ytIntervalRef`
- Auto-fill tytułów/tagów po `handleGetCandidates` (z danych backendu)
- Funkcja `handleRegenerateTitle()` — fetch POST /v1/shorts/title po zmianie trim
- useEffect YT IFrame API loader (script tag injection)
- UI per kandydat:
  - Edytowalny input tytułu shorta
  - Przycisk 🔄 (pojawia się tylko gdy trim jest zmieniony)
  - Chipy tagów z możliwością usuwania
  - Przycisk ▶ Podgląd YouTube z auto-stop na końcu zakresu

## Deploy
- Pre-deploy backup: ✅ OK
- Git pull: ✅ Already up to date
- Docker build vse-api + vse-web: ✅ OK (wykonane przez Supervisora)
- Docker up -d: ✅ Kontenery działają

## Definition of Done

- [x] `core/shorts.py` — ShortCandidate ma `suggested_title` + `tags`, prompt rozszerzony
- [x] `api/routers/shorts.py` — endpoint `POST /v1/shorts/title` działa
- [x] `dashboard-inner.tsx` — tytuł edytowalny, tagi jako chipy, 🔄 po trim, podgląd YT
- [x] Oba kontenery (`vse-api`, `vse-web`) zbudowane i działające
- [x] Raport dual-write
- [x] Heartbeat `done`

## Uwagi operacyjne
- `ShortCandidateSet` model NIE ma pola `vtt_path` — endpoint `/title` używa `_resolve_vtt_path()` (dysk + TranscriptJob DB)
- YT Preview używa IFrame API (nie iframe embed) bo potrzebny jest auto-stop na `end_sec`
- Przycisk 🔄 jest widoczny TYLKO gdy trimAdj jest niezerowy (motywuje do używania trim)
