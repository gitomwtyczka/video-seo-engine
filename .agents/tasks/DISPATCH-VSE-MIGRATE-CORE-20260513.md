# DISPATCH: video-seo-engine — Migracja Generatora i Injectora

**ID:** DISPATCH-VSE-MIGRATE-CORE-20260513
**Autor:** Supervisor 01
**Data:** 2026-05-13
**Priorytet:** 🔴 WYSKOKI
**Agent:** vse-dev 01
**Workspace:** video-seo-engine
**Rola:** Worker/Dev

## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**0. Wczytaj blok systemowy (skills + file bridge + protokół):**
view_file → C:\Users\tomas2\.gemini\antigravity\playground\video-seo-engine\.agents\AGENTS.md

## 🎯 Cel zadania (Deliverable)

Migracja pozostałych skryptów z lokalnego środowiska do nowej, obiektowej i zrefaktoryzowanej struktury `video-seo-engine`.

1. Refaktoryzacja `test_full_seo_v4.py` (który User wkleił lokalnie) do `core/generator.py`. Skrypt ten ma generować poprawną strukturę VideoObject. Zmiany: logowanie (`logging`), type hints, uniezależnienie od hardcodowanych ścieżek, parametryzacja pod wiele portali (użycie zmiennych środowiskowych).
2. Refaktoryzacja `inject_rest_v5.py` do `core/injector.py`. Ma odpowiadać za komunikację z WordPress REST API i iniekcję wygenerowanego schematu.
3. Utworzenie ujednoliconego CLI w `cli/unified_cli.py` (lub zaktualizowanie istniejącego), które zepnie `fetcher.py`, `matcher.py`, `generator.py` oraz `injector.py` w działający end-to-end pipeline.

## 📝 Wytyczne Architektoniczne

- Żadnego hardcodowania adresów (np. `https://prawy.pl`). Użyj `os.environ.get('WP_BASE_URL')` oraz modułu `dotenv`.
- Żadnych twardych ścieżek Windows (np. `D:\Biblioteki\...`). Użyj ścieżek relatywnych do `os.getcwd()` lub argumentów CLI.
- Zamień `print()` na systemowy `logging`.
- Każdą funkcję publiczną udokumentuj (docstrings) i otypuj (type hints).
- Zachowaj rygor względem standardu Video Schema v5.3 (usuwamy Quotation, wymuszamy duration ISO, etc. - sprawdź `AGENTS.md`).

## ✅ Weryfikacja

Po refaktoryzacji, dodaj proste testy w katalogu `tests/` dla `generator.py` i upewnij się, że poprawnie przetwarza on mockowane dane metadanych z YouTube.

## 🏁 Zakończenie

1. Przeprowadź zrzut zmian na GitHub (`mcp_github_push_files` lub `create_or_update_file`).
2. Zaktualizuj `.agents/heartbeat.json` ze statusem "done".
3. Sporządź raport w `.agents/reports/` opisujący co zostało zmigrowane i jak działa CLI.
4. Zgłoś ukończenie do Supervisora.
