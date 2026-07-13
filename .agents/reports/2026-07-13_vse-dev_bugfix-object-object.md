# Raport: Naprawa [object Object] w podglądzie YT

## Co zmieniono w `YouTubePublishModal.tsx`
- Zastąpiono funkcję `buildPreview()` implementacją, która:
  - Iteruje po tablicy `schemaData.chapters` i łączy poszczególne obiekty typu `{ time: ..., label: ... }` we właściwie sformatowany tekst (np. `12:34 Rozdział`).
  - Iteruje po `schemaData.youtube_hashtags` zapewniając dodanie znaku `#` (jeśli go brak) i łączy tablicę w jeden ciąg (string) oddzielony przecinkiem (format akceptowany przez YouTube).
  - Składa wszystkie moduły w prawidłowej kolejności (body, wp_url, mid_cta, chapters, credits, footer_text, hashtags).
- Zmieniono import na górze pliku z `import { useState } from "react";` na `import { useState, useEffect } from "react";`.
- Dodano `useEffect`, który wywołuje `setPreviewText(buildPreview())` gdy `showPreview` jest aktywne i gdy zmienia się wytypowany kanał (`selected`), `schemaData` lub `wpUrl`.

## Typy
- Uruchomiono `npx tsc --noEmit`. Plik `YouTubePublishModal.tsx` został zwalidowany bez nowych błędów TS. (Błędy TS2339 z `accessToken` istniejące w innych plikach nie dotyczą wprowadzonej poprawki).

## Commit SHA
- Zmiany zostały zacommitowane bezpośrednio do repozytorium przez GitHub API (bez deployu!).
- Commit SHA: fe650a8bc670b13aabdce0e3bb0ef8ac3533d272
