# Raport diagnostyczny: Pusty opis na YouTube po publikacji

**Callsign:** `vse-diag3`
**Data:** 2026-07-12

## 1. Co pokazują logi
Ponieważ przed chwilą wdrożono zmiany (API restart o 20:09 UTC), logi z momentu kliknięcia przycisku przez użytkownika przepadły. Aktualne wywołanie `docker logs vse-api` pokazuje jedynie restart oraz requesty `/v1/jobs/pending`. Jednak problem jest ewidentny w kodzie frontendu.

## 2. Czy `schema_data` dociera do backendu niepuste?
Nie. Do endpointu `POST /v1/youtube/publish-description` dociera PUSTY obiekt `{}` jako `schema_data`.

## 3. Gdzie konkretnie powstaje pusty string?
Pusty string wędruje przez następujący łańcuch:
- W `api/routers/youtube.py` (`POST /publish-description`) pobierany jest `seo = req.schema_data`, który wynosi `{}`.
- Funkcja `build_yt_description()` jest wywoływana z parametrami wyciągniętymi przez `.get()`. Ponieważ obiekt jest pusty, wszystko (w tym `body`) przyjmuje wartość domyślną `""` (lub `None`).
- W rezultacie funkcja skleja same pustki, ostatecznie zwracając pusty łańcuch znaków.
- Taki `full_description == ""` jest przesyłany bezpośrednio do Google API, co po prostu kasuje opis na YouTubie.

## 4. Hipoteza Root Cause
Przyczyna leży wyłącznie we frontendzie — w pliku `web/src/app/dashboard/dashboard-inner.tsx`.

Gdy użytkownik klika przycisk publikacji z modala `InjectModal` (publikacja na WP), komponent otrzymuje poprawne dane:
```tsx
// linia ~3632
<InjectModal schemaData={result.raw} ... />
```
Ponieważ `result.raw` to cały obiekt typu `SchemaData`.

Natomiast, gdy użytkownik klika dedykowany przycisk na zakładce YT, który otwiera `YouTubePublishModal`, dane przekazywane są z błędem:
```tsx
// linia ~3671
<YouTubePublishModal schemaData={result.raw?.seo ?? {}} ... />
```
Obiekt `result.raw` **nie ma klucza `.seo`** (był on częścią odpowiedzi HTTP `/v1/generate`, ale stan Reacta zapisuje tylko jego zawartość, czyli same dane do `result.raw`). Ponieważ `result.raw.seo` jest `undefined`, wpada w fallback `?? {}`.

**Rozwiązanie:** Należy we frontendzie w `web/src/app/dashboard/dashboard-inner.tsx` zmienić to wywołanie na:
```tsx
schemaData={result.raw ?? {}}
```