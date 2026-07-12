# Raport wdrożeniowy: Poprawka formatowania rozdziałów (M4) i placeholder M2

**Callsign:** `vse-fix3`
**Data:** 2026-07-12

## 1. Analiza stanu i przyczyna duplikacji
Faktyczny format przesyłanych do `build_yt_description` elementów `chapters` zawiera słowniki, które mogą operować kluczami `timestamp`, `time_str` lub `time` dla czasu, oraz `label`, `title` czy `name` dla nazwy rozdziału.

Przyczyną duplikacji był wadliwy algorytm sklejania:
```python
ts = ch.get("timestamp") or ch.get("time_str", "") or ch.get("label", "")
label = ch.get("label", "")
```
Jeśli tytuł z generatora wpadał od razu w pełnej formie (np. `label="00:00 Tytuł"`), to w starym formatterze zarówno `ts` jak i `label` były równe `00:00 Tytuł`. Co więcej, stary kod przyrównywał ich formy i je doklejał obok siebie bez sprawdzania, co owocowało efektem: `00:00 Tytuł 00:00 Tytuł`.

## 2. Co wdrożono
- **M4 (Rozdziały):**
  - Wyeliminowano przedrostek `⏱️ Rozdziały:` i zamieniono na poprawny ze specyfikacji: `ROZDZIAŁY:`.
  - Wdrożono inteligentne sprawdzanie i deduplikację. Jeśli `label`/`title` już zaczyna się od zdeklarowanego `timestampu`, kod po prostu używa tytułu i nie dopisuje kolejny raz czasu na początek.
  - Zapewniono konwersję na poprawny zapis `MM:SS` (nawet jeśli podany jako typ numeryczny integer - wsparcie fallbackowe).
- **M2 (Artykuł):**
  - Jeśli brakuje `wp_url` lub powiązanego linku do strony, aplikacja poprawnie używa stringa: `🔗 Artykuł: [WSTAW LINK]`, co ułatwia podmianę ręczną użytkownikowi.
- **Specyfikacja:**
  - Plik `docs/YT_DESCRIPTION_SPEC.md` zaktualizowany o wytyczne z zakresu M4 (limity, zasady nazywania, i struktury technicznej).

## 3. Rezultat deployu
- Przeprowadzono mandatory pre-deploy backup na VPS.
- `vse-api` (backend) zbudowane z sukcesem z najnowszych plików.
- Logi startupowe czyste:
```
INFO:     Application startup complete.
2026-07-12 21:37:05,282 [INFO] api.main: Plans seeded (4 plans, ON CONFLICT DO NOTHING).
2026-07-12 21:37:05,282 [INFO] api.main: Default LLM provider: claude
```
- Aplikacja wznowiła działanie bez zakłóceń.

**Zmiany opublikowane:**
`api/routers/inject.py` oraz `docs/YT_DESCRIPTION_SPEC.md`
W repo `gitomwtyczka/video-seo-engine` na branchu `main`.
