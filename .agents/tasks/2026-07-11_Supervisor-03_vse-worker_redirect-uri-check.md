# Dispatch: Diagnostyka REDIRECT_URI — szybka
**Od:** Supervisor-03  
**Do:** vse-worker (Flash)  
**Data:** 2026-07-11  
**Priorytet:** KRYTYCZNY — 2 komendy SSH, raport surowych danych

---

## ZADANIE

Sprawdź co backend FAKTYCZNIE wysyła do Google jako `redirect_uri`.

## KOMENDY — wykonaj dokładnie te dwie

```powershell
# 1. Co jest w .env na VPS
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "grep -i 'redirect\|youtube\|google\|client' /home/ubuntu/video-seo-engine/.env"
```

```powershell
# 2. Co jest w kodzie youtube.py
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "grep -n 'REDIRECT_URI\|redirect_uri\|GOOGLE_CLIENT\|vse.impresjapr' /home/ubuntu/video-seo-engine/api/routers/youtube.py"
```

## RAPORT — dual-write

1. `video-seo-engine/.agents/reports/2026-07-11_vse-worker_redirect-uri-check.md`
2. `sonic-void/.agents/reports/inbox/2026-07-11_vse-worker_redirect-uri-check.md`

Raport: surowe outputy obu komend. Nic więcej.

---
*[Supervisor-03 | sonic-void 11.07.2026]*