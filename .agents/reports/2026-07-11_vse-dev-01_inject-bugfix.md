# Raport z Bugfixu — Brak aktualizacji opisu YouTube podczas wstrzykiwania do WP (Scenariusz A)

## Co zostało zrobione:
1. **Diagnoza problemu:** Użytkownik zgłosił brak aktualizacji opisu filmu na YouTube przy publikacji na portalu ("Publish to Portal").
2. **Przyczyna (Root cause):**
   W `api/routers/inject.py` zaimplementowano sprawdzanie `req.yt_channel_ids`, jednak kod próbował wyciągnąć `video_id` z obiektu `schema_data` (`job_result.get("video_id")`), gdzie po prostu nie istniał.
   Wskutek tego wartość `video_id` była pusta, przez co API ignorowało wykonanie `update_youtube_description` bez żadnego błędu, zwracając jedynie wewnętrznie tekst: `"error": "video_id not found in job result"`.
3. **Rozwiązanie (Fix):**
   Zastosowałem istniejącą funkcję `_extract_video_id` z `api.services.pipeline` do wyciągania ID filmu bezpośrednio z pola `req.video_url` (które jest zawsze przesyłane przez front-end).
4. **Weryfikacja:** 
   Przygotowałem skrypt testowy z użyciem API YouTube by potwierdzić, że OAuth credentials w bazie pozwalają na update (sukces), po czym nałożyłem i zdeployowałem fix na główny serwis API (`vse-api`).

## Commit
- `fix: extract video_id from video_url in inject.py to enable youtube publish [vse-dev]` (vse-api zrestartowane)

Czekam na informację od użytkownika, by ponowił publikację poprzez "Publish to portal".