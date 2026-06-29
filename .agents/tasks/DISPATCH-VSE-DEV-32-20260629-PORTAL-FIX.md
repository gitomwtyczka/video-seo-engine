# DISPATCH VSE-DEV-32 — Fix portali: 2 chirurgiczne poprawki + deploy

**Callsign:** vse-dev (Pro High)
**Projekt:** video-seo-engine
**Data:** 2026-06-29
**Priorytet:** 🔴 WYSOKI
**Typ:** HOTFIX — 2 konkretne zmiany, zero inwencji

---

## Kontekst

Analityk (vse-analyst-01) zdiagnozował dokładnie 2 bugi blokujące zarządzanie portalami.
Raport: `video-seo-engine/.agents/reports/2026-06-29_vse-analyst-01_PORTAL-AUDIT.md`

Architektura i logika są POPRAWNE. Tylko dwie powierzchowne pomyłki.

---

## BUG #1 — Modal `<AddPortalModal>` nie renderuje się w drzewie DOM

**Plik:** `web/src/app/dashboard/dashboard-inner.tsx`

**Diagnoza:**
- Stan `showAddPortalModal` i jego setter są na liniach 1079 i 1094 ✅
- Komponent `<AddPortalModal>` jest zdefiniowany w pliku (linie 658–818) ✅
- **Brakuje:** wywołanie `<AddPortalModal>` w `return` komponentu `DashboardInner`
- Efekt: kliknięcie `+ Dodaj nowy portal` zmienia stan na `true`, ale modal nigdy nie jest wyrenderowany

**Fix — dodaj na końcu return `DashboardInner`, za blokiem `{showInjectModal && <InjectModal ... />}` (linia ~1469):**

```tsx
{showAddPortalModal && (
  <AddPortalModal
    onClose={() => setShowAddPortalModal(false)}
    onSuccess={(portalId) => {
      setShowAddPortalModal(false)
      setSelectedPortalId(portalId)
    }}
  />
)}
```

**UWAGA:** Sprawdź NAJPIERW jakiej sygnatury używa `AddPortalModal` (linie 658–818) — dopasuj propsy `onClose` i `onSuccess` do faktycznej definicji komponentu. Nie zakładaj — przeczytaj.

---

## BUG #2 — Endpoint `/credentials` nie istnieje — powinno być `/full`

**Plik:** `web/src/app/dashboard/use-portals.ts`

**Diagnoza:**
- Frontend (linia ~67) wywołuje: `GET /v1/portals/${portalId}/credentials`
- Backend (`api/routers/portals.py`) eksponuje: `GET /{portal_id}/full`
- Skutek: każda próba pobrania hasła do publikacji kończy się HTTP 404

**Fix — w `use-portals.ts`, funkcja `getCredentials`:**

```ts
// PRZED:
const res = await fetch(`${apiUrl}/v1/portals/${portalId}/credentials`, {

// PO:
const res = await fetch(`${apiUrl}/v1/portals/${portalId}/full`, {
```

To jedyna zmiana w tym pliku. Backendowy endpoint działa poprawnie.

---

## Weryfikacja przed deployem

Po wprowadzeniu zmian, lokalnie sprawdź TypeScript:
```bash
# Jeśli masz dostęp do lokalnego buildu
npx tsc --noEmit
```

Jeśli nie — przynajmniej upewnij się że propsy `<AddPortalModal>` pasują do definicji komponentu.

---

## Deploy

```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  "cd /home/ubuntu/video-seo-engine && docker compose -f docker-compose.vse.yml build vse-web && docker compose -f docker-compose.vse.yml up -d vse-web"
```

Po deploy: `docker compose -f docker-compose.vse.yml logs vse-web --tail 20` — sprawdź brak błędów kompilacji.

---

## Deliverable

- [ ] BUG #1: `<AddPortalModal>` dodany do return `DashboardInner`
- [ ] BUG #2: `/credentials` → `/full` w `use-portals.ts`
- [ ] Deploy `vse-web` na VPS
- [ ] Potwierdzenie: `docker logs vse-web --tail 20` bez błędów

**NIE weryfikujesz E2E** — to zrobi właściciel produktu manualnie.

**Dual-write raport:**
- `video-seo-engine/.agents/reports/2026-06-29_vse-dev_portal-fix.md`
- `sonic-void/.agents/reports/inbox/2026-06-29_vse-dev_portal-fix.md`

Heartbeat `status: done`.

---

*[Supervisor 01 | sonic-void 29.06.2026]*
