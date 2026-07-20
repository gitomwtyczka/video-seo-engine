# Raport: Implementacja logiki fallback dla VTT wg długości wideo

## Cel
Wdrożenie nowej logiki decyzyjnej w procesie pobierania transkryptów wideo (w `core/fetcher.py`), na podstawie czasu trwania wideo (`duration_seconds`) oraz procentowego pokrycia VTT.

## Wykonane kroki
1. Analiza kodu `core/fetcher.py` za pomocą GitHub MCP (`get_file_contents`).
2. Dodanie funkcji pomocniczych do parsowania VTT:
   - `get_vtt_coverage_seconds(vtt_text: str)` parsującej ostatni znacznik czasowy VTT za pomocą wyrażeń regularnych (`HH:MM:SS.mmm` / `MM:SS.mmm`).
   - `check_vtt_coverage(vtt_text: str, duration_seconds: int)` obliczającej pokrycie.
3. Wdrożenie warunkowej logiki pobierania transkryptu (w `process_video`):
   - Krok 1 (istniejący): Pobranie metadanych (API v3 lub yt-dlp) z czasem trwania.
   - Krok 2: Dla filmów `<= 35 min` (2100 s), użycie `transcript-api`. Walidacja pokrycia `>= 80%`.
   - Krok 3: Dla filmów `> 35 min` LUB gdy walidacja Kroku 2 się nie powiedzie (`coverage < 80%`), użycie `yt-dlp` w trybie subtytułów VTT. Walidacja pokrycia `>= 80%`.
   - Krok 4: Jeśli `yt-dlp` też zawodzi (błąd lub `< 80%` pokrycia), zostaje dodana próba awaryjna użycia YouTube Data API v3 (Captions Endpoint `fetch_transcript_api_v3`). Jeśli brak sukcesu, skrypt zapisuje transkrypt o najwyższym uzyskanym pokryciu i loguje ostrzeżenie o spadku jakości.
4. Wgranie aktualizacji `core/fetcher.py` bezpośrednio do `main` przez GitHub API zgodnie z wymogiem `GitHub remote = jedyne źródło prawdy`.

## Zależności i pułapki uwzględnione (Gotchas)
- Pamiętano, że API v3 wymaga autoryzacji do pobierania napisów autogenerowanych nie należących do użytkownika. Jako zabezpieczenie zrealizowany `fetch_transcript_api_v3` posiada własny blok `try...except`, by nie wysypać procesu dla `fetcher.py`.
- Wprowadzono robustny regex obsługujący format zapisu z ułamkami sekundy oddzielanymi kropką lub przecinkiem, radzący sobie ze skróconymi zapisami minuty/sekundy VTT.

[vse-dev-01 | video-seo-engine 2026-07-20 18:55] 📊 V1:6/40 🟢 V2:1str 🟢 V3:2pl 🟢 V4:stabilny V5:ok — raport kompletny
