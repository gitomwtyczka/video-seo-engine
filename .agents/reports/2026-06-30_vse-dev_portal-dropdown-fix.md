# Raport: Portal Dropdown Fix — DISPATCH-VSE-DEV-34

**Callsign:** vse-dev-01
**Data:** 2026-06-30
**Commit:** `d850cd4`
**Status:** ✅ DONE — deployed

---

## Problem

Dropdown portali na `/dashboard` wyświetlał się poprawnie, ale kliknięcie opcji nie działało:
- `+ Dodaj nowy portal` → nic (modal nie otwierał się)
- `✏️ Wpisz ręcznie` → nic

## Przyczyna

### Bug 1 — blok `portals.length === 0`
- `value="__add__"` było hardcoded → klik `__add__` nie zmieniał wartości → `onChange` **NIE odpalał**
- Brak handlera dla `__manual__`

### Bug 2 — blok `portals.length > 0`
- Brak handlera `__manual__` w onChange
- `e.target.value = selectedPortalId` — mutacja DOM, anti-pattern w React

## Fix

### Blok `portals === 0`
- `value=""` z `disabled` na pustym option → każda zmiana odpala onChange
- Dodano handler `__add__` i `__manual__`

### Blok `portals > 0`
- Dodano `else if (val === '__manual__')` handler
- Usunięto `e.target.value = selectedPortalId` (DOM mutation)

### AddPortalModal
- ✅ Był renderowany prawidłowo (L1470-1478) — nie wymagał zmian

## Weryfikacja

- TypeScript build: ✅ `Image video-seo-engine-vse-web Built` — brak błędów
- Deploy: ✅ `Next.js 14.2.29 ✓ Ready in 77ms`
- Container: `vse-web Recreated + Started`

---

*[vse-dev-01 | video-seo-engine 30.06.2026]*
