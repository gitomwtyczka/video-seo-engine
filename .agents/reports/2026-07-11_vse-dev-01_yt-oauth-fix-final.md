# Raport: Rozwiązanie błędu redirect_uri_mismatch
**Data:** 2026-07-11
**Agent:** vse-dev-01

## Cel
Naprawa powracającego błędu `400: redirect_uri_mismatch` dla integracji OAuth z YouTube (połaczenie kanału).

## Diagnoza 
Zbadaliśmy konfigurację po stronie VPS oraz nginx. Stwierdzono następujący przepływ dla requestu uwierzytelnienia z Google:
1. `api/routers/youtube.py` używał zmiennej `REDIRECT_URI`, której wartość domyślna wynosiła: `https://vse.impresjapr.pl/api/v1/youtube/oauth/callback`. Zostało to zmodyfikowane w przeszłości na bazie fałszywego założenia, że Nginx przekierowuje do backendu ruch za pomocą adresu skróconego i oczekuje, byśmy ten `/api` mieli (komentarz w kodzie mówił: "Fixed REDIRECT_URI to include /api prefix because nginx routes /api/v1 to backend").
2. Google Cloud próbował użyć wskazanego `REDIRECT_URI` i wyrzucał wyjątek, ponieważ przekierowywał użytkownika na ten sam adres z `/api/`.
3. Analiza pliku `default.conf` kontenera `crimson-nginx` wykazała, że Nginx **przekazuje prefix /api** dla zapytań backendowych (ponieważ blok `location /api/` używał `proxy_pass` na `http://172.17.0.1:8085;` - bez ukośnika, co oznacza, że prefix nie jest ścinany przez Nginx w trybie path-rewrite).
4. Jednak w `vse-api` logi pokazywały: `"GET /api/v1/youtube/oauth/callback?state=... HTTP/1.0" 404 Not Found`. Backend rzucał `404`, bo FastAPI operowało na prefixie routów zaczynającym się od `/v1/`, a nie `/api/v1/`.
5. Jednocześnie aplikacja w całości działała normalnie tylko z powodu faktu, że frontend Next.js odpytuje endpointy bezpośrednio pod `vse.impresjapr.pl/v1/...` korzystając z odrębnego bloku proxy w Nginx (`location /v1/ { proxy_pass http://172.17.0.1:8085; }`). Wszelkie odpytania bezpośrednio do `/v1/` były właściwie mapowane przez Nginx na backend jako `/v1/`.

## Rozwiązanie
Zdecydowano się naprawić kod źródłowy zamiast modyfikować konfigurację infrastruktury nginx, by utrzymać integralność wywołań frontendowych:
1. Plik `api/routers/youtube.py` został zmodyfikowany: usunięto fragment `/api` z `REDIRECT_URI`. Poprawny adres to teraz: `https://vse.impresjapr.pl/v1/youtube/oauth/callback`.
2. Zaktualizowano komentarze w kodzie, korygując nieporozumienie co do działania Nginxa.
3. Kontenery `vse-api` zostały przebudowane (`docker compose build vse-api` i `docker compose up -d vse-api`) z nowym kodem źródłowym na VPS.

## Status
Zakończono. Użytkownik musi jedynie zmodyfikować Authorized Redirect URI w GCP Console, tak by pasował do zaktualizowanego kodu bez prefiksu `/api`, i logowanie zakończy się pełnym sukcesem bez błędu 404 po powrocie z OAuth.