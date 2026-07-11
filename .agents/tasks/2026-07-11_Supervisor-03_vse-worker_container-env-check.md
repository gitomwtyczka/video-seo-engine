# Dispatch: Exec container — co widzi vse-api w runtime
**Od:** Supervisor-03  
**Do:** vse-worker (Flash)  
**Data:** 2026-07-11  
**Priorytet:** KRYTYCZNY — 1 komenda SSH

## ZADANIE

Jedna komenda — zwróć surowy output:

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker exec vse-api env | grep -i 'youtube\|google\|redirect\|client'"
```

Jeśli `docker exec vse-api` nie działa (inny container name), spróbuj:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker ps --format '{{.Names}}' | grep -i api"
```

Zwraca nazwę, potem:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker exec [NAZWA] env | grep -i 'youtube\|google\|redirect\|client'"
```

## RAPORT — dual-write

1. `video-seo-engine/.agents/reports/2026-07-11_vse-worker_container-env-check.md`
2. `sonic-void/.agents/reports/inbox/2026-07-11_vse-worker_container-env-check.md`

Raport: surowy output `docker exec env`. Nic więcej.

---
*[Supervisor-03 | sonic-void 11.07.2026]*