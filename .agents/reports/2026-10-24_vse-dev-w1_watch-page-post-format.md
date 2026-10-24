# Raport Wdrożeniowy: W1 — Format Wpisu WP (video) oraz Wymogi Google Watch Page 2026 i HCU

- **Autor:** vse-dev-w1
- **Data:** 2026-10-24 22:50 CEST
- **Zadanie:** W1 (TASK-01 do TASK-06)
- **Status:** ✅ Zakończone, zmergowane do `main`, wdrożone na VPS oracle-crimson (TAG: `20261024-203507`)
- **Commity:**
  - PR #9 merge commit: `f0167fe` / `921b9b5` (`api/routers/inject.py`, `tests/test_w1_watch_page.py`)
  - `75bb6c2` (`api/services/pipeline.py`)
  - `8583625` (`core/generator.py`)
  - `f40f9b6` (`core/injector.py`)

---

## 1. CO zostało zrobione
Wdrożono pełny pakiet 6 zadań architektonicznych W1, dostosowujących publikację w WordPressie do wymogów Google Watch Page 2026 oraz wytycznych Helpful Content Update (HCU):
1. **TASK-01:** Wymuszenie formatu wpisu `video` zamiast `standard` w WordPress REST API (`update_post`, `inject_video`, endpoint `/wp-json/vse/v1/publish` we wtyczce `vse-video-seo.php`).
2. **TASK-02:** Dodanie do JSON-LD węzłów `@type: Article` (z powiązaniem `@id` do `VideoObject`) oraz `@type: BreadcrumbList` (ścieżka nawigacyjna Strona główna → Post).
3. **TASK-03:** Responsywny embed 16:9 z zero Cumulative Layout Shift (CLS) — style `aspect-ratio: 16/9; width: 100%;` oraz wrapper `padding-bottom: 56.25%`.
4. **TASK-04:** Akcja `SeekToAction` w schemacie `VideoObject.potentialAction` (`target: {yt_url}&t={seek_to_second_number}`) umożliwiająca bezpośrednie odtwarzanie fragmentów z poziomu wyników wyszukiwania Google.
5. **TASK-05:** Przebudowa promptu publikacji typu `watching_page` w generatorze AI — generowanie 300–450 słów merytorycznej treści, 1–2 śródtytułów `<h3>`, akapitów z tezami, cytatami i naturalnie wplecionymi linkami wewnętrznymi.
6. **TASK-06:** Deterministyczny blok linków wewnętrznych (`_build_internal_links_block`) — automatyczne wstawianie eleganckiego boxu "Warto również przeczytać" w treści artykułu, jeśli LLM nie wplótł linków w tekst.

---

## 2. PO CO to zrobiono (Uzasadnienie biznesowe & SEO)
- **Eliminacja błędu Google Video Indexing:** Posty publikowane jako format `standard` były traktowane przez Google jako zwykłe artykuły tekstowe z przypadkowym embedem wideo, co uniemożliwiało indeksację wideo w karcie "Wideo" i przyznanie Video Rich Snippet.
- **Spełnienie wytycznych Google Watch Page 2026:** Google wymaga, aby strona wideo zawierała odtwarzacz w centralnym punkcie strony (zero CLS) oraz unikalną, pomocną treść redakcyjną (minimum 300 słów pod HCU) wyjaśniającą kontekst materiału.
- **Nawigacja po osi czasu (Key Moments):** Schemat `SeekToAction` wraz z `Clip[]` pozwala robotom Google prezentować bezpośrednio w SERP kluczowe momenty nagrania z precyzyjnymi linkami do sekund.
- **Architektura linkowania wewnętrznego (Internal Link Equity):** Box polecanych artykułów zapewnia stały przepływ PageRanku i sygnałów topical authority pomiędzy powiązanymi wpisami portalu.

---

## 3. JAK to zrealizowano (Szczegóły techniczne & Architektura)

### A. Moduł `core/injector.py`
- Zaktualizowano `build_schema_jsonld`:
  - `VideoObject` posiada stabilne URI `@id: {post_url}#video` oraz `potentialAction` z `WatchAction` i `SeekToAction`.
  - Dołączono obiekt `Article` z URI `@id: {post_url}#article` i referencją `"video": {"@id": video_id_uri}`.
  - Dołączono `BreadcrumbList` z dynamicznym adresem domeny portalu.
- Funkcja `_build_responsive_embed`: generuje responsywny kontener Gutenberg z inline styles dla absolutnego braku przesunięć układu (zero CLS).
- Funkcja `_build_internal_links_block`: weryfikuje obecność linków w treści i generuje blok fallbackowy `vse-related-links-box`.
- Funkcje `update_post` i `inject_video`: przyjmują parametr `post_format="video"` (fallback dla formatów pustych/standard).

### B. Moduł `core/generator.py`
- Zmodyfikowano prompt `_generate_article_fallback` dla `publication_type == "watching_page"`:
  - Zwiększono cel z 150–250 słów na 300–450 słów.
  - Wymuszono 1–2 śródtytuły `<h3>`.
  - Wprowadzono sekcję wplatania linków wewnętrznych (`internal_links_prompt`).
- Zaktualizowano `_get_publication_type_override` pod kątem single-pass watching_page.

### C. Moduł `api/services/pipeline.py` & `api/routers/inject.py`
- `pipeline.py` przekazuje `post_format="video"` w wywołaniach `inject_video` oraz `build_wp_post_html`.
- `inject.py` weryfikuje i przekazuje parametr `post_format` do endpointu `/wp-json/vse/v1/publish` wtyczki WP.

### D. Wtyczka WordPress `vse-video-seo.php`
- Funkcja `rest_external_publish` odbiera `post_format` (domyślnie `video`) i wykonuje `set_post_format($post_id, $post_format)`.

---

## 4. Weryfikacja i Testy
- **Pytest:** Zestaw 49 testów w kontenerze `vse-api` zakończony statusem 49/49 PASS (`tests/test_w1_watch_page.py` – 9 testów sprawdzających schematy, embed 16:9, SeekToAction, internal links block i format video).
- **GitHub Remote:** Wszystkie commity zsynchronizowane bezpośrednio na gałąź `main`.
- **Następny krok:** Zlecenie audytu technicznego dla agenta `shadow-analyst-01` w repozytorium `shadow-perihelion`.
