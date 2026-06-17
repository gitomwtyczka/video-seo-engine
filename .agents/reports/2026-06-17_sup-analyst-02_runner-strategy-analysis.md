# Analiza strategii pobierania transkryptów YouTube — Runner v3.0

**Autor:** sup-analyst-02 | crimson-void
**Data:** 17.06.2026
**Typ:** ANALIZA STRATEGICZNA (nie implementacja)
**Dotyczy:** `video-seo-engine/local-runner/runner.py` (commit 98212642)

---

## Podsumowanie wykonawcze

Runner v3.0 działa poprawnie z yt-dlp + Firefox cookies. Analiza ujawnia **5 krytycznych luk** w obecnej strategii i proponuje v4.0 z inteligentnym wyborem metody, rate limitingiem i bezpieczeństwem konta.

## 5 krytycznych luk

1. **Brak rate limitingu** — burst requests przy wielu pending jobów
2. **User-Agent mismatch** — cookies z Firefox + losowy UA yt-dlp = red flag
3. **Cookies z głównej przeglądarki** — ryzyko dla konta Google (Gmail, Drive)
4. **Brak inteligentnego wyboru metody** — zawsze yt-dlp first, zamiast API first
5. **Brak Deno runtime check** — YouTube 2026 wymaga JS challenges

---

## 1. Runner = User, nie maszyna

| Aspekt | Co robi runner v3.0 | Ocena |
|--------|---------------------|-------|
| Cookies | Autentyczne z Firefox | ✅ OK |
| User-Agent | Losowy (yt-dlp default) | ⚠️ Mismatch |
| TLS Fingerprint | Python/urllib stack | ⚠️ Detectable |
| IP | Domowy residential | ✅ OK |
| Rate limiting | Brak | 🔴 KRYTYCZNE |
| JS Runtime (Deno) | Nie sprawdzane | ⚠️ RYZYKO |

Rekomendacje:
- `--user-agent` spójny z przeglądarką cookies
- `--sleep-subtitles 5`, `--sleep-requests 1`
- Random delay 5-15s między jobami

---

## 2. API vs Browser

Propozycja odwrócenia kolejności:
1. youtube-transcript-api (lekki, 0 ryzyka) → fail?
2. yt-dlp + burner cookies → fail?
3. Report error

Risk matrix:
| Metoda | Ryzyko IP | Ryzyko konta | Niezawodność |
|--------|:---------:|:------------:|:------------:|
| youtube-transcript-api | 🟡 | 🟢 Brak | 🟡 60-70% |
| yt-dlp + cookies (primary) | 🟢 | 🔴 WYSOKIE | 🟢 90%+ |
| yt-dlp + cookies (burner) | 🟢 | 🟢 Brak | 🟢 85-90% |
| YouTube Data API v3 | 🟢 | 🟢 Brak | 🟢 99%* |

---

## 3. Admin konta vs obce wideo

**Scenariusz A (własny kanał):** YouTube Data API v3 (OAuth) → 99% pewność, 0 ryzyko
**Scenariusz B (cudzy kanał):** API first → yt-dlp burner fallback

Warto pytać usera "Czy to Twój kanał?" i cache'ować per channel ID.

---

## 4. Auto-discovery cookies

- yt-dlp czyta CAŁY cookie store (nie tylko YouTube)
- Nie sprawdza freshness cookies
- Runner może sprawdzić zainstalowane przeglądarki (registry/PATH)
- Można sprawdzić freshness przez `os.path.getmtime()` na cookie DB

---

## Quick Wins (<30 min)

1. Random delay 5-15s między jobami (5 min, KRYTYCZNY)
2. `--sleep-subtitles 5` (2 min)
3. `--user-agent` spójny z cookies (10 min)
4. Odwrócić kolejność: API→yt-dlp (15 min)
5. Log wersji yt-dlp na starcie (2 min)

## Long-term

1. YouTube Data API v3 (OAuth) — 2-3 dni
2. Smart browser discovery — 4-6h
3. Burner browser profile — 2-4h
4. UI "Czy to Twój kanał?" — 4-8h
5. Whisper fallback — 2-4 dni

---

*[sup-analyst-02 | crimson-void 17.06.2026 22:30] — raport kompletny*