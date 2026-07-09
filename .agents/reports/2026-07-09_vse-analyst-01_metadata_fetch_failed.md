# Raport: [vse-analyst-01] Diagnoza błędu metadata_fetch_failed

## CO
Analiza błędu `metadata_fetch_failed` występującego na frontendzie dla wideo `pebmxRlHjh0`. 

## PO CO
Rozwiązanie błędu produkcyjnego uniemożliwiającego użytkownikom planu Agency wygenerowanie SEO dla konkretnych (prywatnych) materiałów YouTube.

## JAK
1. **Badanie logów:** Wysłano agenta-workera do VPS w celu odczytu logów kontenera `vse-api`. Otrzymano informację o braku autoryzacji środowiska dla `run_command` (timeout).
2. **Analiza kodu (`core/fetcher.py`):** Zbadano moduł odpowiedzialny za API YouTube. Błąd na frontendzie jest wyrzucany bezpośrednio przez linię 468 (`return {"video_id": video_id, "error": "metadata_fetch_failed"}`). Ma to miejsce, gdy zwracana struktura `meta` jest pusta.
3. **Potwierdzenie hipotezy:** API YouTube Data v3 (linia 344) traktuje wideo prywatne jako nieistniejące (brak obiektów w tablicy `items`). Powoduje to zapis: `logger.warning("[fetcher] API v3: no items for video_id=%s")` oraz zwrócenie pustego obiektu, bez rzucenia błędu HTTP. Informacja od użytkownika potwierdza, że film `pebmxRlHjh0` był oznaczony jako prywatny.

### Zalecenia naprawcze dla vse-dev-01:
Należy zmodyfikować `core/fetcher.py`, aby w przypadku braku `items` (prywatne/usunięte wideo) zwracał specyficzny błąd `video_is_private_or_not_found`. Front-end powinien obsłużyć ten nowy rodzaj błędu, wyświetlając odpowiedni komunikat użytkownikowi.