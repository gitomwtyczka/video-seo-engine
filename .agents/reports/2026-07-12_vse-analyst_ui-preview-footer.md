# Raport Analizy UI: Podgląd opisu YT & footer_text

**Model: Gemini Pro** | **Typ: ANALIZA** | **Data: 2026-07-12**
**Agent:** vse-analyst

Zgodnie z poleceniem przeprowadzono analizę kodu repozytorium (branch `main`), weryfikując obecność i architekturę komponentów UI pod kątem publikacji na YouTube i stopki kanału. 

Oto szczegółowe odpowiedzi na zadane pytania:

### 1. Podgląd opisu YT
**Czy istnieje jakikolwiek komponent w kodzie?**
Obecnie w kodzie na branchu `main` **nie istnieje żaden komponent podglądu opisu dla YouTube (brak `textarea` itp.)**.
- Plik `YouTubePublishModal.tsx` zawiera jedynie listę połączonych kanałów (z checkboxami) oraz przycisk "Wyślij na YouTube". Cały `schemaData` jest natychmiast wysyłany do endpointu `/v1/youtube/publish-description`. Nie ma możliwości podglądu ani jego edycji.
- Istnieje też drugi modal w `dashboard-inner.tsx` (tzw. `InjectModal`), który ma sekcję `{/* Article preview */}`, jednak pokazuje tam tylko `post_title` i `meta_description` na potrzeby publikacji WordPress, a nie zawartość dla YT.

### 2. Stary vs nowy UX
**Ile komponentów modalnych dla YT publish istnieje? Który ma pierwszeństwo i dlaczego?**
W `dashboard-inner.tsx` istnieją **dwa odrębne modale** potrafiące obsłużyć publikację na YT:
1. `YouTubePublishModal` – podpięty pod zakładkę "YouTube" w głównym oknie (sterowany stanem `ytModalOpen`).
2. `InjectModal` – główny modal publikacyjny dla planów Pro/Agency, otwierany przyciskiem "Opublikuj na WordPress" (`showInjectModal`). Wewnątrz niego znajduje się sekcja z checkboxami kanałów (obsługiwana przez `selectedYtChannelIds`), a żądanie do YouTube jest wplatane bezpośrednio w endpoint `/v1/inject` (jako element `body.yt_channel_ids`).

**Pierwszeństwo:** Z punktu widzenia UX, jeśli user jest w trybie "Pro/Agency" i klika duży przycisk publikacji na WP, otwiera się `InjectModal`. Jeśli poprzedni agenci modyfikowali `YouTubePublishModal` pod kątem podglądu opisu, to użytkownik korzystający z globalnego `InjectModal` nigdy tych zmian by nie zobaczył (lub na odwrót). To powoduje rozdźwięk i uczucie "zasłaniania".

### 3. footer_text
**Czy pole footer_text jest dostępne w UI? Gdzie powinno być dodane?**
- Pole `footer_text` **nie jest dostępne** nigdzie w interfejsie.
- W `web/src/app/ustawienia/page.tsx` w sekcji `Kanały YouTube` (linie ok. 680-712) renderowana jest tylko nazwa kanału (`ch.channel_title`) oraz ID kanału (`ch.channel_id`).
- Backend (endpointy w `youtube.py`) posiada w pełni funkcjonującą logikę do obsługi tego pola, w tym `PUT /v1/youtube/channels/{id}` obsługujący zapis.
- **Gdzie powinno być dodane:** Właśnie w pliku `web/src/app/ustawienia/page.tsx`, w mapowaniu listy połączonych kanałów (wewnątrz `<div key={ch.channel_id}>`), należy dodać edytowalne pole `<textarea>` dla `footer_text` z przyciskiem "Zapisz", triggerujące endpoint PUT.

### 4. Co blokuje (Hipoteza)
Hipoteza o tym, że podgląd i stopka "nie wchodzą na front", opiera się na dwóch prawdopodobnych czynnikach:
1. **Rozdwojenie logiki YT w dwóch modalach:** Dodawano `textarea` do jednego modala (np. dedykowanego do zakładki YT), a użytkownik podczas normalnego procesu używa `InjectModal` (publikacja całości WP + YT za jednym kliknięciem).
2. **Kwestie deploymentu:** Utrata niezacommitowanych / niepoprawnie wdrożonych zmian z powodu wymuszonego backupu lokalnego (`git pull origin main` nadpisało ewentualne błędne próby wdrażania), albo frontend (kontener Next.js) po prostu nie został przebudowany po zaktualizowaniu kodu przez agenta (`docker compose build vse-web`). Zmiany mogły nigdy nie wejść do brancha `main`.

### 5. Minimalna zmiana
Aby funkcjonalności w pełni działały i były widoczne:
- **Plik 1:** `web/src/app/dashboard/YouTubePublishModal.tsx` – Dodać rozszerzone pole `<textarea>` wyświetlające tekst opisu YouTube, a jego zawartość przechwytywać w stanie (np. `const [previewText, setPreviewText] = useState(...)`). Tą nadpisaną wartość przekazać w do żądania POST `/v1/youtube/publish-description`. Podobnie w `InjectModal`, jeśli również ma pokazywać podgląd YT.
- **Plik 2:** `web/src/app/ustawienia/page.tsx` – Dla każdej iteracji tablicy kanałów w sekcji YouTube renderować `<textarea defaultValue={ch.footer_text} ... />` oraz wywoływać `fetch("/v1/youtube/channels/" + ch.channel_id, { method: "PUT", body: JSON.stringify({ footer_text: val }) })`.
