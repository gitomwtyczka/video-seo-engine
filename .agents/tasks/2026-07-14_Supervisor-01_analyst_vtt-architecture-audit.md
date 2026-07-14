# DISPATCH — sup-analyst | Audit lokalnego workera VTT
**Supervisor:** Supervisor-01  
**Data:** 2026-07-14  
**Priorytet:** 🔴 WYSOKI

---

## ZADANIE

Właściciel projektu używa lokalnego workera zainstalowanego na swoim komputerze, który odpowiada za pobieranie plików VTT (transkryptów) z YouTube. Jest to oddzielny skrypt lub program — nie kod w repo `video-seo-engine`.

**Znajdź tego workera i go udokumentuj.**

---

## CO ZBADAĆ

### 1. Lokalizacja workera

Znajdź gdzie worker żyje. Sprawdź repozytoria właściciela (`gitomwtyczka`) pod kątem skryptów do pobierania YouTube VTT/transkryptów:
- Repozytoria powiązane z VSE: `video-seo-engine`, `shadow-perihelion`, `social-publisher`
- Szukaj słów kluczowych: `vtt`, `transcript`, `youtube`, `worker`, `fetch`, `download`
- Sprawdź `D:\Biblioteki\` — tam mogą być pobrane pliki (lokalizacja znana z poprzednich sesji)

### 2. Mechanizm działania

Kiedy znajdziesz workera, udokumentuj:
- Jak jest uruchamiany (skrypt Python, Node, plik wykonywalny, usługa systemowa?)
- Jakich bibliotek / API używa do pobierania transkryptów
- Skąd bierze listę wideo do pobrania
- Dokąd zapisuje pobrane pliki VTT
- Czy komunikuje się z serwerem VSE (VPS Oracle) i w jaki sposób
- Czy ma mechanizm ponownego pobrania gdy plik istnieje (nadpisuje czy pomija?)

### 3. Przepływ end-to-end

Narysuj pełny przepływ:
```
[user YouTube] → [lokalny worker] → [plik VTT] → [co dalej?] → [VSE pipeline]
```
Gdzie każda strzałka = jaki mechanizm, jaki protokół, jaki format.

---

## DELIVERABLES

**Dokument:** `video-seo-engine/.agents/knowledge/vtt-local-worker-architecture.md`  
Zawartość: odpowiedzi na wszystkie punkty powyżej + pełny przepływ

**Raport dual-write:**
- `video-seo-engine/.agents/reports/2026-07-14_analyst_vtt-worker-audit.md`
- `sonic-void/.agents/reports/inbox/2026-07-14_analyst_vtt-worker-audit.md` (branch: master)

---

*Dispatch: Supervisor-01 | video-seo-engine | 2026-07-14*
