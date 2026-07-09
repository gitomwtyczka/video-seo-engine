# Dispatch: Diagnoza błędu "metadata_fetch_failed"

**Do:** vse-analyst-01
**Od:** vse-strateg-01
**Data:** 2026-07-09
**Status:** Nowy

## Opis problemu
Zgłoszono problem na produkcji (widoczny na zrzucie ekranu z produkcyjnego Dashboardu dla planu Agency). 
Przy próbie wygenerowania SEO dla URL YouTube (np. identyfikator: `pebmxRlHjh0`), front-end zgłasza błąd:
`Wystąpił błąd. Fetch failed for pebmxRlHjh0: metadata_fetch_failed`

Zgodnie z mapą modułów, moduł `core/fetcher.py` jest odpowiedzialny za pobieranie metadanych i transkryptu z YouTube. Awaria najprawdopodobniej leży na styku z zewnętrznym API YouTube.

## Twoje zadanie (vse-analyst-01)
1. Połącz się przez SSH do produkcyjnego VPS (`147.224.162.100`). Wyciągnij logi z kontenera `vse-api` dla transakcji dotyczącej wideo `pebmxRlHjh0`.
2. Zbadaj `core/fetcher.py` przy użyciu narzędzi czytania kodu. Ustal root cause (np. YouTube zmienił strukturę DOM, limit zapytań, przestarzała biblioteka `yt-dlp`/`youtube-transcript-api`).
3. Opracuj zalecenia naprawcze. Wygeneruj raport i wyślij go do inboxa (`sonic-void/.agents/reports/inbox/`) oraz zapisz lokalnie w tym repozytorium.
4. Pamiętaj: jako analityk (zgodnie z `RULE[AGENTS.md]`) NIE wykonujesz deployu. Zdiagnozuj i zgłoś.

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)
1. GitHub MCP: po create_or_update_file ZAWSZE zweryfikuj newlines.
2. SSH: NIE buduj złożonych komend inline — stwórz skrypt lokalnie (write_to_file) → zrób scp → uruchom przez ssh.
3. Fetchery z YT lubią zwracać captcha / błąd 429. Zwróć szczególną uwagę na kod błędu wewnątrz kontenera.
