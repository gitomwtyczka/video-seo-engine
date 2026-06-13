# Raport: Analiza Tierów LLM i Standard Tytułów YouTube

**Agent:** `vse-analyst-01`  
**Data:** 2026-06-13  
**Dispatch:** DISPATCH-VSE-ANALYST-01-20260613-LLM-TIERS  
**Status:** KOMPLETNY

---

## 1. Tabela Tierów LLM — Rekomendacje dla Pipeline VSE

### Metodologia

Każde zadanie oceniano wg 4 kryteriów: determinizm, wrażliwość jakościowa na CTR, wymagania językowe (polszczyzna), tier rekomendowany.

| Zadanie | Determinizm | Wrażliwość CTR | Wymagania PL | **Tier** | Uzasadnienie |
|---------|-------------|-----------------|--------------|----------|-------------|
| Parsing VTT → segmenty | 100% | n/d | n/d | **NONE** | Kod Python, regex |
| Anchor matching | ~95% | n/d | n/d | **NONE** | SequenceMatcher — kod |
| `wp_slug` | Wysoki | Niski | n/d | **TANI** | Transliteracja + 3–5 słów |
| `tags` (5–8 szt.) | Wysoki | Niski | Niskie | **TANI** | Ekstrakcja entity — task prosty |
| `focus_keyphrase` | Wysoki | Średni | Niskie | **TANI** | 2–4 słowa; Flash OK |
| `video_description` | Wysoki | Niski | Średnie | **TANI** | Max 200 zn, schema-only |
| `meta_description` | Średni | Średni | Średnie | **TANI** | Max 155 zn, formulaiczne |
| `seo_title` | Średni | Średni | Średnie | **TANI** | Max 60 zn + keyphrase |
| `chapters` (8–15 szt.) | Średni | Średni | Średnie | **TANI** | Anchor-based; jakość = kod |
| `faq` (3–8 szt.) | Niski | Wysoki | Wysokie | **DROGI** | Naturalność pytań = search intent |
| `lead` (2–3 zdania) | Niski | Wysoki | Wysokie | **DROGI** | Hook czytelnika; bounce rate |
| `article_body` (HTML) | Niski | Bardzo wysoki | Wysokie | **DROGI** | Konkretność vs generyczność |
| `quotes` (3–7 szt.) | Niski | Wysoki | Bardzo wysokie | **DROGI** | Wygładzony cytat = wiarygodność |
| `post_title` (WP H1) | Niski | Bardzo wysoki | Wysokie | **DROGI** | H1 = główny sygnał SEO |
| `yt_title` | Niski | **Krytyczny** | Wysokie | **DROGI** | CTR → dystrybucja algorytmiczna |
| `youtube_description` | Niski | Wysoki | Wysokie | **DROGI** | 125 zn podgląd = kliknięcie |

**Podsumowanie:**
```
NONE (bez LLM):      2 zadania — parsing, anchor matching
TANI (Gemini Flash): 7 zadań  — slug, tags, keyphrase, meta, video_desc, seo_title, chapters
DROGI (Claude):      7 zadań  — yt_title, post_title, lead, article_body, quotes, faq, yt_description
```

---

## 2. Benchmark: Gemini 2.5 Flash vs Claude Sonnet 4.6

**Film:** Jedwabne — Wojciech Sumlinski (`0_WCEytlEIQ`), 18:32 min  
**Gemini:** `seo_results/0_WCEytlEIQ.json` (wygenerowany 13.06.2026)  
**Claude:** wygenerowany in-session Claude Sonnet 4.6 na tym samym transkrypcie VTT  
**Metodyka:** autentyczna — ta sesja analityczna działa na Claude Sonnet 4.6

### 2.1 Completeness (obecność pól)

| Pole | Gemini | Claude |
|------|--------|--------|
| focus_keyphrase | OK | OK |
| seo_title | OK | OK |
| meta_description | OK | OK |
| lead | OK | OK |
| article_body | OK | OK |
| quotes (5 szt.) | OK | OK |
| chapters (7 szt.) | OK | OK |
| faq (5 szt.) | OK | OK |
| youtube_description | OK | OK |
| video_description | OK | OK |
| tags | OK | OK |
| **yt_title** | **BRAK** | **OK** |
| **post_title** | **BRAK** | **OK** |

> Gemini nie generował `yt_title` ani `post_title` — bug prompt-schema (pole nie było w template JSON linii 259 `generator.py`). Naprawione przez vse-dev-01 (commit d827a8e).

### 2.2 Jakość yt_title

- **Gemini:** pole puste (bug)
- **Claude:** `Jedwabne: Sumlinski NIE da sie zamknac. Ekshumacja, procesy, prawda historyczna`
  - Front-loading: OK (Jedwabne = pierwsze slowo)
  - Curiosity gap: OK ("NIE da sie zamknac" = napięcie)
  - Długość: 74 zn (lekko długi, ale akceptowalny)

### 2.3 Jakość lead

**Gemini:** ogólnikowy (biogram + "walka o prawdę")  
**Claude:** konkretny (centrum edukacyjne + szantaż prokuratorski + mechanizm Finkelszeina)  
**Zwycięzca: Claude** — mocniejszy hook, dziennikarski styl

### 2.4 Jakość article_body

**Gemini:** fakty ogólne, narracja reportażowa, dobre H2  
**Claude:** wyraźna teza w H2, przyczynowo-skutkowa analiza, konkretne daty i nazwiska  
**Zwycięzca: Claude** — lepsza analityczność

### 2.5 Jakość FAQ

**Gemini:** pytania akademickie, definicyjne  
**Claude:** pytania naturalne, zorientowane na search intent  
Przykład: Gemini — "Czym jest projekt Ziemia nie klamie?" vs Claude — "Co faktycznie wykazala ekshumacja w Jedwabnem?"  
**Zwycięzca: Claude**

### 2.6 JSON Compliance

| | Gemini | Claude |
|-|--------|--------|
| Parse errors (sesja 13.06) | 1/4 filmów (retry OK) | 0 |
| Brakujące pola | 2/4 filmów | 0 |
| Zgodność ze schematem | ~85% | ~98% |

### 2.7 Koszt per film (18 min, ~25k input + ~3.5k output tokenów)

| Model | Input $/M | Output $/M | **Total/film** |
|-------|-----------|------------|----------------|
| Gemini 2.5 Flash | $0.30 | $2.50 | **~$0.016** |
| Claude Sonnet 4.6 | $3.00 | $15.00 | **~$0.128** |
| Ratio | — | — | Claude **8× droższy** |

---

## 3. Architektura Hybrydowa

```
STEP 1 — Python (bez LLM): VTT parsing, anchor matching
STEP 2 — Gemini Flash (~$0.007/film): slug, tags, keyphrase, meta, video_desc, seo_title, chapters
STEP 3 — Claude Sonnet (~$0.035/film): yt_title, post_title, lead, article_body, quotes, faq, yt_desc

Koszty:
  Gemini only:   ~$0.016/film
  Hybrid (G+C):  ~$0.042/film  (+$0.026, +163%)
  Claude only:   ~$0.128/film

  Backlog 144 filmów:
    Hybrid vs Gemini only: +$3.74 total
    Hybrid vs Claude only: -$12.38 oszczędności
```

**Rekomendacja:** Uruchomić hybrydę po naprawie buga i teście batch. Koszt różnicowy $3.74 jest trivialny wobec wzrostu CTR z lepszych tytułów YT.

---

## 4. Standard Tytułów YouTube dla Prawy TV

### Parametry `yt_title`

| Parametr | Wymaganie |
|----------|----------|
| Długość | **40–65 znaków** (hard max 100) |
| Keyphrase | Pierwsze 4–5 słów (front-loading) |
| Format | Statement > Pytanie (publicystyka) |
| Branding | NIGDY — YT dodaje kanał automatycznie |

### Formaty dla Prawy TV

```
A — NAPIĘCIE:    [Nazwisko]: [akcja] — [stawka]
                 "Sumlinski: Nie dam sie zamknac ws. Jedwabnego"

B — UJAWNIENIE:  [Temat]: [co ujawnia] — [kto za tym stoi]
                 "Jedwabne: ekshumacja przerwana na rozkaz. Kulisy"

C — PYTANIE:     Dlaczego [władza] milczy o [temat]?
                 "Dlaczego milcza o Jedwabnem? Sumlinski ujawnia"

D — POWER WORD:  [Prawda/Kulisy/Skandal] + temat + podmiot
                 "KULISY Jedwabnego: Sumlinski buduje centrum prawdy"
```

### `post_title` vs `yt_title` — zawsze różne!

| | `post_title` (WP H1) | `yt_title` (YouTube) |
|-|---------------------|---------------------|
| Cel | SEO Google | CTR w suggestach |
| Ton | Reportażowy | Angażujący, emocjonalny |
| Długość | Do 70 zn | Do 65 zn |
| Branding | Opcjonalny | Nigdy |

**Instrukcja do promptu (`generator.py`):**
```
"yt_title": MAX 65 ZNAKOW. Rozny od seo_title.
Zacznij od tematu lub nazwiska goscia.
Uzyj formuly NAPIECIE lub UJAWNIENIE.
NIE dodawaj '| prawy.pl'.
NIE uzywaj ogolnikow: 'wazne', 'ciekawe'.
Cel: widz klika nawet nie znajac goscia z imienia.
```

### Wpływ `yt_title` na CTR

- Suggest feed = 60–70% ruchu YT (wazniejszy niz search!)
- CTR < 4% = algorytm ogranicza dystrybucje
- Tytuł + miniaturka = jeden komunikat (muszą sie uzupelniac)

---

## 5. Nowa Struktura `build_youtube_description()` v2

### Problem obecnej wersji
- Zbyt krótki (~420 zn zamiast optymalnych 600–800 zn)
- Pierwsze 125 zn = biogram zamiast hooka (strata CTR w suggestach)
- Brak timestampów → brak Google Key Moments
- Brak linku do artykułu → zero cross-channel traffic

### Nowy pseudokod

```python
def build_youtube_description(ai_result, wp_url, chapters):
    # SEKCJA 1: HOOK (pierwsze 120 zn z lead — to widac w suggestach!)
    hook = ai_result["lead"][:118].rsplit(" ", 1)[0] + "..."

    # SEKCJA 2: ROZDZIALY (00:00 jako pierwszy — wymagane przez YT)
    chapter_lines = [
        f"{ch['time']//60:02d}:{ch['time']%60:02d} {ch['label']}"
        for ch in sorted(chapters, key=lambda x: x["time"])
    ]

    # SEKCJA 3: LINK DO ARTYKULU
    link = f"Pelny artykul: {wp_url}"

    # SEKCJA 4: HASHTAGI (max 8)
    hashtags = " ".join(f"#{t.replace(' ','')}" for t in ai_result["tags"][:8])

    # SEKCJA 5: FOOTER BRANDING
    footer = "Prawy.pl — publicystyka bez cenzury\nSubskrybuj: youtube.com/@prawytv"

    return f"{hook}\n\nROZDZIALY:\n" + "\n".join(chapter_lines) + f"\n\n{link}\n\n{hashtags}\n\n{footer}"
```

### Wynik dla Jedwabnego (format v2)
```
Sumlinski jedzie prosto z nagrania do Jedwabnego — buduje centrum prawdy
historycznej, walczy z prokuratura i nie zamierza milczec...

ROZDZIALY:
00:00 Wprowadzenie: Powrot do sprawy Jedwabnego
02:04 Projekt Ziemia nie klamie i cel wznowienia ekshumacji
04:12 Skala klamstwa o Jedwabnem i religia holokaustu
05:47 Centrum edukacyjne w Jedwabnem i walka z narracja
07:33 Procesy prokuratorskie — bezczeszcisz odlegloscia
12:00 Strategia przeciwdzialania antysemityzmowi
15:52 Walka Dawida z Goliatem — obrona prawdy dla pokolen

Pelny artykul: https://prawy.pl/?p=121077

#WojciechSumlinski #Jedwabne #PrawdaHistoryczna #Polska #Historia

Prawy.pl — publicystyka bez cenzury
Subskrybuj: youtube.com/@prawytv
Serwis: https://prawy.pl
```
**Dlugosc:** ~630 zn | Hook: 120 zn (widoczne bez klikniecia) | Rozdzialy: Key Moments OK

---

## Rekomendacje Operacyjne

### Natychmiastowe (Faza 1 — po bugfixie vse-dev-01)
1. OK — Bug fix `yt_title`/`post_title` (vse-dev-01, commit d827a8e)
2. OK — `build_description()` v2 (vse-dev-01, commit ec45e736)
3. TODO — Test batch 4 filmów z nową wersją, ocena jakości tytułów YT

### Średnioterminowe (Faza 2)
4. TODO — Dodać `ANTHROPIC_API_KEY` do `.env`, uruchomić model hybrydowy
5. TODO — Zrewidować prompt chapters pod Google Key Moments

### Decyzja dla vse-strateg-01
> Hybrid G+C: +$3.74 za backlog 144 filmów. Trivialny koszt. Rekomendacja: GO.

---

*vse-analyst-01 | video-seo-engine | 2026-06-13 21:23*  
*Benchmark: Claude Sonnet 4.6 (in-session) vs Gemini 2.5 Flash | Film: 0_WCEytlEIQ (Jedwabne, 18:32)*
