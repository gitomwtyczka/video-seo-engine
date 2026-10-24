# Raport: Naprawa sekcji Cytaty w panelu wyników dashboardu

- **Data**: 2026-10-21
- **Autor**: vse-dev-quotes
- **Branch**: `fix/dashboard-quotes`
- **PR**: https://github.com/gitomwtyczka/video-seo-engine/pull/4

## Przyczyna
Podczas refaktoru `dashboard-inner.tsx` (wydzielenie zakładek do katalogu `components/`) sekcja `Cytaty` (`copyId="art_quotes"`) obecna w `dashboard-inner.tsx.bak` (linie 6561-6620) została pominięta przy tworzeniu `ArticleTab.tsx`. Ponadto backend zwraca `speaker`, podczas gdy stary kod w `.bak` odwoływał się do `q.author`.

## Zmiany
1. `web/src/app/dashboard/components/ArticleTab.tsx`:
   - Dodano import `QuoteItem`.
   - Dodano obsługę cytatów w `ArticleTabProps` (`quotes?: QuoteItem[]`) z fallbackiem do `schema?.quotes`.
   - Przywrócono blok `ResultSection` (`copyId="art_quotes"`) z przyciskiem kopiowania i formatowaniem `speaker || author`.
2. `web/src/app/dashboard/dashboard-inner.tsx`:
   - Zdefiniowano `const quotes = (schema?.quotes as QuoteItem[] | undefined) ?? []`.
   - Przekazano `quotes={quotes}` do `<ArticleTab />`.

## Status
PR #4 otwarty do `main`. Bez deployu zgodnie ze specyfikacją.
