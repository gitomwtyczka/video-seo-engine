# Raport z diagnostyki: Application error po fazie 3 (NextAuth)

**Data:** 2026-07-10
**Callsign:** vse-strateg-01
**Temat:** Auth Error Analysis po migracji Fazy 3

Użytkownik odrzucił dalsze improwizacje naprawcze na żywo i zażądał przerwania diagnozowania przez workera, zlecając przekazanie suchych i udokumentowanych faktów bezpośrednio do Supervisora. 

W związku z tym zawiesiłem proces i przygotowałem twarde ustalenia, które blokują poprawne logowanie.

## Twarde fakty i ustalenia z diagnostyki
1. **Objaw kliencki:** Próba logowania formularzem *Credentials* kończy się na froncie zgłoszeniem Next.js: `Application error: a client-side exception has occurred`.
2. **Zachowanie usługi (CURL test):** Bezpośrednie odpytanie endpintu logowania POST na Nginxie `https://vse.impresjapr.pl/api/auth/callback/credentials` z wewnątrz serwera VPS (przy użyciu SSH i curla) zwraca od razu `HTTP/1.1 500 Internal Server Error` od serwera Nginx.
3. **Brak logów:** W kontenerze `vse-web` nie ma żadnego zrzutu Stack Trace dotyczącego błędu HTTP 500 dla NextAuth. Proces kompilacji `standalone` w Next.js po cichu połyka takie wyjątki z routingu i nie przekazuje ich na STDOUT dockera.
4. **Czysty backend API:** W logach serwera `vse-api` nie widać żadnego zarejestrowanego błędu ani w ogóle faktu zapytania na endpoint `/v1/auth/login`. Wyświetlane są tylko standardowe pingi tła (`/pending: 0 jobs returned`).
5. **Konfiguracja NextAuth:** Zmienna środowiskowa w `vse-web` kontenera `NEXTAUTH_SECRET` jest poprawnie załadowana i obecna. Także test zapytania `GET /api/auth/providers` działa i rzuca poprawny JSON konfiguracyjny (status 200), udowadniając że Nginx kieruje ruch poprawnie do Next.js i sam NextAuth działa do momentu wywołania akcji autoryzacji z fetch().
6. **Rozdźwięk logiki API:** Kod źródłowy w `web/src/app/api/auth/[...nextauth]/route.ts` przy funkcji authorize wysyła request do backendu (FastAPI) za pomocą payloadu `JSON.stringify({email, password})` jako Content-Type: `application/json`. Z raportu Fazy 3 wynika, że "Zabezpieczono braki w uwierzytelnianiu", co najpewniej oznacza przejście backendu na formularz `x-www-form-urlencoded` OAuth2 FastAPI. 

## Co blokuje naprawę?
Ukryty log w `vse-web`. Aby z pewnością wiedzieć co rzuca Nginx z wewnątrz Dockera, konieczne jest ręczne podbicie opcji `debug: true` w konfiguracji obiektu `authOptions` pliku `route.ts`. Supervisor po zapoznaniu z tymi faktami powinien wydać dyspozycję poprawnemu zespołowi wdrożeniowemu na przeprowadzenie zmiany w `route.ts`. 

## Status Workera
Polecenie zostało anulowane i wszystkie procesy naprawcze z workera `vse-dev-01` w tle zostały **zabite**, chroniąc serwer i bazę przed naruszeniem bez dokładnego planu od Supervisora. Wymagany restart i nowa sesja decyzyjna (handoff).