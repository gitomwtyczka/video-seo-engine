# Dispatch: Fix ReferenceError accessToken is not defined
**Od:** Supervisor-03  
**Do:** vse-worker (Flash)  
**Data:** 2026-07-11  
**Priorytet:** KRYTYCZNY — dashboard crashuje przy otwarciu artykułu z historii

---

## ⚠️ ZNANE PUŁAPKI
1. Plik ~77KB — weryfikuj rozmiar po zapisie (powinien być ok. 77000-78000 bytes).
2. `accessToken` w DashboardInner jest zadeklarowany: `const accessToken = (session as any)?.accessToken as string | undefined` — to LOKALNA zmienna DashboardInner, NIE prop InjectModal.
3. W InjectModal `accessToken` przychodzi jako PROP — musi być przekazany jawnie przy renderowaniu.
4. Rules of Hooks — nigdy early return przed hookami.

---

## KROK 1 — Diagnostyka przez SSH

Wykonaj te dwa grepy i zwróć mi wyniki w raporcie:

```powershell
# Grep 1: wszystkie wystąpienia accessToken w pliku
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "grep -n 'accessToken' /home/ubuntu/video-seo-engine/web/src/app/dashboard/dashboard-inner.tsx"
```

```powershell
# Grep 2: czy accessToken jest przekazany do InjectModal w JSX
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "grep -n -A 10 'InjectModal' /home/ubuntu/video-seo-engine/web/src/app/dashboard/dashboard-inner.tsx | grep -A 10 'showInjectModal'"
```

---

## KROK 2 — Naprawa

Na podstawie wyników grep sprawdzić:

**Scenariusz A** — `accessToken` użyte POZA `DashboardInner` lub `InjectModal`:
Przenieś użycie do właściwej funkcji.

**Scenariusz B** — `accessToken` NIE jest przekazany jako prop do `<InjectModal>` w JSX:
Znajdź render `<InjectModal` w JSX DashboardInner i dodaj `accessToken={accessToken}` do jego propsów. Przykładowy fragment:
```tsx
{showInjectModal && result && (() => {
  // ...
  return (
    <InjectModal
      schemaData={result.raw}
      videoUrl={result.inputUrl}
      selectedPortalId={selectedPortalId}
      portalName={selectedPortal?.name}
      portalUrl={selectedPortal?.url}
      accessToken={accessToken}   {/* ← to musi być */}
      onClose={() => setShowInjectModal(false)}
    />
  )
})()}
```

**Scenariusz C** — `accessToken` zadeklarowany W ZŁEJ KOLEJNOŚCI (po użyciu):
Przenieś deklarację `const accessToken = (session as any)?.accessToken...` wyżej w DashboardInner, przed wszelkimi hookami które go używają.

Naprawa: pobierz plik przez `get_file_contents`, wprowadź poprawkę, wgraj przez `create_or_update_file`.

---

## KROK 3 — Deploy i weryfikacja

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web 2>&1 | tail -5"
```

Po 30s:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker logs --tail 10 vse-web 2>&1"
```

---

## RAPORT — dual-write

1. `video-seo-engine/.agents/reports/2026-07-11_vse-worker_accesstoken-fix.md`
2. `sonic-void/.agents/reports/inbox/2026-07-11_vse-worker_accesstoken-fix.md`

Raport: wyniki grepów + który scenariusz + commit SHA + `✓ Compiled successfully`.

---
*[Supervisor-03 | sonic-void 11.07.2026]*