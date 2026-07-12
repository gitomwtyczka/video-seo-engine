# Raport: vse-fix2 — plan przeniesienia budowania opisu na backend
**Model:** Gemini Pro | **Typ:** IMPLEMENTACJA
**Data:** 2026-07-12

## Cel
Naprawa braku sekcji (M2-M8) w opisie YouTube publikowanym przez przycisk "Wyślij na YouTube".

## Rekonesans & Plan
1. **Model (api/models/request.py):** YouTubePublishRequest zostanie zaktualizowany, dodając schema_data: dict oraz usuwając stare description: str.
2. **Backend (api/routers/youtube.py):** Endpoint /publish-description zamiast przyjmować z góry zbudowane 
eq.description, zbuduje pełny opis dla każdego kanału używając uild_yt_description (zaimportowane z pi.routers.inject). Będzie iterował po channel_ids, ponieważ dla każdego kanału pobierany jest z bazy własny ooter_text.
3. **Frontend (web/src/app/dashboard/dashboard-inner.tsx):** Zostanie zmieniony tak, by używać pola schema_data: result.raw?.seo ?? {} zamiast wysyłać pre-built description. Zmienna wpUrl zostanie przekazana jako wp_article_url.
4. **Kwestia Tytułu:** W publish-description zauważyłem, że aktualnie wywoływane update_youtube_description aktualizuje **tylko opis** (snippet["description"] = new_description). Tytuł nie jest w ogóle aktualizowany w tej ścieżce! Zostanie to zaraportowane jako TODO.

Przystępuję do modyfikacji.
