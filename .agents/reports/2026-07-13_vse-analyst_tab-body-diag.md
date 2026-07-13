# Diagnostyka: zakładka + body

## Q1: Zakładka w dashboard-inner.tsx
- Czy `TabKey` zawiera `'youtube'`? **TAK** (linia 357).
- Czy tablica `tabs` w `TabBar` zawiera `{ key: 'youtube', label: 'Opis YouTube' }`? **NIE** (linia 1217). To jest przyczyna braku zakładki.
- Czy istnieje blok renderowania dla `activeTab === 'youtube'`? **TAK** (linia 7091).
- Czy `ytDescription` i `setYtDescription` są zadeklarowane w `DashboardInner`? **TAK** (linia 4727).
- Czy `useEffect` wypełniający `ytDescription` z `result.raw` istnieje? **TAK** (linia 5003).

## Q2: Pola YT w response /v1/generate
Backend (`api/services/generator.py`) definiuje i zwraca z AI WYŁĄCZNIE:
- `youtube_description_hook`
- `youtube_hashtags`
- `video_description`

BRAKUJE deklaracji w prompcie i modelu dla: `youtube_description_body`, `youtube_mid_cta`, `youtube_credits`. AI ich po prostu nie generuje, dlatego `schemaData` na froncie nie ma tych wartości.

## Q3: buildPreview w YouTubePublishModal
`buildPreview` w `web/src/app/dashboard/YouTubePublishModal.tsx` próbuje odczytać:
- `schemaData?.youtube_description_body`
- `schemaData?.youtube_mid_cta`
- `wpUrl`
- `schemaData?.chapters`
- `schemaData?.youtube_credits`
- `schemaData?.youtube_hashtags`

Tak wygenerowany tekst JEST poprawnie wrzucany do state'u `previewText` i wyświetlany w `<textarea>` (linie 220-224), gdzie można go edytować. Ale ponieważ 3 z tych pól są `undefined` w obiekcie z backendu, podgląd zawiera tylko puste linki/stopkę.

## Q4: override_description w payload
**TAK**, frontend w funkcji `publish()` (linia 146) dodaje `override_description` do payloadu:
`bodyPayload.override_description = previewText`
Wartość pochodzi z okna `<textarea>` (stan `previewText`).

## Root cause per problem
- **Brak zakładki**: Tablica zakładek `tabs` w `TabBar` (`dashboard-inner.tsx`) nie ma zadeklarowanego obiektu `{ key: 'youtube', label: 'Opis YouTube' }`.
- **Brak body w podglądzie**: Prompt do AI w `api/services/generator.py` nie wymaga od modelu generowania pól `youtube_description_body`, `youtube_mid_cta`, `youtube_credits` - dlatego przychodzą puste. Generuje zamiast tego stary format (`youtube_description_hook` oraz `video_description`).
- **YT się nie aktualizuje**: Opcja `override_description` jest wysyłana do backendu (`POST /v1/youtube/publish-description`), ale najpewniej sam endpoint backendowy albo funkcja publikacji nie mapuje tego prawidłowo na żądanie do YouTube API.

## Minimalne zmiany do naprawy
1. **`web/src/app/dashboard/dashboard-inner.tsx`**: Dodać obiekt dla `'youtube'` do tablicy `tabs`.
2. **`api/services/generator.py`**: Przebudować prompt dla modelu AI, aby zwracał podzieloną strukturę wideo: `youtube_description_body`, `youtube_mid_cta`, `youtube_credits` (zamiast `video_description`).
3. **`api/routers/youtube.py` / `core/injector.py`**: Zweryfikować, w jaki sposób backend obsługuje klucz `override_description` (bo na razie wydaje się go gubić, mimo że frontend go wysyła).