# Raport wdrożenia K1+K2 — Generator Performance & Single-Pass Watching Page

- **Callsign:** vse-dev-k1
- **Data:** 2026-10-20
- **Workspace:** video-seo-engine
- **Status:** SUKCES (Merged & Deployed)

---

## 1. Metryki wdrożenia i identyfikatory
- **PR:** #2 (https://github.com/gitomwtyczka/video-seo-engine/pull/2)
- **Merge Commit SHA:** `ca8bd7a220577bdce53f8d58ebd9a021ca39448b`
- **Branch źródłowy:** `k1-generator-perf` (commit `16c23343ca522bfe6c898f6c7c196a82c4938ba8`)
- **Snapshot TAG (VPS):** `20261020-210157`
- **Kopia konfiguracji w snapshot:** `/home/ubuntu/rollback/20261020-210157/config/` (`.env`, `docker-compose.vse.yml` z uprawnieniami 600)
- **Komenda Rollback (PowerShell):**
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "/home/ubuntu/scripts/vse_rollback.sh 20261020-210157 --code"
```

---

## 2. Wyniki weryfikacji produkcyjnej na VPS (Krok 4)
- `docker logs --tail 40 vse-api`: brak tracebacków, start w 1.2s, port 8085 aktywny, baza danych i migracje OK.
- `docker exec vse-api python -c "import core.generator"`: `IMPORT SUCCESS`.
- `curl -s -o /dev/null -w "%{http_code}" https://vse.impresjapr.pl/docs`: **HTTP 200**.

---

## 3. Pomiary E2E w kontenerze produkcyjnym (Krok 5)
Wykonano pełny przebieg generowania w kontenerze `vse-api` dla filmu ~25 min (49 845 znaków transkryptu VTT) z Claude Sonnet (`publication_type="watching_page"`):

| Parametr | Przed zmianą (K1/K2) | Po zmianie (K1/K2) | Ocena |
|---|---|---|---|
| **Czas łączny** | ~300 s (5 min) | **54.8 s** | **Skrócenie czasu o 82%** |
| **Czas PASS 1** | ~194 s | **54.3 s** | Bez przepisywania transkryptu |
| **PASS 2** | Wywoływany zawsze (~81-97 s) | **Pominięty (SKIPPED)** | `article_engine: pass1_watching_page` |
| **Liczba tokenów wyjściowych** | ~8192 (obcięcie) | **2 737 tokenów** | Bezpieczny margines |
| **Długość article_body** | ~1300 słów | **136 słów** (973 znaki, 2 akapity) | Idealna objętość watching_page |
| **Nagłówki H2/H3 w article_body** | Kilka nagłówków H3 + H2 Podsumowanie | **0 (H2: 0, H3: 0)** | Zgodne z wytycznymi |
| **JSON syntax / repair** | Wymagane naprawy json-repair | **Pierwsza próba poprawna** (retry=False) | Stabilny format JSON |
| **Wykrycie LLM_TRUNCATED** | Obcięcie bez ostrzeżenia | **Brak obcięcia** (warning nie wystąpił) | Mechanizm aktywny |
| **clean_transcript** | Wolne generowanie przez LLM | **49 343 znaki**, start od `[00:00]` | Regułowe w Pythonie (0 tokenów) |

---

## 4. Wdrożone usprawnienia skryptów snapshot/rollback (Krok 2)
- Rozszerzono `/home/ubuntu/scripts/vse_snapshot.sh` o automatyczną kopię `.env` oraz plików zdefiniowanych w `env_file:` w `docker-compose.vse.yml` z uprawnieniami `chmod 600` i katalogiem `chmod 700`.
- Zaktualizowano `/home/ubuntu/scripts/vse_rollback.sh`, aby przy fladze `--code` przywracał również pliki konfiguracyjne z migawki.
