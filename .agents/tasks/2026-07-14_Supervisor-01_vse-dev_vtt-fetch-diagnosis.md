# DISPATCH — vse-dev | VTT Truncation — youtube-transcript-api fetch audit
**Supervisor:** Supervisor-01  
**Data:** 2026-07-14  
**Priorytet:** 🔴 WYSOKI

---

## KONTEKST

Systemów bug: pipeline VSE generuje chaptery tylko dla ~30 minut niezależnie od długości wideo.

Zidentyfikowane wideo testowe:
- `uFLxdXdIoZA` — rzeczywistość: 70+ min | pipeline: ~30 min
- `Xcfh_fxyiHE` — rzeczywistość: 83 min | pipeline: ~30 min

Architektura:
- Lokalny worker `shadow-perihelion/scripts/youtube-worker/youtube_fetch.py` pobiera VTT przez `youtube-transcript-api`
- VTT ląduje lokalnie (`D:\\Biblioteki\\...`), następnie jest wysyłany do VSE API
- VSE pipeline (`core/fetcher.py`) również używa `youtube-transcript-api` bezpośrednio

---

## ZADANIE

### Krok 1 — Audit aktualnego limitu w generator.py

Sprawdź plik `core/generator.py` (repo: `video-seo-engine`, branch: `main`).
- Jaki jest aktualny limit `text_trimmed[:X]`? (poprzedni fix zmienił 80k → 200k, commit 9c116257)
- Ile minut pokrywa przy założeniu ~2000 char/min?
- Czy po tej zmianie chaptery sięgają dalej niż 30 min? Jeśli nie — limit nie jest root cause.

### Krok 2 — Diagnoza youtube-transcript-api.fetch() dla długich wideo

Na maszynie lokalnej (nie VPS) uruchom:

```python
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import WebVTTFormatter

video_id = "uFLxdXdIoZA"
ytt = YouTubeTranscriptApi()

transcript_list = ytt.list(video_id)
for t in transcript_list:
    print(f"lang={t.language_code} generated={t.is_generated}")

# Pobierz
entries = ytt.fetch(video_id, languages=["pl"])
print(f"Liczba segmentów: {len(entries)}")
print(f"Pierwszy segment: {entries[0]}")
print(f"Ostatni segment: {entries[-1]}")

# Porównaj z całkowitym czasem wideo
if entries:
    last_ts = entries[-1].start + entries[-1].duration
    print(f"Ostatni timestamp: {last_ts:.1f}s = {last_ts/60:.1f} min")
```

Zapisz output. Klucz: ile minut pokrywa `entries[-1].start`?

### Krok 3 — Test fallback yt-dlp

Jeśli `ytt.fetch()` zwraca niepełne dane, sprawdź czy `yt-dlp` daje pełny VTT:
```bash
yt-dlp --skip-download --write-auto-sub --sub-lang pl --sub-format vtt \
  -o "%(id)s.%(ext)s" https://www.youtube.com/watch?v=uFLxdXdIoZA
```
Sprawdź rozmiar pliku i ostatni timestamp w VTT.

### Krok 4 — Raport i fix proposal

W raporcie odpowiedz:
1. Ile segmentów/minut zwraca `ytt.fetch()` dla każdego z dwóch wideo?
2. Czy limit w generator.py jest root cause, czy jest gdzie indziej?
3. Rekomendacja fixa (opcje: upgrade biblioteki, switch na yt-dlp, zmiana logiki w fetcher.py)

---

## ⚠️ ZNANE PUŁAPKI

1. Test musi być na maszynie lokalnej lub przez proxy — VPS Oracle jest blokowany przez YouTube dla transkryptów
2. Limit 200k w generator.py był już zaimplementowany (commit 9c116257) — nie implementuj ponownie
3. SSH z PowerShell: złożone komendy → write_to_file → scp → ssh

---

## DELIVERABLES

- Raport dual-write:
  - `video-seo-engine/.agents/reports/2026-07-14_vse-dev_vtt-fetch-diagnosis.md`
  - `sonic-void/.agents/reports/inbox/2026-07-14_vse-dev_vtt-fetch-diagnosis.md` (branch: master)
- Jeśli fix jest jasny i bezpieczny — wdroż i podaj commit SHA

---

*Dispatch: Supervisor-01 | video-seo-engine | 2026-07-14*
