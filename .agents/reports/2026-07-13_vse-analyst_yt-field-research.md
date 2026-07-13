# Research: pole opisu YT

## Q1: Nazwa pola w schemaData
W interfejsie podglądu "Format YouTube (do opisu wideo)", treść kopiowana przez przycisk "Wklej do opisu YT" zasilana jest **bezpośrednio z listy sformatowanych rozdziałów (`chapters`)**, wyodrębnianych za pomocą funkcji `extractChapters(schemaData)`.
Odpowiednia zmienna w komponencie React to `chapters`, a pole źródłowe z modelu to `schemaData.chapters` lub ew. `schemaData.video.chapters`.
Z kolei pełny opis YouTube (np. ten z hookiem, CTA i hashtagami) nie znajduje się w jednym polu lecz jest kompozycją z wielu: `youtube_description_hook` / `youtube_description`, `youtube_description_body`, `youtube_mid_cta`, `youtube_credits`, `youtube_hashtags`.

## Q2: Format youtube_hashtags
Format to `array<string>`.
Przykład ustrukturyzowania w `api/routers/inject.py` to przetwarzanie każdego elementu w pętli dla pewności dodania hasza: `tags = " ".join(t if t.startswith("#") else f"#{t}" for t in hashtags)`.
Przykładowy element może mieć postać z haszem (`"#SEO"`) lub bez (`"SEO"`).

## Q3: build_yt_description() — kolejność modułów
Kolejność łączonych modułów:
1. `body` (M1)
2. `wp_url` — Link do artykułu (M2)
3. `mid_cta` (M3)
4. `chapters` — Timestamps (M4)
5. `credits` (M5)
6. `footer_text` — Stopka per-kanał (M7)
7. `hashtags` (M8)

*Separator:* Poszczególne moduły oddzielane są najczęściej dwoma znakami nowej linii (`\n\n`), poza pierwszym modułem `body`, po którym następują dwa znaki nowej linii.

*Obsługa override w body:* **NIE.** Funkcja `build_yt_description()` nie przyjmuje, ani nie obsługuje parametru typu `override_description`. Model Payloadu backendowego dla tego kontrolera (`InjectRequest` w `api/models/request.py`) również w tej chwili nie zawiera w ogóle parametru z nadpisaniem opisu YT (takiego jak np. wysyłane przez frontend `yt_override_description`).

## Rekomendacja dla następnego agenta
Backend obecnie bezpowrotnie "traci" (ignoruje) nadesłane z UI nadpisanie opisu, polegając w 100% na wewnętrznym, "twardym" formacie składania go w `build_yt_description()`. 

**Co trzeba zmienić (w API / Backendzie):**
1. Dodać pole `yt_override_description: Optional[str] = None` w klasie `InjectRequest` w pliku `api/models/request.py`.
2. Zaktualizować logikę w `api/routers/inject.py` w okolicach miejsca wywołania `build_yt_description()`. Jeśli `req.yt_override_description` będzie podane (not None/empty), użyć jego wartości jako pełnego i gotowego opisu YT zamiast wywoływać `build_yt_description(...)` z częściowych payloadów.
