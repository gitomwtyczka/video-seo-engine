# Raport Handoff: Architektura publikacji YouTube [vse-dev-01]

**Data:** 2026-07-12
**Cel:** Analiza i propozycja naprawy flow publikacji na YouTube z historii.

## 1. Stan faktyczny i popełnione błędy

**Błąd pierwotny:** 
Użytkownik zgłosił błąd przy publikacji na YouTube z okna publikacji (historii). Przyczyną był błąd w kodzie `api/services/pipeline.py`, gdzie funkcja próbowała parsować tekstowe ID kanału YouTube (`UCoH...`) jako `uuid.UUID`. Skutkowało to wewnętrznym błędem 500, który nie był komunikowany na frontendzie (cichy fail).

**Mój błąd operacyjny (błędne założenie):**
Widząc, że w projekcie istnieje osobny komponent `YouTubePublishModal` oraz przycisk `▶️ Wyślij na YouTube` w głównym widoku dashboardu, błędnie założyłem, że intencją architektoniczną jest *całkowite oddzielenie* publikacji WordPress od YouTube. W ramach "naprawy" usunąłem sekcję wyboru kanałów YouTube z `InjectModal`. 
Jak słusznie zauważył użytkownik, zepsuło to jego naturalny workflow – oczekiwał on możliwości jednoczesnej publikacji na WP i YT bezpośrednio z okna `InjectModal`, gdzie "wcześniej były kanały które są podłączone z checkboxami".

## 2. Diagnoza backendu (Dobra wiadomość)

Mimo błędnej decyzji o usunięciu UI na frontendzie, **backend został już poprawnie naprawiony w commicie `ca39ec9`**:
1. Usunąłem problematyczne rzutowanie do UUID w `pipeline.py`.
2. Plik `api/routers/inject.py` posiada już zaimplementowaną i działającą logikę, która przyjmuje listę `yt_channel_ids` bezpośrednio z requestu `/v1/inject` i poprawnie wywołuje `update_youtube_description`.

Oznacza to, że backend jest teraz w 100% gotowy do jednoczesnej publikacji (WordPress + YouTube), bez błędu z UUID.

## 3. Plan naprawczy (Sposób zaradzenia)

Aby przywrócić oczekiwaną funkcjonalność i zachować stabilność, następny agent / Supervisor powinien zatwierdzić poniższe kroki:

1. **Frontend (Przywrócenie UI):** W pliku `web/src/app/dashboard/dashboard-inner.tsx` należy przywrócić usunięty kod renderujący listę checkboxów dla kanałów YouTube wewnątrz `InjectModal` (sekcja `ytChannels.map`).
2. **Frontend (Logika przycisku):** Upewnić się, że główny przycisk "🚀 Opublikuj na portalu" w `InjectModal` aktywuje się poprawnie nie tylko wtedy, gdy wybrano portal WP, ale również (lub tylko) gdy zaznaczono kanał YouTube.
3. **Frontend (Stan):** Upewnić się, że zaznaczone `selectedYtChannelIds` są z powrotem przekazywane w payloadzie POST do `/v1/inject`.

Zaraz po przywróceniu tych elementów na frontendzie, cały proces publikacji (WP + YT) z okna historii będzie w pełni funkcjonalny. Zostawiam ten dokument do decyzji Supervisora.
