# Raport Handoff: Architektura publikacji YouTube [Aktualizacja: Obiektywne Błędy]

**Data:** 2026-07-12
**Cel:** Analiza obiektywnych nieprawidłowości w działaniu aplikacji (obszar publikacji YT/WP).

## 1. Fakty: Nieprawidłowości w działaniu aplikacji (Stan obecny i historyczny)

### A. Brak obsługi błędu (Cichy Fail) przy publikacji YT
Historycznie, gdy użytkownik zaznaczał kanał YT w oknie publikacji, proces na backendzie kończył się błędem 500 (próba parsowania tekstowego ID `UCoH...` jako UUID w pliku `pipeline.py`).
**Skutek dla użytkownika:** Aplikacja nie publikowała na YT, ale na frontendzie nie pojawiał się absolutnie żaden komunikat o błędzie (Silent Failure). Użytkownik pozostawał w przekonaniu, że proces trwa lub zakończył się poprawnie (w przypadku udanej publikacji WP, ale nie YT).

### B. Regresja UX: Brak wyboru kanału YT w głównym oknie publikacji
W obecnej wersji na branchu `main`, w oknie `InjectModal` brakuje sekcji wyboru kanału YouTube (checkboxy zniknęły). 
**Skutek dla użytkownika:** Rozbicie spójnego procesu. Aby opublikować materiał na WP i YT, użytkownik musi wywołać publikację na WP, poczekać na zakończenie, zamknąć okno, a następnie odszukać osobny przycisk "▶️ Wyślij na YouTube" pod spodem w widoku historii. Jest to wada architektoniczna i regresja względem poprzedniego (oczekiwanego) zachowania aplikacji.

### C. Problem z walidacją przycisku publikacji (Zależność od WP)
Nawet przy przywróceniu wyboru YT wewnątrz okna, istnieje wada logiki w `InjectModal`: przycisk "🚀 Opublikuj na portalu" (i jego stan `disabled`) jest ściśle powiązany z posiadaniem portalu WordPress (`selectedPortalId`). 
**Skutek dla użytkownika:** Jeśli użytkownik chce opublikować materiał *tylko* na YouTube, puste pole wyboru portalu zablokuje przycisk, uniemożliwiając akcję.

## 2. Diagnoza Backendowa (Fakty z kodu)

1. Funkcja `inject_and_publish` z `pipeline.py` **nie wymusza już** UUID dla `yt_channel_id`. Ten konkretny crash został usunięty (`ca39ec9`).
2. API endpoint `/v1/inject` wywołuje kod: `if req.yt_channel_ids: update_youtube_description(...)`. Oznacza to, że pojedynczy strzał HTTP POST z frontendu jest w stanie obsłużyć obie publikacje (WP + YT) równolegle, o ile frontend wyśle oba parametry.

## 3. Rekomendowany Sposób Zaradzenia (Dla kolejnej sesji)

1. **Przywrócenie UI w `InjectModal`:** Odbudowanie mapowania `ytChannels` do postaci checkboxów w oknie publikacji.
2. **Naprawa walidacji:** Odpięcie twardej blokady przycisku w `InjectModal` tak, aby przycisk był aktywny jeśli `selectedPortalId != ""` LUB `selectedYtChannelIds.length > 0`.
3. **Wdrożenie jawnych komunikatów błędu (Toast):** Frontend musi sprawdzać w odpowiedzi z `/v1/inject` pole `yt_channels` i statusy publikacji dla YouTube. Jeśli wystąpi błąd specyficzny dla YT, aplikacja musi wyświetlić odpowiedni toast (np. "Błąd publikacji YT: ..."), zapobiegając cichym awariom w przyszłości.