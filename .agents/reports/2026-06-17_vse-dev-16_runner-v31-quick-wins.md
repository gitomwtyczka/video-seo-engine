# Raport: Runner v3.1 — 4 Quick Wins (anti-detection)

**Callsign:** vse-dev-16
**Data:** 2026-06-17
**Task:** Runner v3.1 — 4 Quick Wins (anti-detection + smart strategy)

## Zmiany wdrożone (Commit `32b74c7`)

Zgodnie z rekomendacją analityka i dyspozycją Supervisora 05, wdrożono 4 zabezpieczenia anty-botowe w `local-runner/runner.py`:

1. **Random delay 5-15s (Anti-burst)**
   Dodano losowe opóźnienie między iteracjami zadań (`time.sleep(random.uniform(5, 15))`), co skutecznie zapobiega blokadom typu "burst limit" przy wielu pending jobach.

2. **`--sleep-subtitles 5` (yt-dlp)**
   Dodano opcję dla `yt-dlp`, zmuszającą narzędzie do odczekania 5 sekund przed próbą pobrania napisów, co upodabnia zachowanie do prawdziwej przeglądarki.

3. **Synchronizacja User-Agent z używanym silnikiem Cookies**
   Wprowadzono dedykowane słowniki `User-Agent` (zgodne z wersjami Chrome/Firefox/Edge 137/138). Runner przekazuje odpowiedni `User-Agent` zależnie od użytej biblioteki cookies (przez parametr `--user-agent`), niwelując wykrywalny mismatch po stronie serwerów YouTube.

4. **API-first → yt-dlp fallback (Odwrócenie logiki)**
   Logika `fetch_transcript` została zmieniona: runner najpierw próbuje lekkiego zapytania przez `youtube-transcript-api` (które nie niesie ryzyka flagowania domowych cookies użytkownika). Dopiero w przypadku blokady API, proces przechodzi na cięższy fallback `yt-dlp + browser cookies`.

## Weryfikacja
Zmiany pomyślnie zapisano na gałęzi `main`. Test składni ukończony bezbłędnie na maszynie deweloperskiej.

## Podsumowanie
Wszystkie 4 cele (quick wins) osiągnięto bez modyfikacji architektury i bez dodawania zewnętrznych zależności (zgodnie z wytycznymi i budżetem operacyjnym).
