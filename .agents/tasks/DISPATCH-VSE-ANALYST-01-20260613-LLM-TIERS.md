# DISPATCH-VSE-ANALYST-01-20260613-LLM-TIERS

**Agent:** `vse-analyst-01`  
**Od:** `vse-strateg-01`  
**Data:** 2026-06-13  
**Priorytet:** HIGH  
**Status:** OPEN

---

## Kontekst

Pipeline VSE używa obecnie Gemini 2.5 Flash do generowania całego pakietu SEO (tytuły, opisy, rozdziały, FAQ, lead, article_body). Rozważamy przejście na Claude (Anthropic) lub model hybrydowy: tani model do części zadań + Claude do jakościowych.

Dzisiaj (2026-06-13) przetworzyliśmy 4 filmy — wyniki widoczne w `seo_results/`. Obserwacje z sesji:
- Gemini 2.5 Flash: 1 JSON parse error na 4 próby (film: Jedwabne — retry OK)
- `post_title` i `yt_title` puste w 2/4 JSONach (VfCPRMNN7Ek, DiKQfumYiEk)
- Tytuły YouTube NIE były aktualizowane w inject (brak `yt_title` w odpowiedzi)
- Opisy YouTube krótkie — brak głębi, generyczne frazy

---

## Zadanie analityczne

### 1. Analiza tierów LLM dla pipeline VSE

Oceń każde z zadań pipeline pod kątem: **czy wymaga drogiego modelu czy wystarczy tani?**

| Zadanie | Opis | Rekomendacja tier | Uzasadnienie |
|---------|------|-------------------|--------------|
| Parsing VTT → segmenty | Kod Python, deterministyczny | - | Bez LLM |
| Anchor matching | Kod Python, fuzzy search | - | Bez LLM |
| focus_keyphrase | 2-4 słowa z transkryptu | ? | |
| post_title (H1) | SEO-first, PL gramatyka | ? | |
| seo_title | Max 60 znaków | ? | |
| yt_title | Max 100 zn, viralowy | ? | |
| wp_slug | URL z transliteracją | ? | |
| meta_description | Max 155 zn | ? | |
| lead | 2-3 zdania, 300 zn | ? | |
| article_body | HTML 1000-1500 zn, 3-5 p | ? | |
| chapters (8-15 szt) | Anchor-based, z transkryptu | ? | |
| quotes (3-7 szt) | Cytat wygładzony + anchor | ? | |
| faq (3-8 szt) | Pytania i odpowiedzi | ? | |
| video_description | Max 200 zn, dla schema | ? | |
| youtube_description | Wstęp + rozdziały + footer | ? | |
| tags | 5-8 tagów | ? | |

### 2. Benchmark jakości — Gemini vs Claude

Wykonaj test porównawczy na **jednym filmie z gapu** (użyj `subs/0_WCEytlEIQ.pl.vtt` — Jedwabne, 18:32):

- Wygeneruj SEO JSON przez Gemini 2.5 Flash (już gotowy: `seo_results/0_WCEytlEIQ.json`)
- Wygeneruj SEO JSON przez Claude Sonnet 4.5 (`claude-sonnet-4-5` przez `anthropic` SDK)
- Porównaj:
  - Jakość polszczyzny (naturalność, brak robotycznego stylu)
  - Jakość tytułu YT (czy angażuje? czy zawiera keyphrase?)
  - Jakość article_body (konkretność vs generyczność)
  - Jakość FAQ (pytania realne czy sztuczne?)
  - JSON compliance rate (ile parse errors w 5 próbach)
  - Czas generacji
  - Koszt (cena za 1 film przy ~30k tokenów)

### 3. Model hybrydowy — propozycja architektury

Zaproponuj optymalny podział kosztów:
```
Cheap model (Gemini Flash / GPT-4o-mini):
  → zadania X, Y, Z

Claude Sonnet:
  → zadania A, B, C

Estymowany koszt/film:
  Obecny (Gemini Flash only): X USD
  Proponowany (hybrid): Y USD
  Claude only: Z USD
```

### 4. Standard tytułów YouTube — Google SEO 2026

Zbadaj i udokumentuj aktualny standard Google/YouTube dla tytułów:
- Optymalna długość (znaki, słowa)
- Pozycja frazy kluczowej (front-loading?)
- Format: pytanie vs statement vs emoji?
- Różnica między `post_title` (WP H1) a `yt_title` (YouTube) — kiedy powinny być różne?
- Przykłady dobrych tytułów z polskiego YT (news/publicystyka)
- Jak tytuł YT wpływa na CTR w suggestach?

### 5. Standard opisów YouTube — analiza długości i struktury

Ocena obecnych opisów (krótkie — user feedback: "skąpe"):
- Jaka jest optymalna długość opisu YT dla publicystyki? (znaki)
- Które sekcje są obowiązkowe dla SEO? (pierwsze 125 zn = podgląd)
- Czy rozdziały w opisie faktycznie poprawiają ranking?
- Zaproponuj nową strukturę `build_description()` z dłuższym intro

---

## Deliverable

Raport `2026-06-13_vse-analyst-01_llm-tiers-yt-titles.md` zapisz w:
- `video-seo-engine/.agents/reports/`
- `sonic-void/.agents/reports/inbox/` (dual-write)

Raport musi zawierać:
1. Tabela tier rekomendacji (pełna)
2. Benchmark Gemini vs Claude na Jedwabne
3. Propozycja architektury hybrydowej z kosztami
4. Standard tytułów YT dla Prawy TV (gotowy do implementacji)
5. Nowa struktura `build_description()` — pseudokod lub diff

---

*Dispatch by: vse-strateg-01 | 2026-06-13 20:31*
