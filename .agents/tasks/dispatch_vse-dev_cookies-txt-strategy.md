# Dispatch: cookies.txt strategy — Local Runner yt-dlp fix

**Data:** 2026-07-20  
**Nadawca:** Supervisor-01  
**Odbiorca:** vse-dev (worker)  
**Priorytet:** 🟡 Średni  
**Repo:** video-seo-engine | branch: main

---

## Kontekst

Lokalny runner używa `yt-dlp` do pobierania VTT transkryptów. VPS ma zablokowane IP przez YouTube — runner lokalny (LOCAL_RUNNER_MODE=true) jest jedynym sposobem na pełny VTT dla długich filmów (>35 min).

**Problem zdiagnozowany 2026-07-20:**
- `fetch_transcript_ytdlp()` w `core/fetcher.py` wywołuje yt-dlp **bez cookies** → YouTube zwraca `YouTube is no longer supported in this application or device`
- `--cookies-from-browser chrome` nie działa: Chrome blokuje swoją bazę SQLite gdy jest otwarty (issue #7271)
- `--cookies-from-browser firefox` działa lokalnie z CLI, ale runner jako background process może nie mieć dostępu do profilu Firefoksa
- Najbardziej niezawodne rozwiązanie: `cookies.txt` plik eksportowany raz z przeglądarki, wskazany przez env var

**Downtest:** wideo `jae9brYJgcE` (1h13m) — bez cookies yt-dlp pada, z Firefox cookies yt-dlp pobiera 484 KB VTT (3157 segmentów, last: 01:13:47) vs 66k chars z transcript-api.

---

## Zadanie

### 1. Dodaj obsługę `cookies.txt` w `fetch_transcript_ytdlp()`

Plik: `core/fetcher.py`, funkcja `fetch_transcript_ytdlp()`.

**Logika (w kolejności priorytetu):**
1. Sprawdź env var `YTDLP_COOKIES_FILE` → jeśli ustawiona i plik istnieje → `--cookies <path>`
2. Jeśli nie → spróbuj `--cookies-from-browser firefox` (działa na Windows lokalnie, cicho pomijaj jeśli blad)
3. Jeśli nie → spróbuj `--cookies-from-browser chrome` (może zadziałać gdy Chrome zamknięty)
4. Jeśli żadne → yt-dlp bez cookies (obecne zachowanie — zostaje jako ostatni fallback)

Loguj metodę cookies która zadziałała: `[fetcher] yt-dlp using cookies: file|firefox|chrome|none`

```python
# Przykład logiki wyboru cookies
cookies_file = os.environ.get('YTDLP_COOKIES_FILE', '')
cmd_base = ['yt-dlp', '--skip-download', '--write-auto-sub', '--write-sub',
            '--sub-lang', lang, '--sub-format', 'vtt',
            '--output', os.path.join(output_dir, f'{video_id}.%(ext)s'), url]

if cookies_file and os.path.exists(cookies_file):
    cmd = cmd_base + ['--cookies', cookies_file]
    cookies_method = 'file'
elif sys.platform == 'win32':  # local runner na Windows
    cmd = cmd_base + ['--cookies-from-browser', 'firefox']
    cookies_method = 'firefox'
else:
    cmd = cmd_base
    cookies_method = 'none'
```

### 2. Dodaj obsługę `YTDLP_COOKIES_FILE` w `.env.api.example`

Dopiszcie komentarz:
```
# Lokalny runner — cookies YouTube dla yt-dlp (eksport z przeglądarki)
# YTDLP_COOKIES_FILE=C:/Users/tomas2/cookies/youtube_cookies.txt
YTDLP_COOKIES_FILE=
```

### 3. (opcjonalnie) Dodaj try/except dla `--cookies-from-browser` fallback

Jeśli Firefox nie jest dostępny lub profile zablokowane — yt-dlp zwraca błąd. Należy go catch i retry bez cookies (nie crashować całego joba).

---

## ⚠️ ZNANE PUŁAPKI

1. **fetcher.py jest duży** — przed edycją sprawdź rozmiar. Edytuj przez GitHub MCP `create_or_update_file` z pełną zawartością ALBO chirurgicznie przez `replace_file_content` wskazując dokładne linie do zmiany.
2. **SHA** — przed `create_or_update_file` pobierz aktualny SHA przez `get_file_contents`. SHA na dziś: `c870ddb9f9b00a014ec3cb616593ccdfc4aeca50` (może być nieaktualne — zawsze pobierz fresh).
3. **subprocess list** — yt-dlp jest już wywoływany przez `subprocess.run(cmd, ...)` gdzie `cmd` to lista — dobry wzorzec, zachowaj go (nie sklejaj w string).
4. **Nie ruszaj** logiki coverage (`get_vtt_coverage_seconds`, `check_vtt_coverage`) — te funkcje są poprawne po fixie z 2026-07-20.
5. **Test po deploy:** zrób git pull na VPS nie jest potrzebny — fetcher.py jest używany przez local runner bezpośrednio z lokalnego klonu. Zmiana w GitHub → git pull w lokalnym repo runnera → restart runnera.

---

## Definition of Done

- [ ] `core/fetcher.py` — `fetch_transcript_ytdlp()` obsługuje cookies wg powyższej logiki
- [ ] `.env.api.example` — dodano `YTDLP_COOKIES_FILE=` z komentarzem
- [ ] Commit na GitHub (branch: main)
- [ ] Raport do `video-seo-engine/.agents/reports/` + `sonic-void/.agents/reports/inbox/`
- [ ] `current.md` zaktualizowany

---

*Supervisor-01 | sonic-void | 2026-07-20*
