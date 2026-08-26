# Raport z naprawy historii ShortMachine (VSE)
**Data:** 2026-08-26
**Agent:** shadow-dev-01
**Problem:** Znikająca wybiórczo historia szortów oraz brak ładowania ID wideo z parametru URL po kliknięciu w Historii. Użytkownik wskazał również potrzebe dopisywania kolejnych wygenerowanych szortów do starych (append) zamiast ich nadpisywania/zamieniania.

**Rozwiązanie:**
1. **Frontend (`dashboard-inner.tsx`)**: Naprawiono logikę przekazywania `initialYoutubeId` do `ShortMachineTab`. Zamiast polegać w całości na obarczonej błędem funkcji `extractVideoId(url)` (która nie radziła sobie z dziwnymi formatami URL z bazy np. live stream), dodano fallback do czystego `result?.videoId` wczytanego z bazy danych dla zadania SEO. Gwarantuje to poprawne wczytanie YouTube ID i załadowanie historii po wejściu z `/historia`.
2. **Backend (`api/routers/shorts.py`)**: Zmieniono zapytania SQL za pomocą SQLAlchemy z `limit(1)` na `limit(10)`. Napisano logikę mergującą zestawy kandydatów od najstarszych do najnowszych (append) z deduplikacją względem czasów (z tolerancją <1 sekundy). Zastosowano to dla endpointów:
   - `GET /v1/shorts/history/{youtube_id}`
   - `GET /v1/shorts/candidates/{youtube_id}`
   - `POST /v1/shorts/generate-srt/{youtube_id}`

Dzięki zastosowaniu merge'owania/dopisywania (append), historia starych wyrenderowanych zadań (jobs) będzie od teraz potrafiła poprawnie dopasować się do wciąż obecnych na liście starych kandydatów, co rozwiązuje zjawisko "wybiórczego znikania historii".

**Status:** Zakończone sukcesem. Zmiany wysłane do repozytorium `video-seo-engine`.
