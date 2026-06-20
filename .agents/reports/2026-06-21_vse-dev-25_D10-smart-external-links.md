# Raport D10: Smart External Links — Authority Sources

**Callsign:** vse-dev-25
**Data:** 2026-06-21
**Dispatch:** DISPATCH-VSE-DEV-25-20260621-SMART-EXTERNAL-LINKS-D10
**Commit:** `feb2ed4` (feat(D10): Smart External Links)

---

## CO ZROBIONO

### 1. `core/generator.py` — prompt v5.6 z authority external links

**Zmiany w prompcie LLM:**

- **Punkt 15 (NOWY):** `external_links` — lista 2-3 linków zewnętrznych DoFollow do źródeł wysokiego autorytetu.
  Każdy link to dict: `{"url": "...", "anchor_text": "...", "reason": "..."}`
  
  Zasady E-E-A-T:
  - Wikipedia PL (artykul tematyczny)
  - Strony `.gov.pl` (sejm.gov.pl, gov.pl, prezydent.pl, mon.gov.pl)
  - Agencje prasowe: PAP (pap.pl), Reuters, AP
  - Think-tanki: PISM, OSW, uniwersytety
  - YouTube (link do oryginalnego wideo)

- **Punkt 8 (article_body) — rozszerzony:** Instrukcja MUSISZ wplać MINIMUM 2 linki DoFollow w article_body używając format `<a href="URL" target="_blank">naturalny anchor text</a>`. Przykłady naturalnych wpleceń podane w prompcie.

- **JSON template — rozszerzony:** Dodano `external_links` do odpowiedzi JSON.

### 2. `core/generator.py` — process_video() logging

- D10 logging: liczba wygenerowanych external_links + szczegóły URL/reason per link
- Warning jeśli LLM zwrócił 0 linków (oczekiwane 2-3)
- Summary log z `ext_links=N`

### 3. `core/injector.py` — BRAK ZMIAN (weryfikacja OK)

**Dlaczego brak zmian:**
- `article_body` z tagami `<a href>` trafia do `<!-- wp:html -->` blocków które są pass-through (nie strippują HTML)
- WP REST API akceptuje `<a>` tagi w polu `content`
- D4 `_build_external_link_block()` już używa `rel="noopener"` (bez `noreferrer` — naprawione w D7)
- **Wniosek:** linki `<a>` w article_body przetrwają injection do WP bez zmian

## DEPLOY

- VPS: `git pull` + `docker compose build vse-api` + `up -d vse-api`
- Health: `{"status":"ok","version":"2.0.0","llm_default":"claude"}` ✅

## WERYFIKACJA

- ✅ Commit `feb2ed4` na `main`
- ✅ Build success + container restarted
- ✅ Health endpoint OK
- ✅ Prompt zawiera punkt 15 (external_links) + instrukcję DoFollow w article_body
- ✅ JSON template zawiera `external_links` pole
- ✅ Injector nie strippuje `<a>` tagów (wp:html pass-through)

## UWAGA DLA NASTĘPNEJ SESJI

Pełna weryfikacja end-to-end wymaga wywołania `POST /v1/generate` z prawdziwym video URL i sprawdzenia:
1. Czy `external_links` zawiera 2-3 itemy z realnymi URL-ami
2. Czy `article_body` zawiera tagi `<a href=` do external sources
3. Czy po inject do WP linki są widoczne w artykule

To wymaga API call z kluczem LLM — wykracza poza zakres tej sesji kodu.

---

*[vse-dev-25 | video-seo-engine 21.06.2026 00:55] — raport D10 kompletny*
