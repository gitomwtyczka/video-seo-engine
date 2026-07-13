# Diagnostyka: footer_text

## Q1: GET zwraca footer_text?
TAK. Brak zdefiniowanego na zewnątrz modelu Pydantic (endpoint zwraca bezpośrednio zbudowaną w kodzie listę słowników). Linia kodu w `api/routers/youtube.py` to:
`return [{"id": str(ch.id), "channel_id": ch.youtube_channel_id, "channel_title": ch.title, "footer_text": ch.footer_text} for ch in channels]`

## Q2: PUT zapisuje footer_text do DB?
TAK. Model requestu to `YouTubeChannelUpdate`.
W funkcji `update_channel` (plik `api/routers/youtube.py`) znajduje się modyfikacja: `channel.footer_text = req.footer_text`, a następnie `await db.commit()`. Backend poprawnie zaktualizuje dane w bazie, jeśli tylko znajdzie rekord w tabeli przy użyciu wewnętrznego klucza (UUID z bazy w kodzie oznaczony jako `YouTubeChannel.id`).

## Q3: Frontend — poprawna nazwa pola?
Nazwa pola to `channel.footer_text`. Komponent `FooterTextEditor` (w `web/src/app/ustawienia/page.tsx`) jest kontrolowany (controlled input – wykorzystuje `value={text}`). Payload to poprawny JSON postaci: `{"footer_text": text}`.

## Q4: build_yt_description — skąd footer_text?
Źródłem `footer_text` w `api/routers/inject.py` jest asynchroniczne pobranie danych z bazy dla użytego kanału za pomocą wewnętrznej funkcji `_get_channel()` w `inject_endpoint()`. Kod działa prawidłowo — jeśli stopka byłaby w DB, trafiłaby do opisu. Została tu zapewniona ciągłość danych, nie ma "luki" w logice poza tym, że baza zwraca `null`/pusty ciąg, bo zapis nie zadziałał.

## Root cause (hipoteza)
Główną przyczyną całego zachowania jest to, że frontend wysyła żądanie do złego adresu endpointu (złe ID). 
W pliku `web/src/app/ustawienia/page.tsx` (komponent `FooterTextEditor`), wywołanie zapisu wygląda następująco:
`fetch(`${apiUrl}/v1/youtube/channels/${channel.channel_id}`...)`
Frontend używa zmiennej `channel.channel_id`, co odpowiada identyfikatorowi YouTube (ciąg zaczynający się np. od `UC...`). 
Tymczasem backend w `update_channel` porównuje przekazany argument z wewnętrznym `YouTubeChannel.id` (czyli kluczem głównym bazy w formie UUID). W rezultacie zapytanie ORM nie znajduje rekordu i wyrzuca błąd 404 (Channel not found).

Co więcej, frontendowy `fetch` nie sprawdza `res.ok`, przez co po każdym kliknięciu mimo błędu 404 wyświetla komunikat "✔ Zapisano". Przy odświeżeniu strony frontend ponownie robi GET i otrzymuje stan faktyczny z bazy (brak zapisanego rekordu).

## Minimalne zmiany do naprawy
1. **W pliku `web/src/app/ustawienia/page.tsx`** w komponencie `FooterTextEditor`:
   - Należy zmienić URL używany do aktualizacji kanału. Zamiast `${channel.channel_id}` użyć wewnętrznego `${channel.id}`. Właściwa linia kodu:
     `await fetch(`${apiUrl}/v1/youtube/channels/${channel.id}`, {`
   - Dodać walidację `res.ok` (jeśli odpowiedź to błąd — należy zatrzymać operację, zgłosić błąd i nie wyświetlać zielonego komunikatu sukcesu zapisu).