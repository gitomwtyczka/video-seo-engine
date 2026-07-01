# DISPATCH: VSE-DEV-20260701 — InjectModal Fix (selectedPortalId)

**Zlecenie od:** Supervisor 02 (sonic-void)
**Data:** 2026-07-01
**Priorytet:** KRYTYCZNY — blokuje core feature dla wszystkich użytkowników Pro/Agency
**Estymacja:** 2-3h

## Problem

W `web/src/app/dashboard/dashboard-inner.tsx` komponent `<InjectModal>` jest wywoływany BEZ przekazania `selectedPortalId`, `portalName` i `portalUrl`.

Efekt: `selectedPortalId === undefined` powoduje `isManual = true` zawsze. InjectModal zawsze pokazuje ręczny formularz credentials z localStorage, nigdy nie używa wybranego portalu z dropdown. Użytkownik Pro płaci za auto-publish z zapisanego portalu — ta funkcja jest broken.

## Fix

### Krok 1: Znajdź state portalu w dashboard-inner.tsx

Zidentyfikuj jak portal jest wybrany w dropdownie oraz jaką zmienną przechowuje wybrany portal (selectedPortalId lub podobna). Znajdź skąd pobrać portalName i portalUrl dla wybranego portalu.

### Krok 2: Przekaż props do InjectModal

Poprawiony kod:

```tsx
{showInjectModal && result && (
  <InjectModal
    schemaData={result.raw}
    videoUrl={result.inputUrl}
    onClose={() => setShowInjectModal(false)}
    selectedPortalId={selectedPortalId}
    portalName={selectedPortal?.name}
    portalUrl={selectedPortal?.url}
  />
)}
```

### Krok 3: Weryfikacja

Sprawdź sygnaturę InjectModal (wszystkie wymagane props) i upewnij się że:
- Gdy selectedPortalId jest przekazany to isManual = false
- Modal pokazuje "Credentials pobrane z zapisanego portalu" zamiast "localStorage"

## Deployment

1. Commit do main przez GitHub MCP
2. SSH: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose restart vse-web"`
3. Weryfikacja: `docker logs vse-web --tail 20`

## ZNANE PULAPKI
1. SSH user: ubuntu (NIE root)
2. Nie używaj ask_permission na SSH — run_command bezpośrednio
3. GitHub MCP: po każdym commicie weryfikacja newlines przez get_file_contents
4. Sprawdź czy usePortals zwraca obiekty z polem url (nie tylko id i name)

## Raport końcowy
- Commit SHA
- Które zmienne stanu przekazałeś
- Wynik testu czy isManual zmienia się po wyborze portalu
- Deploy status
