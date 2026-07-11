# Raport: Fix YouTube OAuth (Return JSON) i Konfiguracja GCP

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

## Dodatek: Zmiana Google Cloud Project
Ze względu na powtarzający się błąd `redirect_uri_mismatch` na środowisku produkcyjnym z użyciem starego Client ID `302321935728...`, zalecono użytkownikowi konfigurację całkowicie nowego, dedykowanego projektu w Google Cloud.
- Użytkownik utworzył projekt "Video SEO Engine" i wygenerował nowe klucze OAuth (Client ID: `934133075831-...`).
- Otrzymano od użytkownika plik JSON z nowymi poświadczeniami.
- Zaktualizowano zmienne `GOOGLE_CLIENT_ID` i `GOOGLE_CLIENT_SECRET` w środowisku serwera VPS (`/home/ubuntu/video-seo-engine/.env`).
- Zrestartowano kontenery `vse-api` oraz `vse-web`.

### Aktualny stan (Handoff)
- Nowe ustawienia środowiskowe na VPS zostały załadowane pomyślnie.
- Aktualnie czekamy na propagację zmian DNS / uprawnień po stronie serwerów Google (co może trwać 5-10 minut).
- Spisano raport handoff dla następnego agenta z prośbą o pobranie "error details" z ekranu Google od użytkownika, w razie gdyby problem mismatch występował dalej.

## Deploy
Wykonano deploy serwisów API i Web na VPS.
Logi kontenerów (zarówno po pierwszej poprawce CORS jak i po wymianie kluczy OAuth) potwierdzają stabilną pracę serwera.