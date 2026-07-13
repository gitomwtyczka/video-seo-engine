# DISPATCH — vse-analyst | Analiza architektoniczna: dashboard-inner.tsx

**Data:** 2026-07-13  
**Od:** Supervisor 01  
**Do:** vse-analyst (read-only)  
**Priorytet:** Strategiczny — nie blokuje deploy

---

## ⚡ KROK 0

```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: sonic-void
  branch: master
  path: .agents/protocols/dispatch-system-block.md
```
Heartbeat do `video-seo-engine/.agents/heartbeat.json`.

---

## KONTEKST PROBLEMU

Plik `web/src/app/dashboard/dashboard-inner.tsx` ma ~88KB i 5000+ linii.
Każdy agent który próbuje go czytać przez GitHub MCP (`get_file_contents`)
dostaje obcięty lub niekompletny widok.

Efekty:
- Agenci dodają kod w złym miejscu (nie widzą pełnego kontekstu)
- Duplikują logikę która już istnieje gdzie indziej
- Twierdzą że dodali feature — a go nie ma
- Każdy dispatch produkuje hotfix

To jest powtarzający się wzorzec. Potrzebna systemowa odpowiedź.

---

## 🔍 ZADANIE

### Sekcja A — Pomiar aktualnego stanu

1. Pobierz plik przez SSH i zmierz dokładnie:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "wc -l /home/ubuntu/video-seo-engine/web/src/app/dashboard/dashboard-inner.tsx && wc -c /home/ubuntu/video-seo-engine/web/src/app/dashboard/dashboard-inner.tsx"
```

2. Policz komponenty i hooki wewnątrz pliku:
```powershell
ssh ... "grep -c 'const [A-Z]\|function [A-Z]\|export default\|export function' /home/ubuntu/video-seo-engine/web/src/app/dashboard/dashboard-inner.tsx"
```

3. Wylistuj wszystkie eksportowane i wewnętrzne komponenty:
```powershell
ssh ... "grep -n 'const [A-Z][a-zA-Z]* = \|function [A-Z][a-zA-Z]*(' /home/ubuntu/video-seo-engine/web/src/app/dashboard/dashboard-inner.tsx"
```

### Sekcja B — Analiza możliwości odczytu

Oceń 4 metody dostępu do dużych plików przez agenta:

**Metoda 1: GitHub MCP `get_file_contents`**
- Limit: ile KB/linii faktycznie zwraca?
- Czy obcina silently czy z błędem?
- Czy `download_url` z MCP daje pełny plik?

**Metoda 2: SSH grep (current workaround)**
- Czy `grep -n` + konkretne wzorce daje wystarczający kontekst?
- Czy można zbudować "mapę pliku" przez serię grepów?
- Ograniczenia?

**Metoda 3: SSH `sed -n 'X,Yp'` (czytanie fragmentów)**
- Czy wystarczy znać numery linii z grep i pobrać kontekst `±30` linii?
- Przykład: `sed -n '1200,1240p' dashboard-inner.tsx`

**Metoda 4: Podział pliku (refactor)**
- Czy komponenty są wystarczajnio samodzieln, by wyciąć je do osobnych plików?
- Ile plików powstałoby po sensownym podziale?
- Czy Next.js/import structure na to pozwala?

### Sekcja C — Rekomendacja

Podaj rekomendację per scenariusz:

| Scenariusz | Rekomendacja |
|---|---|
| Krótkoterminowe (dziś/jutro) | |
| Średnioterminowe (następny sprint) | |
| Długoterminowe (refactor) | |

Rekomendacja musi być **konkretna** — nie "rozważyć podział" ale "wyodrębnić komponenty X, Y, Z do plików A, B, C".

---

## 📨 FORMAT RAPORTU

```
video-seo-engine/.agents/reports/2026-07-13_vse-analyst_dashboard-architecture.md
sonic-void/.agents/reports/inbox/2026-07-13_vse-analyst_dashboard-architecture.md
```

```markdown
# Analiza architektoniczna: dashboard-inner.tsx

## Pomiar
- Linie: X
- Rozmiar: X KB
- Liczba komponentów wewnętrznych: X
- Lista komponentów: [...]

## Metody dostępu — ocena
[per metoda: działa / nie działa / ograniczenia]

## Rekomendacja krótkoterminowa
[konkretna procedura dla agenta czytającego duży plik]

## Rekomendacja Średnioterminowa
[konkretny podział na pliki]

## Rekomendacja długoterminowa
[refactor plan]

## Standard operacyjny (do dodania do AGENTS.md)
[blok reguł który powinien trafić do video-seo-engine AGENTS.md]
```

---

*Supervisor 01 | sonic-void | 2026-07-13*
