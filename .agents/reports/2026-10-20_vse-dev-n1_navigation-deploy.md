# Raport wdrożenia N1: Współdzielony PublicHeader, strona 404 oraz linki logo [vse-dev-n1]

- **Data wdrożenia**: 2026-10-20 22:01 UTC
- **Autor / Callsign**: vse-dev-n1
- **Merge Commit SHA**: `471d0a8a6caf7eb2e3e17ff4b3ab30e41d23c4c4`
- **Snapshot Rollback TAG**: `20261020-220032`
- **Środowisko**: Produkcja VPS (147.224.162.100, `vse-web`)

---

## 1. Zakres wdrożenia

- Utworzono komponent `web/src/components/PublicHeader.tsx` z linkiem do `/` (logo VSE), `/cennik`, `/dashboard` (dla zalogowanych), `/login` i `/register` (dla niezalogowanych), przyciskiem powrotu (`showBack`) i responsywnym układem mobile.
- Utworzono dedykowaną stronę 404 `web/src/app/not-found.tsx` z `PublicHeader`.
- Wstawiono `PublicHeader` na podstronach: `/cennik`, `/platnosci/anulowano`, `/platnosci/sukces`, `/regulamin`, `/polityka-prywatnosci`.
- Zmieniono `<div>` logo na klikalny `<Link href="/">` na: `/`, `/shortmachine` (+ `/en`, `/es`), oraz sidebarach `/historia`, `/ustawienia`, `/admin` i `/dashboard` (`dashboard-inner.tsx`).

---

## 2. Wynik Smoke Testów (https://vse.impresjapr.pl)

| Trasa | HTTP Code | Zawiera `href="/"` | Wynik |
|---|---|---|---|
| `/` | 200 | YES | PASS |
| `/cennik` | 200 | YES | PASS |
| `/regulamin` | 200 | YES | PASS |
| `/polityka-prywatnosci` | 200 | YES | PASS |
| `/platnosci/anulowano` | 200 | YES | PASS |
| `/platnosci/sukces` | 200 | YES | PASS |
| `/login` | 200 | YES | PASS |
| `/nie-istnieje-xyz` | 404 | YES | PASS |

---

## 3. Komenda Rollback (PowerShell)

W razie potrzeby przywrócenia stanu sprzed wdrożenia:

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "/home/ubuntu/scripts/vse_rollback.sh 20261020-220032 --code && docker compose -f /home/ubuntu/video-seo-engine/docker-compose.vse.yml build vse-web && docker compose -f /home/ubuntu/video-seo-engine/docker-compose.vse.yml up -d vse-web"
```
