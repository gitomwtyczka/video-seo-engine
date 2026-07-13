# DISPATCH — vse-analyst | Research: pole opisu YT w schemaData

**Data:** 2026-07-13  
**Od:** Supervisor 01  
**Do:** vse-analyst (Gemini Flash — read-only, bez deploy)  
**Priorytet:** BLOKUJĄCY — wynik potrzebny przed kolejnymi dispatchami

---

## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**0. Wczytaj blok systemowy:**
```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: sonic-void
  branch: master
  path: .agents/protocols/dispatch-system-block.md
```

**1. Wyślij heartbeat** do `video-seo-engine/.agents/heartbeat.json`

---

## 🎯 ZADANIE (wyłącznie analiza — zero zmian w kodzie)

Odpowiedz na 3 pytania przez czytanie kodu. Nic nie zmieniaj.

---

## Pytanie 1: Jak nazywa się pole gotowego opisu YT w `schemaData`?

W UI dashboardu widoczny jest przycisk **"Wklej do opisu YT"** oraz label **"Format YouTube (do opisu wideo)"**.

Sprawdź w `web/src/app/dashboard/dashboard-inner.tsx`:
- Znajdź wszystkie wystąpienia frazy `youtube` (case-insensitive)
- Znajdź obsługę sekcji `Format YouTube` lub `Wklej do opisu YT`
- Ustal: z jakiego pola `result.raw` lub `schemaData` czytana jest treść tego przycisku?

**Oczekiwana odpowiedź:** nazwa pola, np. `youtube_format`, `youtube_description`, `yt_description`, itp.

---

## Pytanie 2: Co aktualnie zawiera `schemaData.youtube_hashtags`?

W pliku `api/routers/inject.py` lub `api/services/generator.py`:
- Sprawdź czy `youtube_hashtags` to **string** czy **array**
- Jeśli array: jaki format elementów? (`"#tag"` czy `"tag"`?)

**Oczekiwana odpowiedź:** `string` | `array<string>` + przykładowy element

---

## Pytanie 3: Jak backend buduje finalny opis YT?

W `api/routers/inject.py` znajdź funkcję `build_yt_description()`:
- Wymień kolejność modułów które składa (M1, M2, M3...)
- Sprawdz czy obsługuje `override_description` w body — jeśli nie, zanotuj to
- Podaj separator między modułami (jeden enter? dwa? nic?)

**Oczekiwana odpowiedź:** lista modułów w kolejności + separator + info o override

---

## 📨 FORMAT RAPORTU

Raport zapisz jako:
```
video-seo-engine/.agents/reports/2026-07-13_vse-analyst_yt-field-research.md
sonic-void/.agents/reports/inbox/2026-07-13_vse-analyst_yt-field-research.md
```

Struktura raportu:
```markdown
# Research: pole opisu YT

## Q1: Nazwa pola w schemaData
[odpowiedź + linia kodu gdzie używana]

## Q2: Format youtube_hashtags
[string/array + przykład]

## Q3: build_yt_description() — kolejność modułów
[lista + separator + override?]

## Rekomendacja dla następnego agenta
[co dokładnie użyć w buildYtDescription() po stronie frontendu]
```

Heartbeat `status: "done"` po zapisie raportu.

---

*Supervisor 01 | sonic-void | 2026-07-13*
