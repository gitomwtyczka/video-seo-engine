# HOTFIX — vse-dev | ReferenceError: setYtDescription is not defined

**Data:** 2026-07-13  
**Od:** Supervisor 01  
**Do:** vse-dev  
**Zakres:** TYLKO `dashboard-inner.tsx` — naprawa scope buga. Deploy po commicie.

---

## ⚡ KROK 0

```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: sonic-void
  branch: master
  path: .agents/protocols/dispatch-system-block.md
```
Heartbeat do `video-seo-engine/.agents/heartbeat.json`.

---

## 🔍 BŁĄD

```
ReferenceError: setYtDescription is not defined
```

Produkuje crash całego dashboardu po wygenerowaniu SEO.

**Przyczyna:** `const [ytDescription, setYtDescription] = useState<string>('')`
zostało umieszczone w złym miejscu — poza komponentem `DashboardInner`, lub w innym bloku
niż `useEffect` który go używa. `setYtDescription` nie jest w scope.

---

## 📋 ZADANIE

### Krok 1: Znajdź problem

Pobierz `web/src/app/dashboard/dashboard-inner.tsx` przez `get_file_contents`.

Szukaj w kodzie:
1. Gdzie jest `const [ytDescription, setYtDescription] = useState` — w którym komponencie?
2. Gdzie jest `useEffect` z `setYtDescription(...)` — w którym komponencie?
3. Czy oba są w TYM SAMYM ciele funkcji komponentu `DashboardInner`?

Jeśli nie — przenieś oba do `DashboardInner` (lub tam gdzie jest główny stan `result`).

### Krok 2: Fix

**Zasada:** `useState` i `useEffect` które używają `ytDescription`/`setYtDescription`
MUSZĄ być wewnątrz tej samej funkcji komponentu.

Sprawdź też czy:
- `buildYtDescription` jest zdefiniowane PRZED komponentem (jako zwykła funkcja helper) — OK
- `useEffect` ma poprawne zależności w tablicy `[result]`
- `ytDescription` jest przekazywane do `YouTubePublishModal` jako prop

### Krok 3: Deploy

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web"
```

Sprawdź logi po deployu:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "docker logs vse-web --tail 15"
```

---

## ✅ DEFINITION OF DONE

- [ ] `setYtDescription is not defined` znika
- [ ] Dashboard nie crashuje po wygenerowaniu SEO
- [ ] Zakładka "Opis YouTube" jest widoczna
- [ ] Deploy zakończony

---

## 📨 RAPORT

```
video-seo-engine/.agents/reports/2026-07-13_vse-dev_hotfix-scope.md
sonic-void/.agents/reports/inbox/2026-07-13_vse-dev_hotfix-scope.md
```

Zawartość: gdzie był błąd (linia), co zmieniono, SHA commitu.

---

*Supervisor 01 | sonic-void | 2026-07-13 | HOTFIX*
