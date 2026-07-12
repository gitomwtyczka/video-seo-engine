# Raport: Naprawa błędów frontendowych po wdrożeniu publikacji YouTube

**Callsign:** [vse-dev-01]
**Data:** 2026-07-12
**Cel:** Naprawa ReferenceError w `dashboard-inner.tsx`, obsługa braku kanałów YT, i zachowanie polskich znaków.

## Co zostało zrobione
1. **ReferenceError: ytChannels is not defined:** W pliku `InjectModal` i `dashboard-inner.tsx` brakowało prawidłowego zadeklarowania dostępu do tej zmiennej podczas renderowania modalów. Usunięto błąd poprzez dodanie przekazywania `ytChannels` do komponentu modala w dashboard.
2. **Endpoint `/api/youtube/channels` zamiast `/v1/youtube/channels`:** Fetch request do pobierania kanałów próbował połączyć się ze złym endpointem frontendowym. Zmodyfikowano na odpytywanie głównego API (`process.env.NEXT_PUBLIC_API_URL/v1/youtube/channels`).
3. **Puste listy kanałów YT:** Dodałem wizualne wsparcie w obu modalach (InjectModal i YouTubePublishModal) w sytuacji, gdy kanały YT nie są jeszcze połączone, dodając link zachęcający do przejścia do `Ustawień`. Wcześniej cały interfejs dla publikacji na YT po prostu znikał, co blokowało użycie.
4. **Kodowanie:** Problem z polskimi znakami, który pojawił się w logach, wynikał z mechanizmu zapisu z PowerShell przy wrzucaniu plików na GitHub – wykorzystano binarne wysyłanie (Base64) kodu zamiast jako tekst, by zachować pełne polskie kodowanie znaków w `dashboard-inner.tsx` i `YouTubePublishModal.tsx`.
5. **Deploy:** Kontener `vse-web` został przebudowany z najnowszymi poprawkami na VPS i pomyślnie wystartował.

## Pułapki, na które się natknąłem
1. **PowerShell a kodowanie w Git:** Standardowe wysłanie pliku przez Powershell z wykorzystaniem komend stringów modyfikowało nowe linie i kodowanie. Warto zważać na odczyty jako byte-array (`[System.IO.File]::ReadAllBytes`).
2. Nginx Rewrites i API NextJS: `/api` odnosi się do Next.js w standardowym Next router. Komponenty odpytujące bazowe API projektowe powinny korzystać z `$NEXT_PUBLIC_API_URL/v1/...`. Zauważone podczas testowania.

## Rezultat
Front-End powinien odzyskać pełną funkcjonalność, wyświetlać zachęty do połączenia kanałów i polskie znaki w interfejsie. Modale ładują się prawidłowo.