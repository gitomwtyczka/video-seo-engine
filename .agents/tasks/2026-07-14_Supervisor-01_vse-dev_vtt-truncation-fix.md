# DISPATCH — vse-dev-01 | VTT Truncation Fix
**Supervisor:** Supervisor-01  
**Data:** 2026-07-14  
**Priorytet:** 🔴 WYSOKI — blokuje SEO dla długich materiałów (>60 min)

---

## KONTEKST — CO SIĘ DZIEJE

**Video testowe:** https://www.youtube.com/watch?v=Xcfh_fxyiHE  
**Czas trwania:** ~83 minuty  
**Problem:** Transkrypcja urywa się na 32 minucie. Chaptery, cytaty i FAQ pokrywają tylko ~38% materiału.

---

## DIAGNOZA ROOT CAUSE (wykonana przez Supervisor-01 2026-07-14)

### Przyczyna #1 — KRYTYCZNA: Oracle VPS zablokowany przez YouTube

```
Error: youtube_transcript_api._errors.RequestBlocked
Could not retrieve a transcript — YouTube is blocking requests from your IP.
Most IPs from cloud providers (AWS, GCP, Azure, Oracle) are blocked by YouTube.
```

**Co to oznacza:** `youtube-transcript-api` na VPS (Oracle Cloud, IP: 147.224.162.100) jest blokowany przez YouTube przy próbie pobrania transkryptu. VTT w ogóle nie jest pobierany ze zdalnego serwera.

**Jak więc plik D:\\Biblioteki\\Kurier\\Ziemkiewicz\\Xcfh_fxyiHE (1).vtt ma 32 minuty?**  
→ Plik był pobrany **lokalnie** (yt-dlp lub youtube-transcript-api bez blokady), ale jest niekompletny — kończy się w połowie zdania bez terminalnej pustej linii. Prawdopodobnie yt-dlp przerwał pobieranie lub YouTube serwuje częściowe napisy dla tego wideo.

### Przyczyna #2 — POTENCJALNA: Limit 80 000 znaków w generator.py

W `core/generator.py`, funkcja `generate_seo_v4()`:
```python
text_trimmed = timestamped_text[:80000]
```

Dla 83-minutowego wideo pełny VTT szacunkowo waży ~388 KB (≈388k znaków po parse_vtt_full). Limit 80k znaków pokryłby **tylko ~20% materiału** (~16 minut z 83).

**Ale:** nawet gdyby VTT był pełny, przy 80k limit chaptery obejmowałyby tylko pierwsze 16 minut — nie 32. Więc dla tego konkretnego wideo Przyczyna #1 jest dominująca (plik ma tylko 32 minuty).

**Jednak Przyczyna #2 jest realna dla przyszłych materiałów** — każdy film >40 min będzie obcięty przez ten limit.

---

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)

1. **VPS IP ban** — `youtube-transcript-api` i `yt-dlp` są blokowane na Oracle Cloud dla pobierania transkryptów. NIE próbuj naprawiać tego przez bezpośrednie żądania z VPS — YouTube blokuje całą podsieć Oracle.
2. **Limit 80k** — modyfikacja limitu w generator.py nie rozwiąże problemu pobierania z VPS, to tylko częściowa łatka.
3. **`text_trimmed[:80000]`** — limit jest aplikowany na `timestamped_text` (po parse_vtt_full), nie na surowy VTT. parse_vtt_full deduplikuje i dodaje markery, więc rozmiar po parsowaniu jest mniejszy niż surowy VTT.
4. **SSH z PowerShell** — przy złożonych komendach używaj Trybu B (write_to_file → scp → ssh).

---

## CO ZROBIĆ — PLAN DWUETAPOWY

### Etap A — Natychmiastowy: napraw limit 80k (bez ryzyka, bez zmiany architektury)

**Plik:** `core/generator.py`  
**Zmiana:** Zwiększ limit z 80 000 do 200 000 znaków

```python
# PRZED:
text_trimmed = timestamped_text[:80000]

# PO:
text_trimmed = timestamped_text[:200000]  # ~100 min @ avg 2000 char/min
```

**Uzasadnienie:** Modele Gemini 2.5 Flash i Claude Sonnet obsługują konteksty >1M tokenów. 200k znaków ≈ 50k tokenów — bezpieczne. Dla 83-minutowego wideo pełny VTT po parsowaniu to ok. 100-150k znaków.

**Ważne:** Po zmianie limitu musi być też zmiana komentarza w prompt-ie (sekcja `## KLUCZOWE ZASADY DLA ROZDZIALOW`):
```python
# total_min jest już w prompcie — chaptery muszą pokrywać CAŁY materiał
```
Nic więcej nie zmieniaj w prompcie — jest OK.

### Etap B — Systemowe: mechanizm proxy/cookies dla VTT na VPS

**Problem:** Oracle Cloud IP zablokowany przez YouTube → transkrypty nie pobierają się na VPS.  
**Implikacja:** Użytkownicy muszą lokalnie pobierać VTT i uploadować ręcznie, LUB potrzebujemy proxy.

**Opcje do zbadania (nie implementuj teraz, tylko udokumentuj w raporcie):**

1. **Webshare rotating proxies** — youtube-transcript-api obsługuje proxy config (v1.2.4+): `YouTubeTranscriptApi(proxies={...})`
2. **Cookie auth** — zalogowany użytkownik YouTube, cookies do `youtube-transcript-api`. RYZYKO: ban konta.
3. **Lokalny worker** — pipeline pobiera VTT lokalnie (poza VPS) i uploaduje do API jako plik. Dashboard już ma upload VTT — rozszerzyć ten flow.
4. **ytdl-sub + yt-dlp z proxy** — alternatywny klient z obsługą proxy.

**Rekomendacja Supervisora:** Opcja 3 (lokalny worker) jest najbezpieczniejsza i nie wymaga zewnętrznych serwisów. Opisz w raporcie jak zaimplementować, ale NIE implementuj bez zgody.

---

## DELIVERABLES

### Obligatoryjne (Etap A):
- [ ] Modyfikacja `core/generator.py` — limit 200k
- [ ] Commit na GitHub (branch: main)
- [ ] Deploy na VPS (`docker compose build && up -d vse-api`)
- [ ] Test weryfikacyjny: przetwórz video `Xcfh_fxyiHE` lokalnie z VTT i sprawdź czy chaptery sięgają do >60 min

### Raport:
- [ ] Dual-write raport: `video-seo-engine/.agents/reports/` + `sonic-void/.agents/reports/inbox/`
- [ ] Sekcja w raporcie: "Opcje rozwiązania blokady VPS" (4 opcje opisane wyżej)
- [ ] Rekomendacja której opcji Etapu B użyć

---

## WERYFIKACJA

Po wdrożeniu Etapu A:
```bash
# Test z lokalnym VTT (plik 32-minutowy do testu integralności limitu)
curl -X POST https://vse.impresjapr.pl/v1/generate \
  -H 'Authorization: Bearer TOKEN' \
  -F 'url=https://www.youtube.com/watch?v=Xcfh_fxyiHE' \
  -F 'vtt_file=@/path/to/Xcfh_fxyiHE.vtt'
```
Sprawdź czy chaptery w wyniku pokrywają do końca dostępnego VTT (32 min w tym wypadku).

Dla pełnego 83-minutowego testu: pobierz VTT lokalnie przez `yt-dlp` i wyślij jako upload.

---

## PODSUMOWANIE ROOT CAUSE

| Przyczyna | Komponent | Efekt | Fix |
|---|---|---|---|
| Oracle VPS IP zablokowany przez YouTube | `core/fetcher.py` → `fetch_transcript_api()` | VTT nie pobiera się na VPS → `RequestBlocked` | Etap B (proxy/lokalny worker) |
| Limit 80k znaków w generatorze | `core/generator.py` → `generate_seo_v4()` | Chaptery pokrywają ~20% 83-min wideo | Etap A — zmień na 200k |
| Lokalny plik VTT urwany w połowie | Zewnętrzne (yt-dlp lub YT serwis napisów) | Plik kończy się na 32:08 bez kompletnego ostatniego segmentu | Pobierz ponownie lokalnie przez yt-dlp |

---

*Dispatch sformułowany przez: Supervisor-01 | video-seo-engine | 2026-07-14*
