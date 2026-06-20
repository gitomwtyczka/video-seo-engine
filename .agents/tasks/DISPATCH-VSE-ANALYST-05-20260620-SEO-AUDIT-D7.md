---
dispatch_id: "VSE-ANALYST-05-D7-SEO-AUDIT"
created: "2026-06-20"
supervisor: "Supervisor 01"
assigned_to: "[vse-analyst-05]"
repo: "video-seo-engine"
branch: "main"
priority: "MEDIUM"
status: "dispatched"
---

# DISPATCH D7-prep — Audyt SEO RankMath (analiza bez implementacji)

## Cel

Zbadaj dlaczego wygenerowane artykuły VSE dostają 57/100 w RankMath zamiast 90+.
Przygotuj spec dla workera (D7-impl).

**Rola: ANALYST — raport z rekomendacją, zero edycji kodu.**

---

## Kontekst

Screenshot RankMath z 20.06.2026 (kurier365.pl):
- Wynik: 57/100
- Działa: fraza w tytule, fraza w treści, fraza w podtytułach, alt obrazów, unikalna fraza, 733 słów
- NIE działa:
  1. Fraza kluczowa brak w META description
  2. Fraza kluczowa brak w URL (slug)
  3. Fraza nie na początku treści
  4. Gęstość słów kluczowych 0.14 (za niska, fraza pojawia się 1 raz)
  5. Linki zewnętrzne — D4 dodał `seo_external_link` ale RankMath nie widzi
  6. DoFollow linki zewnętrzne — j.w.
  7. Linki wewnętrzne — ZALEŻNOŚĆ: wymaga wiedzy o portalu docelowym (D6b rozwiewa)

## Zadania

### 1. Zbadaj META description

Plik: `core/injector.py` → `build_post_content()` lub `inject_to_wordpress()`
- Czy ustawiamy `rank_math_description` w WP API call?
- Czy wstawiamy `focus_keyphrase` do opisu meta?
- Jeśli nie — napisz rekomendację jak to zrobić.

### 2. Zbadaj slug (post_name)

Plik: `core/injector.py` → `inject_to_wordpress()`
- Czy ustawiamy `slug` / `post_name` w WP API call?
- Aktualnie WP auto-generuje slug z tytułu (obcina do ~75 znaków)
- Rekomendacja: ustaw slug = slugify(focus_keyphrase)

### 3. Zbadaj gęstość keyword

Plik: `core/generator.py` → prompt LLM
- Czy prompt mówi LLM żeby użył frazy kluczowej 3-5 razy w tekście?
- Rekomendacja: dodaj instrukcję w prompcie: "Użyj frazy kluczowej '{focus_keyphrase}' minimum 3 razy w treści artykułu"

### 4. Zbadaj fraza na początku treści

Plik: `core/generator.py` → prompt LLM
- Czy prompt mówi LLM żeby zaczął lead od frazy kluczowej?
- Rekomendacja: "Rozpocznij pierwszy akapit od frazy kluczowej"

### 5. Zbadaj linki zewnętrzne

Plik: `core/injector.py` → `_build_external_link_block()`
- Link jest generowany z `seo_external_link` w profilu
- Dlaczego RankMath nie widzi? Możliwe przyczyny:
  - Link jest po `<!-- wp:more -->` i RankMath nie skanuje excerpt
  - Link ma `rel="noopener noreferrer"` co RankMath traktuje jako nofollow?
  - Link jest w `<p>` który jest ukryty CSS?
  - WordPress czystrzy/filtruje HTML przy zapisie?
- Zbadaj HTML wygenerowanego posta na WP (wp-admin → edytuj → HTML view)

### 6. Linki wewnętrzne — ANALIZA (nie implementacja)

- Potwierdź że to wymaga znajomości portalu docelowego PRZED generowaniem
- D6b daje tę możliwość (parametr `--site`)
- Opisz jak by wyglądał flow: po wyborze portalu → pobierz 10 ostatnich postów → wstaw 2-3 linki
- Czy WP REST API pozwala pobrać posty z danego portalu? Jaki endpoint?

---

## Deliverable

Raport markdown z:
- Diagnozą każdego z 7 punktów
- Konkretną rekomendacją (plik, linia, zmiana)
- Priorytetem (co da największy skok RankMath)
- Zależnościami (co wymaga D6b)

## Raportowanie

1. `video-seo-engine/.agents/reports/2026-06-20_vse-analyst-05_seo-audit-d7.md`
2. `sonic-void/.agents/reports/inbox/2026-06-20_vse-analyst-05_seo-audit-d7.md`

---

*Supervisor 01 | video-seo-engine | 2026-06-20*
