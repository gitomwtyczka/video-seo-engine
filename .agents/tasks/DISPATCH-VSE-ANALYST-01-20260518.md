# DISPATCH: Pełna rekonstrukcja kontekstu — video-seo-engine

**Do:** `[vse-analyst-01]`
**Workspace:** video-seo-engine
**Priorytet:** 🟡 P1 — orientacja strategiczna
**Od:** `[fleet-strateg-01 | shadow-perihelion]`
**Data:** 2026-05-18T20:14 CEST

---

## Środowisko operacyjne

- **OS:** WSL2/Linux natywny (Jagodziak4)
- **Shell:** `run_command` (bash) — zero stellar-relay, zero PowerShell
- **SSH:** aliasy w `~/.ssh/config` — `oracle-crimson`, `vultr-llm`, `cyberfolks`

---

## Cel

Rekonstrukcja pełnego kontekstu prac nad `video-seo-engine` z ostatnich ~5-7 dni.
Supervisor sygnalizuje, że ostatnia intensywna faza dotyczyła **zgodności treści wstrzykiwanej do WordPress z artykułowym standardem redakcyjnym** — wypracowanym pierwotnie w shadow-perihelion.

Twój raport ma odpowiedzieć na pytanie: **co dokładnie zostało zrobione, co zostało na stole, i jaki był kierunek?**

---

## KROK 0 — Środowisko

```bash
# Sprawdź kontekst projektu
cat /home/tobroz/projects/video-seo-engine/AGENTS.md
cat /home/tobroz/projects/video-seo-engine/knowledge/video-seo-pipeline.md
cat /home/tobroz/projects/video-seo-engine/README.md
```

---

## KROK 1 — Git log (pełne commit messages)

```bash
git -C /home/tobroz/projects/video-seo-engine log --format="%h %ai %s%n%b" | head -150
```

Szukaj commitów dotyczących:
- WordPress article format / standard artykułu
- Zgodność z redakcyjnym pipeline (Kurier365, prawy.pl)
- Schema compliance / injection zmian
- Thumbnail, RankMath, ALT, meta description
- Batch processing

---

## KROK 2 — Brain dirs z okresu prac (13-17 maja)

Przeszukaj overview.txt najnowszych brain dirs. Priorytet:

```bash
# Znajdź brain diry z maja 13-17 (wg daty modyfikacji)
ls -lt /home/tobroz/.gemini/antigravity/brain/ | grep "May 1[3-7]"
```

Dla każdego znalezionego — przeczytaj overview.txt:
```bash
cat /home/tobroz/.gemini/antigravity/brain/{ID}/.system_generated/logs/overview.txt 2>/dev/null | head -100
```

**Szczególnie interesujące brain diry (z listy najnowszych):**
- `127f18d4-849e-41fc-9017-19ecba49a97e` (May 17)
- `dd56b234-8cfa-4e1f-82ba-c22a7ef878da` (May 17)
- `5ae65c75-b137-4670-b912-dad74ee43a0f` (May 17)
- `ad2700e5-264a-464c-a4c4-34303b89aef2` (May 17)
- `7d51fd71-535c-410c-8814-c19d1b845443` (May 17)
- `79798d9e-3144-4ae7-b077-c9a4bc5b8aad` — "hero-worker 01 | shadow-perihelion 01.05.2026" (May 14)
- `4c0ac986-9dff-4e74-9ffd-e828d339f425` — "Auditing Missing Conversation History" (May 13)

---

## KROK 3 — Pliki kodu (zmiany po 13 maja)

```bash
find /home/tobroz/projects/video-seo-engine -name "*.py" -newer /home/tobroz/projects/video-seo-engine/.agents/reports/2026-05-13_vse-architect-01_validate-01.md | sort
```

Dla każdego znalezionego pliku — przeczytaj i zrozum ostatnie zmiany vs gitlog.

Szczególna uwaga na:
- `core/generator.py` — standard generowanego artykułu
- `core/injector.py` — co trafia do WP
- `batch_seo_generate.py` / `batch_inject.py` — jak wygląda batch
- `inject_rest_v5.py` — legacy injector (porównaj z nowym)

---

## KROK 4 — Standard artykułu w shadow-perihelion

Szukaj w shadow-perihelion śladów "standardu artykułu":

```bash
find /home/tobroz/projects/shadow-perihelion -name "*.md" | xargs grep -l -i "standard\|artykuł\|editorial\|format\|schema" 2>/dev/null | head -10
```

Sprawdź też knowledge base Supervisora (sonic-void):
```bash
ls /home/tobroz/projects/sonic-void/.agents/ 2>/dev/null
find /home/tobroz/projects/sonic-void -name "*.md" -path "*knowledge*" 2>/dev/null | head -10
```

---

## KROK 5 — Raporty z video-seo .agents

```bash
cat /home/tobroz/projects/video-seo-engine/.agents/reports/2026-05-13_vse-architect-01_faza1-complete.md
cat /home/tobroz/projects/video-seo-engine/.agents/reports/2026-05-13_vse-architect-01_validate-01.md
```

---

## DELIVERABLE

Napisz raport w formacie:

### Sekcja 1: TIMELINE — co kiedy
Chronologia prac z dokładnymi datami (gitlog + brain diry).

### Sekcja 2: STAN TECHNICZNY — co jest gotowe
- Które moduły, w jakiej wersji, zwalidowane czy nie

### Sekcja 3: STANDARD ARTYKUŁU — co wypracowano
- Co to jest "standard artykułu" z shadow-perihelion
- Jak generator.py/injector.py próbuje go respektować
- Jakie były ostatnie prace w tym obszarze (ALT, RankMath, meta, thumbnail?)

### Sekcja 4: CO ZOSTAŁO NA STOLE
- Niezamknięte zadania
- Otwarte pytania
- Batch 210 — stan i plan

### Sekcja 5: REKOMENDACJA — od czego zacząć
Jedna konkretna sugestia dla Stratega: co robić jako pierwsze.

---

## Raportowanie

```
write_to_file → /home/tobroz/projects/video-seo-engine/.agents/reports/2026-05-18_vse-analyst-01_context-recon.md
```

Dodatkowo wyślij kopię do Stratega:
```
write_to_file → /home/tobroz/projects/shadow-perihelion/.agents/reports/inbox/2026-05-18_vse-analyst-01_to_strateg.md
```

---

*[fleet-strateg-01 | shadow-perihelion | 2026-05-18T20:14 CEST]*
