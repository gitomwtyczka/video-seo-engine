# Raport Eskalacyjny: Regres w logowaniu YouTube OAuth
**Data:** 2026-07-11
**Agent:** vse-dev-01
**Temat:** Błąd 400 redirect_uri_mismatch mimo pełnej zgodności URI z konsolą GCP

## 1. Kontekst i Tło Sytuacji
Podczas integracji logowania kanałów YouTube w module `vse-api` pojawiał się błąd `400: redirect_uri_mismatch`. Zlokalizowaliśmy problem w architekturze komunikacji:
* Skrypt backendowy generował `redirect_uri` w postaci `https://vse.impresjapr.pl/api/v1/youtube/oauth/callback`.
* Z powodu specyficznej konfiguracji bloku `location /api/` w Nginx, zapytania z `/api/` wchodziły do backendu w całości (Nginx nie ucinał prefiksu). Backend jednak obsługuje ścieżki od `/v1/`, przez co wywołania te trafiały w próżnię (404).

Rozwiązaliśmy ten problem z sukcesem poprzez usunięcie przedrostka `/api` ze zmiennej `REDIRECT_URI` bezpośrednio w kodzie API i wdrożenie kontenerów (commit `09fe3053`).
Następnie poleciliśmy użytkownikowi dodanie poprawionego adresu do Google Cloud Console.

## 2. Bieżący Status
Użytkownik dodał **poprawny adres** jako `URIs 3` w sekcji "Authorized redirect URIs" w GCP:
`https://vse.impresjapr.pl/v1/youtube/oauth/callback`

Mimo odczekania ok. 8 minut i ponownej próby logowania, Google wciąż odrzuca zapytanie.
Na ekranie błędu widnieje komunikat:
`Błąd 400: redirect_uri_mismatch`
Z informacją wewnątrz:
`redirect_uri=https://vse.impresjapr.pl/v1/youtube/oauth/callback`

Zestawiając zrzuty ekranu: wartość wysłana przez naszą aplikację jest **absolutnie identyczna** z wartością wpisaną przez użytkownika do konsoli GCP.

## 3. Podjęte kroki analityczne i dane
* Weryfikacja Client ID: Z poziomu VPS odczytano `GOOGLE_CLIENT_ID=934133075831...`. Ten sam ciąg znaków widnieje na zrzucie ekranu z Google Cloud Console użytkownika. Aplikacja uderza do prawidłowego projektu GCP.
* Weryfikacja routingu po poprawce: Aplikacja poprawnie wygenerowała URL OAuth ze zmienionym, skróconym linkiem (bez `/api`).
* Środowisko testowe GCP: Aplikacja znajduje się w trybie "Testing", ale użytkownik operujący aplikacją znajduje się na liście "Test users" (wcześniejszy błąd 403 z tym związany został zażegnany).

## 4. Wnioski i Przypuszczenia (do analizy przez Supervisora)
Dlaczego Google nadal twierdzi, że URI się nie zgadza?

**Hipoteza 1: Opóźnienie propagacji konfiguracji w klastrach Google (Najbardziej prawdopodobne)**
Google bezpośrednio zaznacza w konsoli: *"It may take 5 minutes to a few hours for settings to take effect"*. Choć zazwyczaj trwa to kilka minut, w niektórych przypadkach, szczególnie w weekendy i przy częstych zmianach tych samych kluczy, serwery uwierzytelniające mogą korzystać z zbuforowanych (starych) autoryzowanych adresów. Użytkownik testował po 8 minutach od kliknięcia "Save". Prawdopodobnie konfiguracja jeszcze się nie rozeszła.

**Hipoteza 2: Niewidoczne znaki w konfiguracji (Częsty błąd UI)**
Podczas wklejania adresu z czatu do pola "URIs 3" w konsoli Google Cloud, mógł zostać skopiowany niewidoczny znak, na przykład biała spacja na końcu lub znak nowej linii. Wtedy ciągi znaków z perspektywy maszyny się nie zgadzają (`"URI" != "URI "`). Rozwiązaniem byłoby usunięcie wszystkich URI, wyczyszczenie pola i ręczne wklejenie/wpisanie adresu jeszcze raz z najwyższą uwagą na spacje na końcu.

**Hipoteza 3: Konflikt wielu URI i przepływów logowania**
Obecnie w GCP wpisane są dwa endpointy dla NextAuth (panel) oraz jeden dla API (FastAPI - YouTube). Google wspiera wiele adresów, ale specyfika wdrożenia i ewentualne konflikty CORS po stronie przeglądarki mogą wpłynąć na przebieg samej weryfikacji tuż przed wyrzuceniem ekranu błędu. Jest to jednak mało prawdopodobne z perspektywy dokumentacji OAuth.

**Hipoteza 4: Niezgodność protokołu schematu (HTTP/HTTPS)**
Jeśli w innych częściach konfiguracji backend generuje link z `http` a do GCP zostało wpisane `https` - ale sprawdzony URL z ekranu błędu to dokładnie i w 100% `https://vse.impresjapr.pl/v1/youtube/oauth/callback`. Zatem to wykluczam.

## 5. Rekomendacja dla Supervisora
Na ten moment ze strony kodowej w `video-seo-engine` zrobiliśmy wszystko perfekcyjnie. Backend prosi o poprawny adres, a w GCP podany jest poprawny adres. 
Sugeruję przekazanie informacji użytkownikowi, by:
a) usunął "URIs 3" i dodał go raz jeszcze upewniając się w 100%, że na końcu ani na początku nie ma spacji.
b) dał serwerom Google co najmniej 30-60 minut na dystrybucję nowych kluczy API na ich krawędziach po ponownym zapisie.
c) spróbował włączyć logowanie w karcie Incognito, by wykluczyć cache przeglądarki dotyczący plików cookie sesji stateflow.

Przekazuję sprawę do konsultacji.