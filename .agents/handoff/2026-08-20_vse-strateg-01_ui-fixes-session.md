# Handoff — vse-strateg-01 | 2026-08-20

## Status sesji
**Zamknięta z V1:🔴.** Przekazuję dowódzenie.

---

## Co zostało zrobione (commity)

| Commit | Plik | Co |
|---|---|---|
| `8ecd1c0` | `video_cutter.py` | `_generate_submachine_srt()` — plain segments, no karaoke accumulation |
| `3aaf6f7` | `runner.py` | `source` priority — `local_path` bije `youtube_url` |
| `55733a1` | `library_matcher.py` | `find_local_by_basename()` — szuka pliku po samej nazwie w znanych katalogach |
| `4dc4613` | `video_cutter.py` | basename resolution przed FileNotFoundError |
| `3d67c5d` | `runner.py` | folder naming — używa stem z `local_path` bez `os.path.exists` check |
| `7aec562` | `dashboard-inner.tsx` | klikalny link do folderu (potem okazało się że `file://` blokowany przez HTTPS) |

## Worker w toku (nie czekałem na wynik)

**Subagent `b5d9c918`** (vse-dev-02) robi dwa fixy w `dashboard-inner.tsx`:
1. Zamiana `file://` link → przycisk "Kopiuj ścieżkę folderu" (clipboard)
2. Select-all checkbox nad listą kandydatów w ShortMachine

Sprawdzić czy worker wysłał raport — jeśli tak, zrobić git pull.

---

## Co NIE jest zrobione — PRIORYTETY

### 🔴 Audio fingerprinting — library_matcher.py
**Problem:** `find_local_match()` pobiera 90s audio od POCZĄTKU → czołówka kanału, identyczna dla każdego odcinka.
**Fix:** 3 próbki z 33%/50%/66% czasu trwania + `--cookies-from-browser chrome` + voting 2/3.
**Pliki:** `library_matcher.py` (`_download_yt_audio_sample`, `find_local_match`) + `video_cutter.py` (przekazanie `start_sec`/`end_sec`).

### 🟡 runner.py source priority — test
Fix `3aaf6f7` nie był przetestowany. Użytkownik nie potwierdził że lokalny plik działa.

### 🟡 Browse button — pełna ścieżka
`<input type="file">` nie daje pełnej ścieżki. `find_local_by_basename()` (commit `55733a1`) jest obejściem. Priorytet niski.

---

## Stan PC użytkownika

- `local_overrides.json`: `{"yMY7NC4ZDNQ": "C:\\Users\\tomas2\\Videos\\Prawy\\Płużanski Wernic społecznik.mp4"}`
- VSELocalRunner: powinien być zrestartowany po ostatnich fixach (user restartuje przez Services.msc)
- Logi: `C:\ProgramData\VSELocalRunner\runner-YYYYMMDDTHHMMSS.sss.log`

---

## Znane pułapki

1. `dashboard-inner.tsx` 7865 linii — zawsze grep+sed przez SSH, nigdy `view_file` całości
2. `file://` link z HTTPS → blokowany przez przeglądarkę
3. VSELocalRunner restart wymaga admina (Services.msc), agent nie może sam
4. Po każdym commicie do `local-runner/` — przypomnieć userowi o restarcie serwisu

---

*vse-strateg-01 | 2026-08-20 20:39 | V1:51🔴 — handoff*
