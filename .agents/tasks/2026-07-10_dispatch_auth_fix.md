# Dispatch: Naprawa Client-side exception przy logowaniu (HTTP 500 w NextAuth)

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)
1. GitHub MCP: po create_or_update_file ZAWSZE zweryfikuj newlines
2. SSH: NIE buduj złożonych komend inline — write_to_file → scp → ssh
3. Next.js na produkcji "polyka" errory 500 w logach. Żeby zobaczyć logi w `route.ts`, wpisz `debug: true` w obiekcie `authOptions`. Pamiętaj, by po zdiagnozowaniu to usunąć!
4. ⛔️ Pamiętaj o MANDATORY PRE-DEPLOY BACKUP na VPS (`/home/ubuntu/scripts/backup_pre_deploy.sh`) ZANIM zrobisz deploy jakiejkolwiek zmiany na serwer. (Sprawdź regułę w AGENTS.md!).

## KONTEKST
Frontend rzuca w użytkownika: "Application error: a client-side exception has occurred" w momencie kliknięcia Zaloguj. Przeprowadziłem śledztwo: curl wykonany na `POST https://vse.impresjapr.pl/api/auth/callback/credentials` na VPS daje `HTTP 500 Internal Server Error` od Nginxa. Brak 500-tki w logach kontenera `vse-web` (pewnie polyka to release Next.js). 

**Moja hipoteza stratega:**
Wdrażający w Faza 3 (poprzednik) zrekonstruował logowanie w `vse-api` (wprowadzając w FastAPI autoryzację po OAuth2 form / fernet). Prawdopodobnie endpoint API dla logowania spodziewa się np. `application/x-www-form-urlencoded` z fields: `username` i `password`. W tym czasie `web/src/app/api/auth/[...nextauth]/route.ts` nadal strzela POST JSONem: `body: JSON.stringify({email, password})`. Gdy to odbiera, FastAPI zwraca HTTP 422, co w `route.ts` jest nieobsłużone i NextAuth wyrzuca klienta twardym parsowaniem błędu. To powoduje crash po stronie frontu.

## TWOJE ZADANIE:
1. Przeanalizuj logikę backendową użytkownika `vse-api` (zobacz plik routera: `api/routers/auth.py` lub podobny od logowania).
2. Potwierdź moją hipotezę (lub ją obal) - być może konieczne było użycie nowej ścieżki importu, np. `/v1/auth/token`?
3. Wypchnij bezpośrednio poprawkę do `route.ts` i ew. zapuść ręczny hot-fix na serwer VPS.
4. Zanim przeprowadzisz deploy na VPS i dokonasz zmian (git pull, docker compose up), wywołaj `backup_pre_deploy.sh` przez SSH zgodnie ze standardami!!
5. Upewnij się, że logowanie credentials wciąż działa poprawnie w konsoli / devtools i user wejdzie do dasha.
6. Pisz statusy z dual-write raportem do mnie na końcu, zamknij dispatch.