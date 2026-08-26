# Raport z naprawy ścieżki Shorts (VSE)
**Data:** 2026-08-26
**Agent:** shadow-dev-01
**Problem:** Ścieżka kopiowania w UI dla wygenerowanego shorta zawierała wielokrotne backslashe (C:\\\\VSE\\\\Shorts).
**Rozwiązanie:**
Zidentyfikowano hardcoded ścieżkę w komponencie `web/src/app/dashboard/components/ShortMachineTab.tsx`.
Właściwość `output_dir` wysyłana w payloadzie do API (JSON string) była eskejpowana podwójnie (8 backslashy w kodzie źródłowym TSX). Zmieniono z `'C:\\\\\\\\VSE\\\\\\\\Shorts'` na `'C:\\\\VSE\\\\Shorts'` co w JS daje `C:\\VSE\\Shorts` a w JSON string wysyłanym do API backend zinterpretuje poprawnie jako `C:\VSE\Shorts`.

**Status:** Zakończone sukcesem. Zmiany wysłane do repozytorium `video-seo-engine`.
