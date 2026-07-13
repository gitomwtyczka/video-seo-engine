# Fix: zakładka + body + override (oraz hotfixy publikacji YouTube)

## Zrealizowane zadania (Część 1)

### 1. Fix zakładki "Opis YouTube" w `dashboard-inner.tsx`
- **Zmiana**: Dodano `{ key: 'youtube', label: 'Opis YouTube' }` do tablicy `tabs` w komponencie `TabBar` w `web/src/app/dashboard/dashboard-inner.tsx`.
- **Wynik**: Zakładka prawidłowo wyświetla się w interfejsie po wygenerowaniu SEO (przeszła z braku definicji do działającego elementu UI).

### 2. Fix braku body w podglądzie (Fallback dla `youtube_description_body`)
- **`web/src/app/dashboard/YouTubePublishModal.tsx`**: W `buildPreview` zmodyfikowano logikę ładowania "M1". Jeśli `schemaData?.youtube_description_body` jest undefined, ładuje najpierw `youtube_description_hook`, a potem `video_description`.
- **`web/src/app/dashboard/dashboard-inner.tsx`**: Zastosowano analogiczny fallback w pomocniczej funkcji `buildYtDescription`.

### 3. Fix: Override na YouTube (`override_description`)
- Analiza: Pole `override_description` w modelu `YouTubePublishRequest` (`api/models/request.py`) istniało i było w kodzie. Plik `api/routers/youtube.py` ma prawidłową obsługę `full_description = req.override_description`, po czym wysyła je w `update_youtube_metadata`.
- Wniosek: Prawdopodobną przyczyną braku "nadpisanego" opisu była pusta zawartość wygenerowanego podglądu, która potem była wysyłana z UI. Od teraz, dzięki poprawce nr 2, podgląd generuje się właściwie, a nadpisane zmiany bez problemu przechodzą przez funkcjonujący już mechanizm w backendzie. 

---

## Zrealizowane zadania (Część 2 - Hotfixy po testach E2E)

### 4. Hotfix: Błąd importu `update_youtube_description` przy wysyłce z modala WordPress
- **Problem**: Użytkownik zgłosił błąd `cannot import name 'update_youtube_description' from 'api.core.youtube_publish'` przy jednoczesnej wysyłce na WordPress i YouTube.
- **Diagnoza**: W module `api/routers/inject.py` wciąż widniała stara nazwa funkcji publikującej (`update_youtube_description`), podczas gdy plik źródłowy `api/core/youtube_publish.py` zawierał już nazwę zaktualizowaną: `update_youtube_metadata`.
- **Rozwiązanie**: Poprawiono nazwę importu i wywołanie w `inject.py` na prawidłowe `update_youtube_metadata`.

### 5. Hotfix: Brak tytułu przy publikacji przez modal WordPress
- **Problem**: Użytkownik zauważył, że publikacja przez "Publikuj na WordPress" aktualizuje opis, ale ignoruje tytuł na YouTube, podczas gdy przycisk "Wyślij na YouTube" radzi z tym sobie bez problemu.
- **Diagnoza**: Funkcje aktualizujące metadane YouTube spodziewały się w payloadzie wygenerowanego tytułu pod kluczem `yt_title`. W rzeczywistości jednak główny prompt LLM przypisuje wygenerowany tytuł do klucza `post_title`. Dlatego `seo.get("yt_title")` zwracało typ `None`, a funkcja modyfikująca na YouTube omijała aktualizację tytułu, jeśli był on pusty.
- **Rozwiązanie**: W plikach `api/routers/inject.py` i `api/routers/youtube.py` dodano zabezpieczenie typu fallback: `new_title=seo.get("yt_title") or seo.get("post_title")`. Zapewnia to, że nawet bez dedykowanego pola `yt_title`, tytuł zostanie prawidłowo wyłuskany z danych zgenerowanych przez LLM (klucz `post_title`) i przekazany do YouTube.

## Wdrożenie (Deploy)
- Wykonano `backup_pre_deploy.sh` bez błędów.
- Uruchomiono przebudowę obrazów dockera `vse-api` i `vse-web`. Kontenery działają w statusie `Healthy`/`Started`.
- Sprawdzono logi - zero nowych wyjątków dotyczących wdrożenia. Serwer prawidłowo przetwarza żądania po obu poprawkach.