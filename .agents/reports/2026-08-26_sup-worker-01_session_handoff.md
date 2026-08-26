# Handoff Report — sup-worker-01 | shadow-perihelion
**Data:** 2026-08-26 | **Sesja:** 4c9dbe9f-adaa-4b32-8ca7-ecfa1751882a  
**Status:** ✅ Zamknięte — przekazuję Supervisorowi  
**Brain lokalizacja:** `C:\Users\tomas2\.gemini\antigravity\brain\4c9dbe9f-adaa-4b32-8ca7-ecfa1751882a\`  
**Transcript:** `..\.system_generated\logs\transcript.jsonl`  
**Scratch & SRT:** `...\scratch\` (patrz sekcja pliki)

---

## 🌟 KLUCZOWY INSIGHT BIZNESOWY — SRT jako samodzielny produkt (NOWE)

> Ten insight pojawił się na końcu sesji i MUSI być przekazany Supervisorowi i shadow-strateg.

### Odkrycie
W trakcie sesji zrealizowaliśmy proof-of-concept, który ujawnił **nową wartość produktową**: możliwość tworzenia shortów w pełni bezkosztowo i ręcznie, wyłącznie przez generowanie plików SRT.

### Model "SRT-Only Shorts"

| Etap | Narzędzie | Koszt |
|------|-----------|-------|
| Pobierz transkrypt z YT | yt-dlp / youtube-transcript-api | 0 zł |
| Wygeneruj kandydatów | LLM (Gemini Flash) | ~0,01–0,05 USD |
| 3 pliki SRT | VSE backend | 0 zł (serwer) |
| Montaż | Premiere Pro / DaVinci / CapCut | narzędzie klienta |
| Publikacja YT | ręcznie | 0 zł |

**Łączny koszt serwera na użytkownika: ~0,05 USD/film**

### Propozycja tiers

```
TIER FREE (~0 zł):
  - Do 3 shortów na film
  - Generuje: pelny_film.srt, napisy_shortow.srt, shorts_markers.srt
  - Ręczne pobieranie plików
  - Ręczny montaż w Premiere/DaVinci
  - Zero renderingu wideo po stronie serwera

TIER SRT PRO (~10 USD/mies lub mniej):
  - Unlimited shortów
  - Integracja z kanałem YT (auto opis/tytuł/hashtagi po publikacji)
  - Historia i zarządzanie szortami przez panel

TIER FULL AUTO (wyższa cena):
  - Wszystko powyżej
  - Local Runner — automatyczne renderowanie na komputerze klienta
  - Faster-Whisper — transkrypcja z MP3 bez kosztów API
  - Auto-publikacja z harmonogramem
```

### Dlaczego to ważne
1. **Bariera wejścia = 0** — użytkownik potrzebuje tylko Premiere Pro (które i tak ma)
2. **Wartość realna** — SRT z timestampami shortów to 90% roboty montażysty. Wie dokładnie gdzie ciąć.
3. **Zarażenie ideą** — po kilku razach user zobaczy ile czasu oszczędza i naturalnie sięgnie po automatyzację
4. **Skalowanie bez bólu** — Free tier nie generuje kosztów serwera, więc można dać go szeroko

### Następne kroki dla shadow-strateg
- Zaprojektować UX "Pobierz pakiet SRT" jako standalone CTA
- Rozważyć landing page tylko dla tego workflow
- Wycenić tier SRT PRO (10 USD/mies wydaje się właściwe, może nawet 7–8 USD)
- Zapisać w roadmapie jako osobną funkcjonalność od renderowania

---

## 1. WĄTEK TECHNICZNY — Naprawa 3 bugów VSE (✅ ZAMKNIĘTE)

### Problem
Po dużym refaktorze w kodzie VSE pojawiły się 3 krytyczne regresje:

1. **Historia szortów znikała po F5** — frontend nie parsował `data.candidates` po pobraniu historii z API, `smTitles`/`smTags` zostawały null'ami.
2. **Wymuszony link YT** — endpoint `/render` odrzucał request gdy podano pełny URL zamiast 11-znakowego ID; nie było wywołania `extractYoutubeId`.
3. **YouTube API Error 400 przy Publish** — `youtube_publish.py` wysyłał cały obiekt `snippet` (wraz z polami read-only jak miniatury), co Google odrzucało.

### Rozwiązanie (commity na `main`)
| Plik | Zmiana |
|------|--------|
| `api/models/__init__.py` | Dodano importy ShortCandidateSet i ShortJob do metadata |
| `api/migrate.py` | Naprawiono logikę migracji tabel |
| `api/routers/shorts.py` | `extractYoutubeId()` przed zapisem job'u |
| `api/core/youtube_publish.py` | Filtrowanie snippet'u — tylko title, description, categoryId, tags |
| `web/.../dashboard-inner.tsx` | Poprawka initialYoutubeId |
| `web/.../ShortMachineTab.tsx` | Parsowanie historii + extractYoutubeId w payload |
| `web/.../YouTubePublishModal.tsx` | Czerwone kolorowanie błędów z API |

### Deploy
- Backup: `/home/ubuntu/backups/video-seo-engine_backup_20260825_221214`
- One-click restore: `./restore_vse.sh /home/ubuntu/backups/video-seo-engine_backup_20260825_221214`
- Produkcja: ✅ Działa. All containers healthy.

---

## 2. WĄTEK TECHNICZNY — Hook + Punchline w opisie szorta (✅ ZAMKNIĘTE)

### Problem
AI generuje świetnie sformatowane pola `hook_text`, `body_summary`, `punchline_text` dla każdego kandydata shorta. Przy otwieraniu okna publikacji YouTube te pola były ignorowane — opis był pusty lub zawierał tylko tytuł.

### Rozwiązanie
`ShortMachineTab.tsx` — w bloku budowania `smSchemaData`:
```typescript
const combinedBody = [hookTxt, bodySum, punchTxt].filter(Boolean).join('\n\n');
const smSchemaData = {
  youtube_description_body: combinedBody,
  yt_title: smTitles[i] || c.suggested_title || c.title || ''
}
```
Opis do YouTube = Hook + Body + Punchline + (automatycznie) stopka kanału z backendu.

**Commit:** `5b574aeeb924442c78a5c36be895d3becfe7d9d8`  
**Status:** ✅ Deploy i build zakończony pomyślnie.

---

## 3. WĄTEK ARCHITEKTONICZNY — Hybrid SRT dla długich filmów (🔵 ZAPLANOWANE)

### Decyzja
Odchodzimy od FFmpeg overlay (renderowania napisów wpalonych w wideo) dla długich formatów. Zamiast tego: **pure SRT-Driven workflow** — trzy osobne pliki SRT:

| Plik | Zastosowanie |
|------|-------------|
| `pelny_film.srt` | YT Closed Captions (CC) — pełna transkrypcja |
| `karaoke_hooks.srt` | Napisy tylko w obszarach shortów — do Premiere/DaVinci |
| `shorts_markers.srt` | Duże bloki czasowe z `[SHORT 1: tytuł]` — import do Premiere daje wizualne markery cięć na osi czasu |

**Kluczowa zaleta:** Zero re-encodingu wideo. Montażysta przeciąga `shorts_markers.srt` na ścieżkę Captions w Premiere → widzi klocki → tnie żyletką → gotowy short w 5 sekund.

### Próba testowa (⚠️ NIEKOMPLETNA — patrz sekcja 5)
Wygenerowano kandydatów i pliki SRT dla `IDN480v41Ps`:
- Pliki SRT gotowe lokalnie w `scratch/` 
- Problem: kandydaci nie widoczni w panelu — patrz sekcja 5

### FFmpeg Overlay
Przeniesiony na Roadmapę — niepriorytyzowany. Może wrócić przy skalowaniu automatyzacji.

---

## 4. WĄTEK ARCHITEKTONICZNY/BIZNESOWY — Faster-Whisper + MP3 (🟡 ZAPLANOWANE / NIEZREALIZOWANE)

### Kontekst
Koszt transkrypcji przez zewnętrzne API (np. OpenAI Whisper): ~1,40 USD za godzinny film → przy abonamentach VSE to "samobójstwo ekonomiczne".

### Stan infrastruktury
- `local-runner/requirements.txt`: **brak `faster-whisper`** — tylko `youtube-transcript-api`
- `requirements.txt` (API): brak Whisper
- Aktualny runner: tylko YT transcript API (gotowe napisy), nie transkrybuje audio

### Architektura rozwiązania (zaprojektowana, NIE wdrożona)
```
Premiere Pro → eksport MP3 (lekki plik) 
    → Upload do VSE lub LocalRunner
    → faster-whisper lokalnie (darmowo, GPU klienta)
    → word-level timestamps
    → JSON z transkryptem → serwer VSE
    → Gemini/Claude za parę groszy: wytnij 3 shorty
    → Trzy pliki SRT gotowe do Premiere
```

### Korzyści ekonomiczne
- Whisper: 0 zł (lokalny GPU)
- LLM za analizę: ~0,02–0,05 USD
- Serwer: tylko lekki tekst, zero transferu wideo
- Skalowalność: unlimited darmowych userów bez wzrostu kosztów

### Następny krok (Dispatch dla kolejnego agenta)
1. Dodaj `faster-whisper` do `local-runner/requirements.txt`
2. Dodaj skrypt `local-runner/transcribe.py` (przyjmuje MP3, zwraca JSON z word timestamps)
3. Dodaj endpoint API `POST /v1/transcribe` (przyjmuje JSON z timestampami, produkuje SRT + kandydatów shortów)
4. Dodaj w panelu zakładkę "Transkrybuj MP3"

---

## 5. WĄTEK AKTYWNY — Brak shortów w panelu dla IDN480v41Ps (🔴 WYMAGA NAPRAWY)

### Problem
Shorty wygenerowane przez `/v1/shorts/candidates` **nie pojawiają się w zakładce ShortMachine** po wpisaniu ID wideo. W panelu widać puste pola (screenshot: ShortMachine z pustymi inputami).

### Root Cause (hipoteza, do weryfikacji przez subagenta)
Podczas debugowania deploymentu wykonano `git reset --hard` na serwerze. Ta komenda **nie niszczy danych w bazie**, ale kandydaci mogli nie zostać zapisani do bazy w ogóle — endpoint `/v1/shorts/candidates` prawdopodobnie **tylko zwraca JSON**, a nie zapisuje do tabeli `short_candidate_sets`.

Sprawdź na VPS:
```bash
docker exec vse-postgres psql -U vse -d vse -c "SELECT id, youtube_id, created_at FROM short_candidate_sets WHERE youtube_id LIKE '%IDN480%' ORDER BY created_at DESC LIMIT 5;"
```

### Problem #2 — Brak sekcji "Historia wideo / SRT" w panelu
Panel VSE nie ma żadnej sekcji wyświetlającej pliki SRT wygenerowane podczas poprzednich sesji. Pliki SRT zostały wygenerowane lokalnie (scratch/) ale nie są:
- Przechowywane na serwerze
- Linkowane do konkretnego youtube_id w bazie
- Wyświetlane w interfejsie

### Pliki SRT (lokalne, do ponownego wgrania)
Dostępne w `brain/4c9dbe9f.../`:
- [`pelny_film.srt`](file:///C:/Users/tomas2/.gemini/antigravity/brain/4c9dbe9f-adaa-4b32-8ca7-ecfa1751882a/pelny_film.srt)
- [`shorts_markers.srt`](file:///C:/Users/tomas2/.gemini/antigravity/brain/4c9dbe9f-adaa-4b32-8ca7-ecfa1751882a/shorts_markers.srt)
- [`karaoke_hooks.srt`](file:///C:/Users/tomas2/.gemini/antigravity/brain/4c9dbe9f-adaa-4b32-8ca7-ecfa1751882a/karaoke_hooks.srt)

### Kandydaci (dane do re-importu)
`brain/4c9dbe9f.../scratch/candidates.json` — 3 kandydaci, pełne dane:
- SHORT 1 (professional): `50s–125s` — "Zełeński honoruje morderców Polaków"
- SHORT 2 (emotional): `242s–305s` — "Polska pomogła Ukrainie a otrzymała policzek"  
- SHORT 3 (emotional): `843s–905s` — "Naród bez honoru jest narodem bez wartości"

### Akcja naprawcza (dla następnego agenta)
1. Zweryfikuj przez SSH czy w `short_candidate_sets` jest rekord dla `IDN480v41Ps`
2. Jeśli nie — dodaj zapis do bazy w endpointzie `/v1/shorts/candidates` (lub POST ręcznie przez psql)
3. Sprawdź co zwraca `GET /v1/shorts/history/IDN480v41Ps`
4. Jeśli history działa — wejdź na panel, wklej ID i sprawdź czy ShortMachine ładuje dane

---

## 6. WĄTEK BIZNESOWY — Freemium & Local Runner Mac (🔵 ZAPLANOWANE)

### Koncepcja
**Darmowy tier:** Użytkownik dostaje skrypt/apkę webową (yt-dlp + darmowy Whisper) który działa lokalnie. Serwer VSE dostaje tylko lekki tekst. Koszt na darmowego usera = ~0 zł.

**Pro tier:** Automatyzacja, integracja z kanałem YT, advanced SRT workflow, auto-publish.

**Mac Local Runner:** Użytkownik już korzysta z Agencyjnego Local Runnera. Planowana obsługa MAC w kolejnej wersji. Brak bariery instalacyjnej po stronie usera — gotowość do dodania faster-whisper bez friction.

---

## 7. ROADMAPA — Priorytety dla następnej sesji

| Priorytet | Zadanie | Szacunek |
|-----------|---------|----------|
| 🔴 P1 | Fix: Krótkoterminowo — wgraj kandydatów IDN480v41Ps do bazy (ręczny SQL lub fix endpointu) | 30 min |
| 🔴 P1 | Fix: `/v1/shorts/candidates` powinien zapisywać do `short_candidate_sets` jeśli nie robi tego teraz | 1h |
| 🟡 P2 | Feat: SRT storage — zapisywanie wygenerowanych SRT do bazy/dysku i wyświetlanie w panelu | 2–3h |
| 🟡 P2 | Feat: Local Runner — faster-whisper + skrypt `transcribe.py` + endpoint `/v1/transcribe` | 3–4h |
| 🔵 P3 | Feat: Panel — zakładka "Transkrybuj MP3" | 2h |
| 🔵 P3 | Feat: Freemium — logika limitowania kandydatów (3 max dla free) | 1h |
| 🗺️ Roadmapa | FFmpeg overlay dla długich filmów | Przyszłość |

---

## 8. ŚRODOWISKO

| Zmienna | Wartość |
|---------|---------|
| VPS | oracle-crimson (147.224.162.100) |
| SSH Key | `~/.ssh/oracle-crimson.key` |
| Repo | `gitomwtyczka/video-seo-engine` branch `main` |
| Docker compose | `docker-compose.vse.yml` |
| Backup dir | `/home/ubuntu/backups/` |
| Restore script | `/home/ubuntu/restore_vse.sh [BACKUP_PATH]` |
| Postgres | container: `vse-postgres`, user: `vse`, db: `vse` |
| API | port 8085 (internal), `vse-api` container |
| Web | `vse-web` container |
| Panel URL | `https://vse.impresjapr.pl/dashboard` |

---

## 9. NAMIARY NA BRAIN

```
Conversation ID:  4c9dbe9f-adaa-4b32-8ca7-ecfa1751882a
Brain Dir:        C:\Users\tomas2\.gemini\antigravity\brain\4c9dbe9f-adaa-4b32-8ca7-ecfa1751882a\
Transcript:       ..\.system_generated\logs\transcript.jsonl
Scratch:          ...\scratch\
  - candidates.json    (3 kandydaci IDN480v41Ps — pełne dane)
  - sm.tsx             (patched ShortMachineTab)
  - yt.tsx             (patched YouTubePublishModal)
Artifacts:
  - pelny_film.srt
  - shorts_markers.srt
  - karaoke_hooks.srt
  - architecture_long_video.md
  - handoff_report.md (ten plik)
  - implementation_plan.md
  - task.md
```

---

*[sup-worker-01 | shadow-perihelion 26.08.2026] — handoff kompletny*
