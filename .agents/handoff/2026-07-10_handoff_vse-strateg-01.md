# Handoff: Zakończenie sesji przedwczesne (zmiana strategii na żądanie użytkownika)

**Data:** 2026-07-10
**Callsign:** vse-strateg-01

Użytkownik przerwał diagnostykę błędu "Application Error" rzucanego przez przeglądarkę przy próbie logowania w panelu i poprosił o zmianę podejścia (sporządzenie raportu z ustaleń dla Supervisora, a nie modyfikację produkcyjną w ciemno).

**Stan aplikacji:**
Błąd 500 rzucany jest tylko po stronie callbacku NextAuth. Wykonana komenda Nginx na VPS (`curl POST /api/auth/callback/credentials`) potwierdza 500-tkę. W dockerze brak logów, co utrudnia identyfikację linijki na Next.js.
Prawdopodobną przyczyną jest niespójność formatu wymiany payloadu dla logowania (z json w `route.ts` na `application/x-www-form-urlencoded` w API po ostatnich migracjach bazy i Fazy 3).

**Co zostało zrobione:**
- Ubito workera z pętlą naprawczą, przerywając działania.
- Sporządzono oficjalny raport do skrzynki `sonic-void`.
- Zaktualizowano `heartbeat.json` na status `handoff`.
- Zaktualizowano `current.md`.

**Co musi zrobić następny Agent po akcepcie od Supervisora:**
Musi przeanalizować routery w `vse-api`, aby sprawdzić jak backend przyjmuje logowanie, a następnie wprowadzić poprawki w `web/src/app/api/auth/[...nextauth]/route.ts`. Przed deployem odpalić w kontenerze flagę `debug: true` dla authOptions by dostać pełen log, co zapobiegnie crashowaniu po cichu w production build. 

Zaleca się nową sesję roboczą pod szyldem workera (`vse-dev`), w porozumieniu z Supervisorem.