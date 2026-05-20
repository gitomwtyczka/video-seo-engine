# DISPATCH: Optymalizacja tytułów — YT + WordPress SEO
**Od:** Supervisor 01 (sonic-void)
**Do:** vse-strateg-01 (video-seo-engine)
**Data:** 2026-05-20
**Priorytet:** 🔴 Wysoki — PRZED uruchomieniem kolejnych batch'ów

---

## ⚡ KROK 0 — Zanim cokolwiek

### 0a. Przedstaw się + Vitals (jedna linia, góra i dół każdej wiadomości)

```
[vse-strateg-01 | video-seo-engine 2026-05-20 HH:MM] 📊 V1:0/40 🟢 V2:1str 🟢 V3:0pl 🟢 V4:stabilny V5:ok — online
```

Aktualizuj linię vitals co 3-5 kroków lub przy zmianie stanu (ta sama linia na dole każdej wiadomości z aktualnym stanem).

### 0b. Heartbeat
```bash
echo '{"callsign":"vse-strateg-01","status":"working","current_task":"DISPATCH-TITLES planning","timestamp":"'$(date -Iseconds)'"}' > /home/tobroz/projects/video-seo-engine/.agents/heartbeat.json
```

### 0c. Kontekst (przeczytaj przed planowaniem)
```
view_file → /home/tobroz/projects/video-seo-engine/.agents/knowledge/video-seo-pipeline.md
view_file → /home/tobroz/projects/video-seo-engine/AGENTS.md
view_file → /home/tobroz/projects/video-seo-engine/.agents/reports/2026-05-19_vse-dev-01_session-handoff.md
```

---

## Kontekst decyzji

Pipeline VSE generuje i wstrzykuje SEO (VideoObject, Clip, FAQ, RankMath meta) do artykułów WordPress.
Brakuje kluczowego elementu: **optymalizacja tytułów**.

Obecny stan:
- Tytuły WP postów — bez zmian (oryginalne z importu, często słabe SEO)
- Tytuły YT filmów — bez zmian (redakcja Prawy TV, często bez słów kluczowych)
- `seo_title` z Gemini trafia do RankMath, **ale NIE nadpisuje `post_title` w WP**
- `yt_admin.py` potrafi aktualizować opis YT przez OAuth — nie obsługuje tytułów

**Decyzja Supervisora:** tytuły muszą być SEO-zoptymalizowane i skorelowane z treścią artykułu zanim ruszą kolejne batch'e injekcji.

---

## Zadanie — zaprojektuj i zaplanuj feature "Title Sync"

### Zakres funkcjonalny

**A. WordPress — title optimization**
- Generator (Gemini) tworzy już `seo_title` — należy go wstrzykiwać do `post_title` WP (nie tylko do RankMath)
- Opcja: osobna wersja tytułu dla `post_title` (h1 na stronie) vs `rank_math_title` (tag `<title>`, może być dłuższy)
- Zasada korelacji: `post_title` musi zawierać `focus_keyphrase`

**B. YouTube — title optimization**
- `yt_admin.py` obsługuje `videos.update` przez OAuth właściciela kanału (credentials gotowe)
- Tytuł YT powinien być zoptymalizowany pod: słowa kluczowe + clickbait + długość (max 100 znaków)
- Musi być **skorelowany** z tytułem artykułu — te same główne słowa kluczowe, inna forma (YT bardziej angażujący)
- Nie może się powtarzać dosłownie (YT ma własne SEO)

**C. Zasada projektowa**
- Gemini generuje **komplet**: `post_title`, `seo_title` (RankMath), `yt_title` — w jednym prompcie
- Wszystkie trzy muszą zawierać `focus_keyphrase`
- `yt_title` ≤ 100 znaków, angażujący, z pytaniem lub emocją
- `post_title` — SEO-first, naturalne słowa kluczowe
- `seo_title` — może być dłuższy (do 60 znaków dla SERP), z branding pipe: `| Prawy TV`

---

## Twoje zadanie (strateg)

### 1. Analiza techniczna (z vse-analyst-01 lub samodzielnie)

Sprawdź:
- Jak wygląda aktualny prompt w `core/generator.py` (sekcja generowania `seo_title`)
- Czy `core/injector.py` ma już logikę `post_title` update czy tylko RankMath
- Czy `core/yt_admin.py` ma metodę `update_title()` czy tylko `update_description()`

### 2. Zaprojektuj architekturę feature

Przygotuj plan implementacji zawierający:
- Zmiany w prompcie Gemini (nowe pola: `post_title`, `yt_title`)
- Zmiany w `core/generator.py` (output schema)
- Zmiany w `core/injector.py` (wstrzykiwanie `post_title` do WP REST API)
- Nowa metoda w `core/yt_admin.py`: `update_title(video_id, yt_title)`
- Nowa komenda CLI: `vse update-titles --video YT_ID` (opcjonalnie: `--wp-only`, `--yt-only`)
- Jak obsłużyć istniejące SEO JSONy — czy regenerować prompt czy patch w locie

### 3. Dispatch dla vse-dev-01

Po zatwierdzeniu przez Supervisora — wyślij dispatch implementacyjny do `vse-dev-01`.

**Dispatcher gate:** raport do Supervisora ZANIM cokolwiek zostanie zaimplementowane.

---

## Raport końcowy

**Ścieżka lokalna:**
```
/home/tobroz/projects/video-seo-engine/.agents/reports/2026-05-20_vse-strateg-01_titles-plan.md
```

**Kopia do Supervisora (GitHub MCP):**
```
mcp_github_create_or_update_file:
  owner: gitomwtyczka
  repo: sonic-void
  branch: master
  path: .agents/reports/inbox/2026-05-20_vse-strateg-01_titles-plan.md
  message: "report: vse-strateg-01 titles-plan"
```

Raport musi zawierać:
- Analiza stanu obecnego (co jest, czego brakuje)
- Proponowana architektura feature
- Szacowany nakład (liczba plików, złożoność zmian)
- Pytania do Supervisora (jeśli są)

---

*[Supervisor 01 | sonic-void | 2026-05-20]*
