# Koncepcja SEO: Rozdziały YT jako Search Surface Area

**Data:** 2026-07-13 | **Autor:** Supervisor 01  
**Status:** do implementacji — kolejność patrz sekcja Roadmap

---

## Filozofia

Bez rozdziałów: 1 wynik w Google.  
Z 8 rozdziałami: 8 niezależnych punktów wejścia w wynikach.

Rozdziały nie są ozdobnikiem — są **mnożnikiem ruchu organicznego**.

W 2026: AI (Perplexity, ChatGPT, Gemini) przeszukuje YouTube przez metadane rozdziałów.
Precyzyjny tytuł rozdziału = większa szansa że AI zacytuje wideo jako źródło.

---

## Zasada nadrzędna tytułowania

> **"Co wpisze w Google ktoś szukający tego konkretnego fragmentu?"**
> → To jest tytuł rozdziału.

### Przykłady

| ❌ Źle | ✅ Dobrze |
|---|---|
| Wstęp | Czym jest analiza rynku nieruchomości? |
| Co o tym myślę | Dlaczego stopy procentowe rosną w 2026 |
| Podsumowanie | Kiedy warto kupować akcje wzrostowe |
| Część 1 | ❌ nigdy |
| Introduction | ❌ nigdy |

### Zakaz absolutny

Nigdy nie używaj: `Wstęp`, `Podsumowanie`, `Część X`, `Co o tym myślę`, `Introduction`, `Outro`.
To zmarnowany potencjał SEO — zero wartości dla użytkownika i algorytmów.

---

## Specyfikacja techniczna tytułów (aktualna)

| Parametr | Wartość | Uzasadnienie |
|---|---|---|
| Długość | **30–50 znaków** | Mobile ucina dłuższe — kluczowe słowo musi być widoczne |
| Słowa | 4–7 słów | Balans czytelności i density |
| Pierwsze słowo | Słowo kluczowe | Mobile-first: najważniejsza fraza na początku |
| Zawartość | Long-tail keyword | Fraza którą ktoś wpisze w Google |
| Intencja | Zorientowana na problem/rozwiązanie | Nie chronologia, ale "od pytania do odpowiedzi" |

> Korekta względem poprzedniej specyfikacji: zakres 25–50 uściślono do **30–50** na podstawie praktyki SEO 2026.

---

## Techniczne minimum YouTube (nie naruszaj)

- Pierwszy rozdział: `00:00`
- Minimum 3 rozdziały
- Każdy rozdział: min. 10 sekund
- Kolejność: chronologiczna

---

## Cross-linking WP ↔ YT (M4B)

Format deep linku do konkretnego momentu YT:
```
https://www.youtube.com/watch?v=VIDEO_ID&t=120  (sekundy)
```

**Schemat cross-linkingu:**
```
Artykuł WP → zawiera cytaty z wideo → każdy cytat = link do konkretnego rozdziału YT
Opis YT → zawiera link do artykułu WP (M2)
```

Efekt: Google widzi dwa powiązane dokumenty wzmacniające się nawzajem.

**Implementacja M4B:**
- Backend: fuzzy match tekstu cytatu → timestamp z VTT → generuje URL `?t=X`
- Frontend: cytaty w opisie YT z klikalnymi linkami
- Status: **P1** (awansowany z P2 na podstawie tej analizy)

---

## Architektura systemu (docelowa)

```
WARSTWA 1 — Generowanie (crimson-void prompt)
  ├── Zasada intencji: "co wpisze użytkownik w Google"
  ├── Zakaz: Wstęp, Podsumowanie, Część X, Co o tym myślę
  ├── "Wstęp" → konkretne pytanie (Czym jest X?)
  ├── Długość: 30-50 znaków
  └── Kluczowe słowo PIERWSZE

WARSTWA 2 — Opis YT (build_yt_description w inject.py)
  ├── M4: rozdziały jako blok timestampów (obecny)
  └── M4B: deep links cytaty → ?t=X (do implementacji)

WARSTWA 3 — Cross-linking (nowy moduł)
  └── Artykuł WP → linkuje do konkretnych rozdziałów YT
      Wymaga: inject.py generuje linki po opublikowaniu na YT
      Status: Faza P3 (webhook)
```

---

## Roadmap implementacji

| Priorytet | Zadanie | Repo | Status |
|---|---|---|---|
| 🔴 P0 | Preview opisu YT + footer_text w UI | video-seo-engine | **Dispatched 2026-07-13** |
| 🔴 P1 | Prompt update: intencja, zakaz śmieci, 30-50 zn | crimson-void | Do dispatch |
| 🟡 P1 | M4B: cytaty z deep linkami (?t=) | video-seo-engine | Po prompt update |
| 🔵 P2 | Cross-linking WP ↔ YT (inject → WP artykuł) | video-seo-engine | Faza P3 webhook |

---

## Prompt update dla crimson-void (szkic)

Do dodania do promptu generującego rozdziały:

```
ZASADY TYTUŁOWANIA ROZDZIAŁÓW:
1. Zadaj pytanie: "Co wpisze w Google ktoś szukający tego fragmentu?" — to jest tytuł.
2. Długość: 30-50 znaków, 4-7 słów.
3. Pierwsze słowo = najważniejsze słowo kluczowe (mobile ucina resztę).
4. Orientacja na intencję: od problemu do rozwiązania, nie chronologia.
5. ZAKAZANE słowa: Wstęp, Podsumowanie, Część, Introduction, Outro, Co o tym myślę.
6. Zamiast "Wstęp" → konkretne pytanie: "Czym jest [Temat]?"
7. Każdy tytuł musi zawierać long-tail keyword z domeny tematycznej wideo.
```

---

*Supervisor 01 | sonic-void | 2026-07-13*  
*Źródło: analiza standardów YT vs praktyki SEO community 2026*
