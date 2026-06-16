## ⚡ KROK 0

**Callsign:** `[vse-analyst-02 | video-seo-engine]` | Model: Claude Sonnet

---

# TASK: vse-analyst-02 — Diagnoza: VTT / Admin 500 / Historia linki

**Data:** 2026-06-16 | **Dispatch:** Supervisor 03  
**Rola: TYLKO diagnoza. NIE implementujesz.**

---

## 📚 KROK 0b — Przeczytaj PRZED analizą (OBOWIĄZKOWE)

1. `docs/ARCHITECTURE.md` przez GitHub MCP
2. `ROADMAP.md` przez GitHub MCP

Bez tych dokumentów nie zaczniesz analizy. To nie jest formalność — te pliki dają kontekst który eliminuje odkrywanie rzeczy już znanych.

---

## Trzy problemy do zbadania

### 1. Rozdziały — `(bez tytułu)` zamiast tekstu

Backend wykrywa 14 rozdziałów (badge pokazuje liczbę). Ale frontend renderuje `?` i `(bez tytułu)`. 

Zbadaj:
- Co jest w bazie w polu `schema_data.chapters` dla ostatniego gotowego joba (SSH + psql)
- Jak frontend parsuje chapters w `web/src/app/dashboard/page.tsx` (GitHub MCP)
- Znajdź gdzie gubi się tytuł i czas — czy w bazie czy w renderowaniu

### 2. Admin panel — HTTP 500 przy ładowaniu użytkowników

Panel się otwiera, redirect do logowania działa. Po zalogowaniu: `Users API: HTTP 500`.

Zbadaj:
- Logi `vse-api` podczas requesta do `/v1/admin/users` (SSH)
- Kod `api/routers/admin.py` — czy jest lazy loading który może crashować w async (GitHub MCP)
- Porównaj z fixem dev-08 w `api/auth.py` (`selectinload`) — czy admin ma ten sam problem

### 3. Historia — linki nie klikają

Tytuł i link pod nim widoczne, ale nieinteraktywne.

Zbadaj:
- Kod `web/src/app/historia/page.tsx` (GitHub MCP) — czy `<a href>` jest czy element jest bez linku
- Czy `YT →` button ma href

---

## Format raportu

Dla każdego z 3 problemów:
```
## Problem X
- Root cause: [co dokładnie nie działa i gdzie]
- Plik(i) do zmiany: [konkretne pliki i linie]
- Proponowany fix: [1-3 zdania co zmienić]
- Ryzyko: [czy fix może coś zepsuć]
```

Nie implementujesz. Raport trafia do Supervisora który konsultuje z użytkownikiem i decyduje co wdrażać.

---

## Dostęp

- GitHub MCP: `gitomwtyczka/video-seo-engine` branch `main`
- SSH: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100`
- **NIE implementujesz | FILE BRIDGE: ZAKAZ**

---

## Raport (dual-write):
1. `video-seo-engine/.agents/reports/2026-06-16_vse-analyst-02_diagnoza-vtt-admin-historia.md`
2. `sonic-void/.agents/reports/inbox/2026-06-16_vse-analyst-02_diagnoza-vtt-admin-historia.md`

```
[vse-analyst-02 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[vse-analyst-02 | video-seo-engine DD.MM.YYYY HH:MM] — raport kompletny
```

*Supervisor 03 | sonic-void | 2026-06-16 22:45*
