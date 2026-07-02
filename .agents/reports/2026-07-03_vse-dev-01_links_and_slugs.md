# Raport: Naprawa linków wewnętrznych i problemu długich slugów

**Data:** 2026-07-03
**Agent:** vse-dev-01
**Zadanie:** Usunięcie wymuszania `wp_slug` oraz złagodzenie wymagań dotyczących linków wewnętrznych w promptach LLM, a także zaprzestanie wysyłania `slug` do WordPress API.

## Wdrożone zmiany
1. `core/generator.py`:
   - Usunięto całkowicie wymóg generowania `wp_slug` z instrukcji dla LLM (limit 60 znaków i reguły transliteracji zostały wycięte).
   - Zaktualizowano wymóg "LINKI ZEWNETRZNE (DoFollow)" na "LINKI WEWNETRZNE" łagodząc go z "MUSISZ wplesc MINIMUM 2" do "wstaw 2-4 z nich. Jeśli brak prawdziwych URL-i – wstaw `<!-- TODO: dodać link wewnętrzny -->`".
   - Usunięto walidację i hard-limit po odebraniu JSON-a z LLM dla klucza `wp_slug`.
2. `core/injector.py`:
   - Usunięto kod przypisujący wartość do `payload["slug"]`. Dzięki temu WordPress API wygeneruje go samodzielnie przez `sanitize_title()`.
   - W słowniku wyjściowym `inject_video` flaga `wp_slug_set` zmieniona na `False`.

## Git Commit
Zatwierdzono i wysłano w commit `de630903e0d87378dd4851e82feb340a138e0079`.

Wdrożenie pomyślne. Zgodnie z instrukcją nie wykonano deployu.
