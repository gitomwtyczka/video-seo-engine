# Raport z implementacji: Aktualizacja tytułu wideo oraz stopki per-kanał na YouTube

**Callsign:** `vse-dev-02`
**Data:** 2026-07-12

## CO
1. Dodano obsługę aktualizacji tytułu wideo na YouTube z poziomu PressAI Dashboard.
2. Zaimplementowano endpoint do aktualizacji konfiguracji per-kanał (stopka YT).

## PO CO
1. **Tytuł:** Ażeby publikacja na YouTube z dashboardu (Scenariusz A) była kompletna i nadpisywała oryginalny (często techniczny lub roboczy) tytuł nowo wygenerowanym tytułem zoptymalizowanym pod kątem SEO.
2. **Stopka:** Ażeby użytkownicy mogli zdefiniować własny tekst doklejany na dole opisu (np. zaproszenie do subskrypcji, linki do patronite/newslettera) per kanał YT.

## JAK
1. `api/core/youtube_publish.py`:
   - Zmiana `update_youtube_description` na `update_youtube_metadata`.
   - Dodanie wsparcia argumentu `new_title` i aktualizacji pola `title` w `snippet` Google API.
2. `api/routers/inject.py` oraz `api/routers/youtube.py`:
   - Przekazywanie nowo wygenerowanego tytułu z `schema_data["yt_title"]` jako parametru `new_title` przy publikacji opisu na YT (zarówno przy samodzielnym pushu do YT jak i przez integrację `inject_endpoint`).
3. `api/models/request.py`:
   - Dodanie pydantic modelu `YouTubeChannelUpdate` zawierającego pole `footer_text`.
4. `api/routers/youtube.py` (Zarządzanie stopką):
   - Zmiana endpointu `GET /channels` tak, aby zwracał pole `footer_text`.
   - Stworzenie endpointu `PUT /channels/{channel_id}` używającego `YouTubeChannelUpdate`, aby frontend mógł zapisać ustawioną przez użytkownika stopkę.
5. Wykonano deploy backendu na środowisko VPS (`oracle-crimson`). Zastosowano mandatory pre-deploy backup.

## Następne kroki (Handoff dla frontendu)
W następnym kroku agent obsługujący frontend musi zaimplementować:
1. UI do dodawania stopki do kanałów na podstawie `footer_text` w `/v1/youtube/channels`.
2. Dodanie zapytania `PUT` wysyłającego zaktualizowany `footer_text` w obiekcie `YouTubeChannelUpdate`.
