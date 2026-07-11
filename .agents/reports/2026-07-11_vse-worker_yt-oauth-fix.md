# Raport: Fix YouTube OAuth (Return JSON)

**Data:** 2026-07-11
**Agent:** vse-dev-01
**Task:** Supervisor-03_vse-worker_yt-oauth-fix.md

## Wykonane akcje
Zmodyfikowano endpoint `GET /v1/youtube/oauth/login` w `api/routers/youtube.py`, aby zapobiec błędom CORS wynikającym z użycia `RedirectResponse` w zapytaniach fetch().
Commit SHA: `89a3cc51fd278795415cde726a4e28f2eebe04f3`.

### Kod PRZED zmianą
```python
@router.get("/oauth/login")
async def youtube_oauth_login(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    oauth_state = OAuthState.create_for_user(current_user.id)
    db.add(oauth_state)
    await db.commit()
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?response_type=code"
        f"&client_id={GOOGLE_CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        f"&scope={YT_SCOPE}&access_type=offline&prompt=consent"
        f"&state={oauth_state.state_token}"
    )
    return RedirectResponse(auth_url)
```

### Kod PO zmianie
```python
@router.get("/oauth/login")
async def youtube_oauth_login(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    oauth_state = OAuthState.create_for_user(current_user.id)
    db.add(oauth_state)
    await db.commit()
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?response_type=code"
        f"&client_id={GOOGLE_CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        f"&scope={YT_SCOPE}&access_type=offline&prompt=consent"
        f"&state={oauth_state.state_token}"
    )
    return {"authorization_url": auth_url}
```

## Deploy
Wykonano deploy serwisów API i Web na VPS.
`docker logs --tail 10 vse-api`:
```
2026-07-11 12:14:37,197 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:60848 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 12:14:47,759 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:41274 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 12:14:58,330 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:34822 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 12:15:08,881 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:39732 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 12:15:19,460 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:54602 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
```