📨 RAPORT DO [Supervisor 01]

## VSE Log Analysis — 23.07.2026

### Stan VPS
- Docker: 
  - `vse-api` (Up 20 hours, port 8085)
  - `vse-web` (Up 26 hours, port 3001)
  - `vse-postgres` (Up 26 hours, healthy, port 5434->5432)
- Commit na VPS: `e0b22c8` fix: scope youtube.force-ssl w _build_credentials()
- Stan brancha: VPS jest **do tyłu o 2 commity** względem `origin/main` (wymagany git pull i ew. restart api).
- Fixy: 
  - ab1ce1f ❌ (Brak na VPS - nowszy commit nie został sfetchowany/zdeployowany. Prawdopodobnie to jeden z dwóch brakujących commitów).
  - 23a599f ✅ (Obecny na VPS).
  - 9c116257 ✅ (Obecny na VPS).

### Logi — kluczowe obserwacje
- **403/Forbidden:** Brak błędów 403 od YouTube w ostatnich logach, co wskazuje na to, że fix na brakujący scope (23a599f) zadziałał poprawnie.
- **VTT/truncation:** Widać logi konwersji VTT (`__VTT__ format detected — converting to WebVTT for generator`, `VTT parsed: 50485 chars | 941 segments`). Wskazuje to, że VTT jest obsługiwane bez wymuszonego "truncation".
- **post_excerpt:** Brak możliwości weryfikacji. Zlecone zapytanie do tabeli `articles` zakończyło się błędem – tabela nie istnieje w bazie danych `vse` wewnątrz kontenera `vse-postgres`. Dane są przechowywane w tabeli `transcript_jobs` w polu `schema_data` w postaci JSONB. Dokładniejsza analiza struktury pokazała, że `schema_data` posiada klucze m.in. `lead` czy `faq`, ale nie posiada gotowego klucza `post_excerpt`. Prawdopodobnie pole to jest budowane w kodzie podczas operacji "inject". Przede wszystkim jednak, w logach gita widać, że repozytorium na VPS jest o 2 commity za `origin/main`, a zatem z dużym prawdopodobieństwem fix ten (będący dzisiejszym commitem) jeszcze się tam nie znajduje.
- **Inne błędy:** W logach pojawiły się ostrzeżenia wskazujące na ban IP / problem z limitami zewnętrznej biblioteki pobierania transkryptów z YouTube:
  - `[fetcher] transcript-api error for bEh_P_uYS18: Use proxies to hide your IP address...`
  - `[fetcher] API v3 captions error for bEh_P_uYS18: HTTP Error 404: Not Found`

### Rekomendacja
- Należy wykonać aktualizację VPS: wejść przez SSH, wykonać `git pull origin main` i zrestartować/zrebuildować API (`docker compose -f docker-compose.vse.yml build vse-api && docker compose -f docker-compose.vse.yml up -d vse-api`), by wypuścić fix 1 (post_excerpt).
- Rozważyć obejście zabezpieczeń anty-scrapingowych YouTube (ip ban), prawdopodobnie przez zaimplementowanie wsparcia dla proxy w `youtube-transcript-api`.
- Zaktualizować dispatche: docelowa instancja bazy na VPS to `vse-postgres` (baza `vse`), a w jej strukturze brak tabeli `articles`. Baza przetrzymuje statusy w `transcript_jobs` a struktura JSON wewnątrz nie posiada gotowych złączeń do WordPressa jak `post_excerpt`.