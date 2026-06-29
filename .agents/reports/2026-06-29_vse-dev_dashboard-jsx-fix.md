# Raport: DISPATCH-VSE-DEV-33 — Dashboard JSX Fix

**Callsign:** vse-dev-01
**Data:** 2026-06-29
**Commit:** `0b690e4`
**Status:** ✅ DONE

---

## Problem

Na stronie `/dashboard` widoczny był literalny tekst `)}` pod dropdownem portali.
Modal "+ Dodaj nowy portal" nie otwierał się po kliknięciu.

**Przyczyna:** Worker z DISPATCH-32 wstawił Publication type selector z błędnym wcięciem (14 spacji zamiast 12), przez co znalazł się wewnątrz `</div>` portalu zamiast jako sibling w gridzie `grid-cols-2`. Linia 1130 zawierała `)}` które React renderował jako tekst.

## Fix

**Plik:** `web/src/app/dashboard/dashboard-inner.tsx`

- Publication type selector: wcięcie 14→12 spacji (teraz jest child grida `grid-cols-2`)
- Usunięte stray `)}` z linii 1130 — zastąpione `</div>` (zamknięcie grida)
- Styl `backgroundImage` w `<select>` skopiowany 1:1 z oryginału

**Diff:** 15 insertions, 16 deletions (netto -1 linia)

## Deploy

- Build Next.js: ✅ Compiled successfully
- Static pages: ✅ 10/10 wygenerowanych
- Kontener vse-web: ✅ Ready in 77ms
- Logi: brak błędów

## Deliverable checklist

- [x] Fix wcięcia publication type selector (2 spacje)
- [x] Usunięte `)}` z linii 1130
- [x] Commit na main (`0b690e4`)
- [x] Deploy vse-web na VPS
- [x] Logi bez błędów

---

*[vse-dev-01 | video-seo-engine 29.06.2026]*
