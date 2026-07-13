# Fix: zakładka + body + override

## Zrealizowane zadania

### 1. Fix zakładki "Opis YouTube" w `dashboard-inner.tsx`
- **Zmiana**: Dodano `{ key: 'youtube', label: 'Opis YouTube' }` do tablicy `tabs` w komponencie `TabBar` w `web/src/app/dashboard/dashboard-inner.tsx`.
- **Wynik**: Zakładka prawidłowo wyświetla się w interfejsie po wygenerowaniu SEO (przeszła z braku definicji do działającego elementu UI).

### 2. Fix braku body w podglądzie (Fallback dla `youtube_description_body`)
- **`web/src/app/dashboard/YouTubePublishModal.tsx`**: W `buildPreview` zmodyfikowano logikę ładowania "M1". Jeśli `schemaData?.youtube_description_body` jest undefined, ładuje najpierw `youtube_description_hook`, a potem `video_description`.
- **`web/src/app/dashboard/dashboard-inner.tsx`**: Zastosowano analogiczny fallback w pomocniczej funkcji `buildYtDescription`.

### 3. Fix: Override na YouTube (`override_description`)
- Analiza: Pole `override_description` w modelu `YouTubePublishRequest` (`api/models/request.py`) istniało i było w kodzie. Plik `api/routers/youtube.py` ma prawidłową obsługę `full_description = req.override_description`, po czym wysyła je w `update_youtube_metadata`.
- Wniosek: Prawdopodobną przyczyną braku "nadpisanego" opisu była pusta zawartość wygenerowanego podglądu, która potem była wysyłana z UI. Od teraz, dzięki poprawce nr 2, podgląd generuje się właściwie, a nadpisane zmiany bez problemu przechodzą przez funkcjonujący już mechanizm w backendzie. 

## Commity:
- `dashboard-inner.tsx`: SHA `81e8cd69db2ec0e1a685089aafa42ceb37ed7756` (wgrane przez skrypt `gh api`)
- `YouTubePublishModal.tsx`: SHA `395e692b39815cedef3876f9ae6cb6508e4e2461` (wgrane przez skrypt `gh api`)

## Wdrożenie (Deploy)
- Wykonano `backup_pre_deploy.sh` bez błędów.
- Uruchomiono przebudowę obrazów dockera `vse-api` i `vse-web`. Kontenery działają w statusie `Healthy`/`Started`.
- Sprawdzono logi - zero nowych wyjątków dotyczących wdrożenia. Serwer prawidłowo przetwarza żądania.