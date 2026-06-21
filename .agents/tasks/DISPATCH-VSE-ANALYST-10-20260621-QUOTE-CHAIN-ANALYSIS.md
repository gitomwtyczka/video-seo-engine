# DISPATCH — vse-analyst-10 — Cudzysłowy: Pełna Analiza Łańcucha

**Dispatch ID:** A11  
**Callsign:** vse-analyst-10  
**Priorytet:** 🔴 KRYTYCZNY  
**Data:** 2026-06-21  
**Wystawiony przez:** Supervisor 02  

---

## KONTEKST

Problem cudzysłowów w generowanym HTML to systemowy bug VSE.
LLM (Claude) generuje `"` wewnątrz stringów JSON, co łamie parsing.
Problem powraca mimo wielokrotnych łatek — każdy agent aplikuje lokalny fix,
który jest degradowany przez następne pokolenia.

User twierdzi: _"kilka dni temu zanalizowaliśmy sytuację i znaleźliśmy rozwiązanie,
ale to rozwiązanie przez kolejne pokolenia agentów było degradowane"_.

D12 (vse-dev-27, 21.06) dodał instrukcję w prompcie + retry, ale to łatka.

## ZADANIE

### 1. Znajdź oryginalną analizę

Przeszukaj raporty w:
- `video-seo-engine/.agents/reports/` (06-17 do 06-19)
- `sonic-void/.agents/reports/inbox/` (ten sam zakres)
- Szukaj fraz: `cudzysłów`, `quote`, `html.*attr`, `json.*parse`, `sanitize`

### 2. Zmapuj pełny łańcuch

Proceśłedź cały pipeline i udokumentuj:
```
LLM output → JSON parse → HTML injection → WP REST API → wyświetlenie na portalu
```

Dla każdego etapu:
- Jaki format danych wchodzi?
- Jak są przetwarzane cudzysłowy?
- Gdzie dokładnie następuje złamanie?

### 3. Przeczytaj aktualny kod

Pliki do analizy:
```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: video-seo-engine
  branch: main
  path: core/generator.py

  path: core/injector.py
  
  path: core/prompts.py (lub prompts/)
```

Szukaj:
- `json.loads()` — jak obsługuje escaped quotes?
- `article_body` — jak HTML jest wstawiany do WP?
- Prompt instructions dotyczące cudzysłowów
- Wszelkie `replace()`, `sanitize`, `clean` na HTML content

### 4. Zaproponuj rozwiązanie systemowe

Możliwe podejścia (ocenić każde):

1. **Post-processing po json.loads()**: 
   W `article_body` zamień `"` na `'` wewnątrz HTML atrybutów
   ```python
   import re
   body = re.sub(r'(\w+)="([^"]*)"', lambda m: f"{m.group(1)}='{m.group(2)}'", body)
   ```

2. **HTML entity encoding**: `&quot;` zamiast `"`

3. **Dedykowany sanitizer**: Warstwa między JSON parse a WP injection

4. **Prompt engineering**: Instrukcja użycia `'` zamiast `"` w HTML (obecne — nieskuteczne)

5. **json.dumps() na LLM output**: Przed parsowaniem

## OUTPUT

Raport w:
```
mcp_github_create_or_update_file:
  repo: video-seo-engine
  path: .agents/reports/2026-06-21_vse-analyst-10_quote-chain-analysis.md
```

Dual-write do:
```
sonic-void/.agents/reports/inbox/2026-06-21_vse-analyst-10_quote-chain-analysis.md
```

Raport MUSI zawierać:
- Pełny łańcuch z punktami złamania
- Rekomendowane rozwiązanie z kodem
- Reference do oryginalnej analizy (jeśli znaleziona)
- Ocena wariantów rozwiązań

## CREDENTIALS

Dostęp do GitHub MCP wystarczy do analizy kodu.
Nie potrzebujesz SSH/VPS.

---

*[Supervisor 02 | sonic-void 21.06.2026 17:42]*