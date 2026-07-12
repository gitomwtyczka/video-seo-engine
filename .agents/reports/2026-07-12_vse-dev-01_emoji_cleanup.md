# Raport: Naprawa emoji w dashboard-inner.tsx

**Agent:** vse-dev-01
**Data:** 2026-07-12
**Cel:** Finalizacja dispatcha 2026-07-12_emoji_cleanup.md

## Co zrobiono:
1. **Analiza (Krok 0 & 1):** Potwierdzono, że emoji uległy podwójnemu kodowaniu na skutek wcześniejszych operacji PowerShell/base64. Regex `slugify` (linie 1566-1576) również został uszkodzony (znaki box-drawing zamiast polskich znaków).
2. **Implementacja (Krok 2):** Zamiast pisać złożone skrypty regexowe, użyto 3-przebiegowego skryptu pythona na VPS, który punkt po punkcie zamienił uszkodzone `codepoints` na poprawne sekwencje:
   - Poprawiono regex w `slugify` przywracając oryginalne mapowania polskich znaków.
   - Poprawiono emoji w przyciskach UI (m.in. "✔️ Skopiowano", "🚀", "⚠️", "📄", "🖼️", "💬").
   - Weryfikacja dodatkowym skryptem skanującym wykazała 0 uszkodzonych znaków.
3. **Commit (Krok 3):** Wystąpił problem z narzędziem `create_or_update_file` GitHub MCP — API obcięło 88-kilobajtowy plik w związku z wklejeniem tekstu w oknie JSONa. Problem naprawiono natychmiastowym obejściem przy pomocy lokalnego CLI `gh api` z przekazaniem payloadu wprost z pliku, dzięki czemu plik na GitHub został bezstratnie odtworzony (Krok 3b).
4. **Deploy (Krok 4):** Uruchomiono `docker compose build vse-web && docker compose up -d vse-web`. Kontener odtworzony.

## Wynik
Aplikacja została przebudowana, wszystkie emoji wyświetlają się poprawnie, a plik na repozytorium zdalnym jest w 100% zsynchronizowany.

## Znane problemy (GOTCHA)
- Narzędzie GitHub MCP w przypadku tak wielkich plików bywa zawodne z powodu ucinania contextu przez token limit (obcina base64). Do update'u dużych plików (>50KB) bezpieczniej używać skryptu z `gh api` lub `multi_replace_file_content`.