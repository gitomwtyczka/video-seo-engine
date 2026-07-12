# Raport wdrożeniowy: Poprawka schemaData dla YouTubePublishModal

**Callsign:** `vse-frontend2`
**Data:** 2026-07-12
**Cel:** Naprawa usterki kasującej opisy na YouTube (puste `schema_data` w frontendzie).

## Co zostało zrobione
1. Zlokalizowałem błędne wywołanie `<YouTubePublishModal schemaData={result.raw?.seo ?? {}} ... />` w `web/src/app/dashboard/dashboard-inner.tsx` (linia ~3671).
2. Ponieważ `result.raw` zawiera dane już na najwyższym poziomie (a nie w `.seo`), zmieniłem kod na: `<YouTubePublishModal schemaData={result.raw ?? {}} ... />`.
3. Zmiany opublikowałem w repozytorium GitHub.
4. Zbudowałem nową wersję obrazu frontendu `vse-web` na środowisku produkcyjnym (VPS) z obowiązkowym pre-deploy backupem bazy danych.
5. Pomyślnie uruchomiono zaktualizowany kontener. Aplikacja pomyślnie zainicjowała Next.js (Ready).

## Podsumowanie i rezultaty
Po wdrożeniu tej poprawki funkcja "Wyślij na YouTube" będzie przekazywać do backendu cały schemat (podobnie jak przycisk WordPressa), dzięki czemu opis filmu znowu będzie odpowiednio wypełniany z powrotem.

Brak zauważalnych regresji, aplikacja z sukcesem wstała i działa stabilnie na docelowym porcie. Weryfikacja wykonana pomyślnie.
