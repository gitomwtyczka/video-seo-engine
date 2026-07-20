## Runner log — fakty
- 19:37:22: Zaczęto przetwarzać Job `43e2039d-7340-4ca9-9212-bf0f13855f9e` (wideo `jae9brYJgcE`).
- yt-dlp+cookies_file zwrócił błędy: `YouTube is no longer supported in this application or device.` dla pl oraz en.
- Fallback browser_cookies (firefox/chrome) również zawiódł (błędy z brakiem bazy cookies).
- 19:37:31: Uruchomiono jako ostatnią deskę ratunku `transcript-api`.
- 19:37:33: API znalazło pl, `transcript-api OK: 66526 chars, 1579 segments`.
- 19:37:33: Wynik joba wysłany, lecz otrzymał z API odp: `status=already_processed`.
- Brak w logu informacji w formacie `VTT coverage: last segment at`.

## VPS docker — fakty
- 17:37:17 (UTC): transcript-api oraz yt-dlp na VPS odrzuciły request, VPS zainicjował job dla Local Runnera (LOCAL_RUNNER_MODE=true).
- 17:37:26: Otrzymano od runnera pierwszy wynik joba: `Transcript truncated to ~99975 chars (original: 185847)`. Rozmiar 185847 sugeruje, że to stary .vtt pobrany przez inne/poprzednie wywołanie ok. 19:05.
- Przekonwertowano odebrany fragment do WebVTT na API: `1679 segments, 145880 chars`, VTT parsed dał: `39:44`.
- 17:37:33: Kolejny POST od runnera dla tego samego joba odrzucony: `already in status 'fetched', ignoring duplicate result` (to była ta odpowiedź 66k z transcript-api).

## Wnioski
- Coverage: BRAK informacji o "Xs (Xmin)" z logów nowej implementacji. (Wynik z pierwszego zgłoszenia API parsowany jako 39:44).
- Metoda: transcript-api (powiodła się na Runnerze, ale odrzucono ją jako duplikat); yt-dlp poległ ("no longer supported").
- Segmentów: 1579 (wg odrzuconego transcript-api) / 1679 (wg zaakceptowanego zduplikowanego/starego payloadu yt-dlp na API).
- Błędy: tak (yt-dlp cookies "device not supported", brak coverage blocku w logach runnera, wyścig/podwójna wysyłka ze starym wynikiem yt-dlp uciętym przez VPS do 99k).