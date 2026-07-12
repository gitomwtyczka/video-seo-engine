# Raport: Krok 3B v2 — Frontend YouTube Publishing

## Cel
Przywrócenie checkboxów kanałów YouTube w InjectModal oraz finalizacja opcji "Wyślij tylko na YouTube".

## Wykonane prace
1. Stworzono nowy komponent `YouTubePublishModal` do opcji publikacji wyłącznie na YouTube.
   - Wdrożono plik: `web/src/app/dashboard/YouTubePublishModal.tsx`
2. Zaktualizowano `dashboard-inner.tsx` i `InjectModal`:
   - Przywrócono listę kanałów YT jako checkboxy (w środku formularza w `InjectModal`). Checkboxy YT znajdują się bezpośrednio w `InjectModal`.
   - Poprawiono logikę walidacji przycisku "Opublikuj" `disabled` (można wysłać, gdy wybrano portal WP LUB gdy wybrano kanał YT do publikacji równoległej).
   - Wdrożono payload `yt_channel_ids: selectedYtChannelIds` wysyłany do `/v1/inject`.
   - Zaimplementowano łapanie błędów YT z `yt_results` (gdzie status !== "ok") i doklejanie ich do stanu błędu, który wyświetlany jest na dole okna (ze względu na brak globalnej biblioteki Toast).
   - Przycisk "Wyślij na YouTube" (poza modalem Inject) jest ujęty inline w `dashboard-inner.tsx` obok przycisku "Opublikuj na portalu".
3. Wykonano skrypt `backup_pre_deploy.sh` oraz zbudowano z sukcesem kontener `vse-web` na VPS.

## Commity (GitHub)
- `fb53647fb95fd42406ceed0fd54a7d0ea80ee0ce` — feat: YouTubePublishModal component [vse-dev]
- `09a4ce369d1cc0829832a043d9c6f820449106b7` — fix: restore YT checkboxes in InjectModal [vse-dev]

## Deploy
- Skompilowano i zrestartowano `vse-web` na 147.224.162.100.
