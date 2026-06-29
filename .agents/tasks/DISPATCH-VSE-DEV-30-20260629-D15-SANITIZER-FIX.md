# DISPATCH D15: Bezpieczny Pre-Parse Sanitizer (Fix JSONDecodeError)

**ID:** DISPATCH-VSE-DEV-30-20260629-D15-SANITIZER-FIX
**Priorytet:** 0 (KRYTYCZNY BLOKER)
**Agent:** (do przydzielenia z rodziny `vse-dev-XX`)

---

## 🎯 CEL
Całkowita eliminacja błędów 500 (JSONDecodeError) spowodowanych tym, że LLM pluje surowym HTML-em z uciekającymi cudzysłowami (np. `{"article_body": "<a href=\"https://prawy.pl\">"}`) wewnątrz wartości string dla JSON-a.

## ⛔ ZAKAZY
Wcześniejszy analityk zaproponował "ślepą" łatkę w postaci regexa: `r'(\w+)=\\\"([^\\"]*?)\\\"'`.  
**ZAKAZUJEMY takiego podejścia bez pełnego reżimu testowego.** Udowodniono, że takie podejście korumpuje zwykły tekst, rozwala tagi zagnieżdżone typu `onclick` i nie wychwytuje escape'ów `\n`.

## 🛠️ ZADANIE DO WYKONANIA

1. **Stworzenie dedykowanej funkcji `_sanitize_llm_json(raw_text)` w module `core/generator.py`.** Funkcja ma stanowić ostatnią deskę ratunku przed wykonaniem `json.loads(text)`.
2. **Wdrożenie bezpiecznej naprawy:** Użycie stabilnej metody parsowania awaryjnego (np. moduł `json-repair`, jeśli dostępny w przestrzeni) ALBO perfekcyjnie wyizolowanego regexa TDD (działającego tylko w tagach `<\w+[^>]*>`).
3. **Modyfikacja `generate_seo_v4()`:** Przepuszczenie outputu LLMa najpierw przez Twój nowy sanitizer.
4. **Unit Testy:** MUSISZ napisać pytest w `tests/` sprawdzający:
   - Czy złośliwy JSON się nie sypie na parsowaniu: `{"article_body": "To tekst i równanie e=\"mc2\", a to link <a href=\"#\">klik</a>. Script: onclick=\"alert('TEST')\""}`.
   - Pamiętaj, test przechodzi dopiero gdy JSON zostanie bezpiecznie sformatowany bez naruszenia spójności HTML (np. nie urywa `onclick`).

Po zakończeniu, opublikuj standardowy raport, wciśnij wszystko na produkcję i zgłoś "done" przez heartbeat.