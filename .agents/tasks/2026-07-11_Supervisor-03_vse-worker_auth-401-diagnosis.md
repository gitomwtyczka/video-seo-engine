# Dispatch: Diagnoza 401 Unauthorized — zbieranie danych
**Od:** Supervisor-03  
**Do:** vse-worker (Flash)  
**Data:** 2026-07-11  
**Typ:** data-collection — surowe outputy, bez analizy

---

## CEL

Zbierz dane diagnostyczne dot. problemu: wszystkie API calls zwracają 401 Unauthorized (portale, historia, /v1/users/me). Supervisor zrobi analizę po otrzymaniu danych.

## ⚠️ ZNANE PUŁAPKI
1. SSH — używaj pełnych ścieżek Windows do klucza
2. Nie analizuj — tylko zbieraj surowe outputy
3. psql może wymagać `-d vse` lub innej nazwy bazy — sprawdź jeśli błąd

## KOMENDY DO WYKONANIA (SSH)

```powershell
# 1. Backend logi ostatnie 60 linii
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker logs --tail 60 vse-api 2>&1"

# 2. Portale w bazie
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker exec vse-postgres psql -U postgres -d vse -c 'SELECT id, name, url, user_id FROM wp_portals LIMIT 20;'"

# 3. Joby w bazie
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker exec vse-postgres psql -U postgres -d vse -c 'SELECT id, user_id, created_at, status FROM jobs ORDER BY created_at DESC LIMIT 10;'"

# 4. refreshAccessToken w route.ts
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "grep -A 25 'refreshAccessToken' /home/ubuntu/video-seo-engine/web/src/app/api/auth/\[...nextauth\]/route.ts"

# 5. NEXTAUTH env vars
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "grep 'NEXTAUTH' /home/ubuntu/video-seo-engine/.env"

# 6. Auth refresh endpoint
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "grep -n 'refresh' /home/ubuntu/video-seo-engine/api/routers/auth.py | head -20"

# 7. Tabele w bazie (weryfikacja nazw)
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker exec vse-postgres psql -U postgres -d vse -c '\dt'"
```

## RAPORT

Dual-write:
1. `video-seo-engine/.agents/reports/2026-07-11_vse-worker_auth-401-data.md`
2. `sonic-void/.agents/reports/inbox/2026-07-11_vse-worker_auth-401-data.md`

Raport = surowe outputy wszystkich komend, każda opisana numerem.

---
*[Supervisor-03 | sonic-void 11.07.2026]*