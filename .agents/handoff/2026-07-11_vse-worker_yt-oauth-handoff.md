# Handoff: vse-dev-01 -> NEXT
**Data:** 2026-07-11
**Temat:** Problem redirect_uri_mismatch na produkcji

## Kontekst
Wdrożyliśmy zmianę w zwracaniu JSON z `youtube_oauth_login` (`api/routers/youtube.py`). Pojawił się błąd CORS, ale to wynikało z niezarejestrowanych redirect URI. 

Użytkownik próbował zmienić to w GCP, ale okazało się, że ma zły projekt (używaliśmy starego Client ID `302321935728...`). Użytkownik utworzył NOWY projekt GCP (Video SEO Engine), podał nowy `client_id` i `client_secret`. 
Zaktualizowałem plik `.env` na VPS i zrestartowałem `vse-api` oraz `vse-web`. W `.env` zapisano nowe dane uwierzytelniające dla NextAuth.

## Problem w toku
Początkowo nadal zgłaszało błąd `redirect_uri_mismatch`. Zostawiłem użytkownika czekającego na propagację ustawień po stronie Google (co może trwać do 5-10 minut).

## Next Steps dla Ciebie
1. Powitaj użytkownika (świeża sesja).
2. Sprawdź, czy po odczekaniu błąd ustąpił.
3. Jeśli błąd nadal występuje, ZAPYTAJ O "error details" (szczegóły błędów na dole strony logowania Google), żeby sprawdzić jaki dokładnie URL NextAuth lub API próbuje wysłać, a jakiego brakuje w panelu Google Cloud.
4. Upewnij się, że w Next.js w `docker-compose.vse.yml` i na produkcji zmienna `NEXTAUTH_URL` używa HTTPS. Zmienna `GOOGLE_REDIRECT_URI` jest wpisana w `.env` jako `https://vse.impresjapr.pl/api/v1/auth/google/callback` ale NextAuth zazwyczaj używa `https://vse.impresjapr.pl/api/auth/callback/google`.
