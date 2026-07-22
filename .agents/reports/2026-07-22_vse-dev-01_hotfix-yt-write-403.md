# Raport: Hotfix 403 Forbidden przy wysyłce na YouTube

**Callsign**: vse-dev-01
**Zadanie**: hotfix-yt-write-403 (2026-07-22)

## CO
Dodano odpowiedni scope OAuth (`https://www.googleapis.com/auth/youtube`) do funkcji odbudowującej poświadczenia (`_build_credentials`) w module `api/core/youtube_publish.py`.

## PO CO
Podczas próby wysłania zaktualizowanych metadanych wideo (tytuł, opis) do API YouTube pojawiał się błąd 403 Forbidden. Wynikało to z faktu, że podczas odświeżania tokena za pomocą `refresh_token` nie przekazywano w Credentials oryginalnych uprawnień (scope), co powodowało uzyskanie zredukowanego tokenu pozbawionego uprawnień `write` przy wywołaniu `videos.update`.

## JAK
1. Zmodyfikowano `api/core/youtube_publish.py`.
2. Do konstruktora `Credentials` wewnątrz `_build_credentials` dodano pole `scopes=["https://www.googleapis.com/auth/youtube"]`.
3. Wykonano kopię zapasową (`backup_pre_deploy.sh`) na VPS.
4. Wykonano deploy na VPS (git pull, docker compose build & up vse-api).
5. Potwierdzono poprawne logi kontenera.