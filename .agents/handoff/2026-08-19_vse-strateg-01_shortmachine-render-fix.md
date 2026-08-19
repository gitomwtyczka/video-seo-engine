# Handoff — vse-strateg-01 | 2026-08-19

## Status sesji
**Zamknięta poprawnie.** Przekazuję dowodzenie.

---

## Co zostało zrobione (commity)

| Commit | Co | Plik |
|---|---|---|
| `b3a773d` | Dodano `find_local_by_yt_id()` — szukanie lokalnego pliku po YT ID w nazwie | `local-runner/library_matcher.py` |
| `948eb86` | Wywołanie `find_local_by_yt_id` przed fingerprint matchem | `local-runner/video_cutter.py` |
| `c96f3d3` | Dodano `_load_local_overrides()` + priorytet 0 override w `_download_fragment()` | `local-runner/video_cutter.py` |
| `b481c74` | Podkatalogi `{nazwa_wideo}_{data}` dla shortów | `local-runner/runner.py` |
| (browse) | Przycisk Browse + pole local_path w ShortMachine UI | `web/src/app/dashboard/dashboard-inner.tsx` |

---

## Stan aktualny na PC użytkownika

- `C:\ProgramData\VSELocalRunner\local_overrides.json` — zawiera mapowanie:
  ```json
  {"yMY7NC4ZDNQ": "C:\\Users\\tomas2\\Videos\\Prawy\\Płużanski Wernic społecznik.mp4"}
  ```
- Serwis **VSELocalRunner wymaga restartu** po ostatnim git pull (runner.py się zmienił)
- Git pull wykonany: `C:\Users\tomas2\.gemini\antigravity\playground\video-seo-engine` → aktualny do commit `4a4ce7d`

---

## Co NIE zostało zrobione — PRIORYTET NA NASTĘPNĄ SESJĘ

### 🔴 Audio fingerprinting — właściwy fix library_matcher.py

**Problem:** `find_local_match()` pobiera 90s audio od POCZĄTKU wideo z YouTube → czołówka kanału, identyczna dla każdego odcinka → zero wartości matchującej. Dla prywatnych filmów w ogóle nie działa (brak cookies).

**Decyzja właściciela projektu:** Matchowanie ma pobierać 2-3 próbki ze ŚRODKA wideo (nie początku/końca), używać `--cookies-from-browser chrome` dla prywatnych filmów, voting 2/3 próbek.

**Pliki do zmiany:**
- `local-runner/library_matcher.py`:
  - Funkcja `_download_yt_audio_sample()` — pobierać z 33%/50%/66% czasu trwania, nie od 0
  - Dodać `--cookies-from-browser chrome` (fallback edge, firefox)
  - `find_local_match()` — wziąć 2-3 próbki, voting ≥2/3
  - Przekazać `start_sec`/`end_sec` jako hint (sam kandydat jest w środku wideo)
- `local-runner/video_cutter.py`:
  - Przekazać `start_sec`/`end_sec` do `find_local_match()`

**Obecna pętla fallback w `_download_fragment()`:**
```
0. local_overrides.json (manual map)     ← DZIAŁA
1. find_local_by_yt_id (ID w nazwie)     ← DZIAŁA, ale rzadko użyteczne
2. find_local_match (fingerprint)        ← ZEPSUTE (pobiera od początku, brak cookies)
3. yt-dlp download                       ← PADA dla prywatnych
```

### 🟡 Browse button — pełna ścieżka vs tylko nazwa pliku
Przeglądarka nie daje pełnej ścieżki przez `<input type="file">`. Pole pokazuje tylko nazwę. Użytkownik musi wpisać pełną ścieżkę ręcznie. To OK tymczasowo — priorytet niski.

### 🟡 runner.py — source priority
`source = "youtube" if job.get("youtube_url") else "local"` — zawsze youtube gdy youtube_url obecne. Powinno być: `source = "local" if local_path else "youtube"`. Fix niski priorytet (override w video_cutter.py obchodzi problem).

---

## Architektura local_overrides.json (do dokumentacji)

Plik: `C:\ProgramData\VSELocalRunner\local_overrides.json`  
Format: `{"YOUTUBE_ID": "C:\\pełna\\ścieżka\\plik.mp4"}`  
Czytany on-demand (bez restartu serwisu po zmianie).  
Edytowalny ręcznie lub w przyszłości przez UI.

---

## Znane pułapki

1. **Polskie znaki w ścieżkach** — przy ręcznym wpisywaniu łatwo pomylić `ń`/`n`, `ż`/`z` etc. Zawsze weryfikuj przez `Test-Path` po zapisie.
2. **Restart serwisu** — wymaga admina. User robi przez `Services.msc`. Agent nie może przez `Restart-Service` (brak uprawnień).
3. **Git pull** agent może sam wykonać z `C:\Users\tomas2\.gemini\antigravity\playground\video-seo-engine`.
4. **dashboard-inner.tsx** — 7865 linii, zawsze grep+sed przez SSH, nigdy view_file całości.

---

*vse-strateg-01 | 2026-08-19 16:10 | V1:34🟡 — handoff*
