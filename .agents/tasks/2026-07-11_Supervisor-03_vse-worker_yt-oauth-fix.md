# Dispatch: Fix youtube oauth/login — return JSON zamiast redirect
**Od:** Supervisor-03  
**Do:** vse-worker (Flash)  
**Data:** 2026-07-11  
**Priorytet:** KRYTYCZNY — OAuth CORS block

---

## ROOT CAUSE

Endpoint `GET /v1/youtube/oauth/login` robi `RedirectResponse` (302) na Google OAuth URL.
Frontend woła go przez `fetch()` — przeglądarka automatycznie podąża za redirectem i trafia
na `accounts.google.com` które blokuje CORS:
```
Access to fetch at 'https://accounts.google.com/o/oauth2/...' 
(redirected from 'https://vse.impresjapr.pl/v1/youtube/oauth/login') 
has been blocked by CORS policy
```

## FIX — backend: `api/routers/youtube.py`

### KROK 1 — Przeczytaj plik

GitHub MCP:
- repo: gitomwtyczka/video-seo-engine, branch: main
- path: `api/routers/youtube.py`

### KROK 2 — Zmiana

Znajdź funkcję `youtube_oauth_login`. Prawdopodobnie wygląda tak:
```python
@router.get("/oauth/login")
async def youtube_oauth_login(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # ... buduje authorization_url ...
    return RedirectResponse(url=authorization_url)
```

Zmień ostatnią linię z `RedirectResponse` na zwrot JSON:
```python
    return {"authorization_url": authorization_url}
```

Jeśli funkcja nie buduje `authorization_url` lokalnie tylko od razu robi redirect —
złóż URL z parametrów które ma (client_id, redirect_uri, scope) i zwróć jako JSON.

### KROK 3 — Wgraj przez GitHub MCP

Utworzony plik przez `create_or_update_file` z aktualnym SHA.

### KROK 4 — Deploy backend + frontend

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-api vse-web 2>&1 | tail -10"
```

Po 30s:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker logs --tail 10 vse-api 2>&1"
```

---

## RAPORT — dual-write

1. `video-seo-engine/.agents/reports/2026-07-11_vse-worker_yt-oauth-fix.md`
2. `sonic-void/.agents/reports/inbox/2026-07-11_vse-worker_yt-oauth-fix.md`

Raport: pełna treść funkcji `youtube_oauth_login` przed i po + commit SHA + `docker logs` API.

---
*[Supervisor-03 | sonic-void 11.07.2026]*