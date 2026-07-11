# Raport: Naprawa publikacji na YouTube [vse-dev-01]

**Data:** 2026-07-11
**Dotyczy:** Naprawa błędu publikacji na YouTube z historii (Application error / brak przycisku)

## 1. Analiza problemu
Użytkownik zgłosił dwa problemy przy próbie publikacji wygenerowanych treści z widoku historii:
1. Brak przycisku Wyślij na YT w modalu InjectModal.
2. Kliknięcie Opublikuj z zaznaczonym kanałem YT kończyło się błędem publikacji YT bez komunikatu (lub błędem na konsoli).

**Przyczyny:**
1. Nowa architektura przeniosła obsługę YouTube do dedykowanego modala (YouTubePublishModal), ale stary kod w InjectModal nadal renderował listę kanałów (co było mylące, gdyż przycisk wysłania na YT zniknął z tego modala).
2. Żądanie wysłane z InjectModal trafiało do /v1/inject, a następnie do pipeline.py, gdzie funkcja inject_and_publish próbowała parsować channel_id (np. UCoH...) za pomocą uuid.UUID(yt_channel_id), co powodowało rzucenie wyjątku ValueError przerywającym publikację na YouTube.

## 2. Rozwiązanie (Wdrożone i zdeployowane)

**Backend:**
- Usunięto zdezaktualizowaną logikę youtube_publish i konwersję UUID z api/services/pipeline.py. 
- Upewniono się, że dedykowany endpoint w api/routers/youtube.py oraz api/core/youtube_publish.py używają poprawnego typu string dla channel_id.

**Frontend:**
- Z web/src/app/dashboard/dashboard-inner.tsx usunięto zduplikowane, przestarzałe kontrolki YouTube (checkbox'y kanałów) z komponentu InjectModal.
- Modal InjectModal służy teraz **wyłącznie** do publikacji na WordPress, tak jak zakładała nowa koncepcja 2-ścieżkowa.
- Publikacja na YouTube odbywa się teraz **wyłącznie** poprzez przycisk ▶️ Wyślij na YouTube (widoczny w sekcji wyników obok przycisku 🚀 Opublikuj na WordPress), który otwiera dedykowany YouTubePublishModal.

## 3. Stan obecny (Post-Deploy)
Zdeployowano poprawkę (commit: ca39ec9). Użytkownik powinien teraz:
1. Kliknąć ▶️ Wyślij na YouTube w głównym widoku wygenerowanych wyników.
2. Zostanie otwarty dedykowany modal YouTube z poprawnym podpięciem tokenu z sesji i obsługą endpointu /v1/youtube/publish-description.
