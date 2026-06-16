## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**Twój callsign:** `[arch-senior-01 | video-seo-engine]`  
**Workspace:** video-seo-engine  
**Sugerowany model:** Claude Opus 4 — synteza strategiczna

---

# TASK: arch-senior-01 — Architecture Decision & Roadmap VSE

**Data:** 2026-06-16  
**Dispatch from:** Supervisor 03  
**Priorytet:** 🔵 Strategiczny — wejście do fazy D2/D3

---

## Twój deliverable:

Jeden dokument: `docs/ARCHITECTURE_decisions.md`

Synteza 4 raportów analitycznych w **konkretny, priorytetowany roadmap techniczny** dla VSE.
Nie piszesz kodu. Nie implementujesz. Piszesz decyzje architektoniczne i kolejność zmian.

---

## Cztery raporty do syntezy

Przeczytaj wszystkie przez GitHub MCP (`gitomwtyczka/video-seo-engine`, branch: `main`):

1. `docs/ANALYSIS_security.md` — arch-sec-01 (security audit)
2. `docs/ANALYSIS_api.md` — arch-api-01 (api design)
3. `docs/ANALYSIS_saas.md` — arch-saas-01 (saas patterns)
4. `docs/ANALYSIS_scalability.md` — arch-scale-01 (scalability @ 1000 users)

Jeśli nazwy plików się różnią — sprawdz `docs/` przez `get_file_contents` na katalogu.

---

## Pytania na które masz odpowiedzieć

### P1: Co robimy NAJPIERW? (quick wins)
Które zmiany dają najwyższy ROI przy najniższym ryzyku? Lista max 3 pozycji.

### P2: Co blokuje skalowanie do 1000 users?
Główny wąskie gardło — jedna diagnoza, jedno remedium.

### P3: Architektura multi-tenant — kiedy?
Czy VSE wymaga multi-tenancy teraz, czy można odroczyć? Co jest trigger.

### P4: Local Runner — jak długo?
Czy jest plan zastąpienia Windows-only runnera. Rekomendacja.

### P5: Jakich decyzji NIE można odwrócić?
Lista decyzji architektonicznych które jeśli podjemie się źle, zablokują drogę do SaaS.

---

## Format raportu

```markdown
# Architecture Decisions — Video SEO Engine
**Senior Architect:** arch-senior-01  
**Data:** 2026-06-16  
**Input:** 4 raporty analityczne (sec, api, saas, scale)

## TL;DR (max 5 zdań)
[Najważniejsze wnioski dla CEO]

## Decyzje architektoniczne (ADR)

### ADR-01: [Tytuł]
- **Status:** Zaakceptowana / Do zatwierdzenia / Odroczona
- **Kontekst:** ...
- **Decyzja:** ...
- **Skutki:** ...

### ADR-02: ...

## Priorytetowany roadmap techniczny

| Faza | Co | Effort | Blokuje co? |
|------|-----|--------|-------------|
| P0 (teraz) | ... | ... | ... |
| P1 (sprint 1) | ... | ... | ... |
| P2 (sprint 2-4) | ... | ... | ... |
| P3 (kwartalnie) | ... | ... | ... |

## Czerwone linie (czego NIE robić)
[Lista decyzji które zamknęłyby drogę do SaaS]

## Otwarte pytania do Supervisora
[Maksymalnie 3 — tylko te które blokują decyzje]
```

---

## Raport po wykonaniu

Wyślij do:
1. `video-seo-engine/docs/ARCHITECTURE_decisions.md`
2. `video-seo-engine/.agents/reports/2026-06-16_arch-senior-01_architecture-decisions.md`
3. `sonic-void/.agents/reports/inbox/2026-06-16_arch-senior-01_architecture-decisions.md`

**Dual-write do sonic-void inbox jest OBOWIĄZKOWY.**

---

## Dostęp

- GitHub MCP: `gitomwtyczka/video-seo-engine` branch `main`
- SSH VPS (jeśli potrzebny): `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "komenda"`
- **FILE BRIDGE / Wetty: ZAKAZ**

---

## Protokół callsign (OBOWIĄZKOWE)

```
[arch-senior-01 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[arch-senior-01 | video-seo-engine DD.MM.YYYY HH:MM] — raport kompletny
```

---

*Supervisor 03 | sonic-void | 2026-06-16 18:18*
