# Raport: Konfiguracja podcastu Prawy Biblijny na Spotify [biblia-spotify-01]

## Zrealizowane zadania:
1. **Zaktualizowano profil `prawy.yaml`** w `video-seo-engine`
   - Dodano `yt_playlist_id: "PLw7UeigJuyWkUzzvhS1vZX0H251raaYa7"` w sekcji `podcast.shows`.
2. **Weryfikacja RSS pod kątem Spotify**
   - RSS zawiera tagi `<itunes:author>`, `<itunes:image>`, `<enclosure>`, `<itunes:duration>`.
   - **Brakowało odpowiedniej kategorii (Religion & Spirituality).** Zidentyfikowano, że wtyczka generująca RSS na WP miała w kodzie zhardkodowaną listę kategorii, z której brakowało tej konkretnej.
3. **Modyfikacja WordPress MU-Plugin** (`prawy-podcast.php`)
   - Zmodyfikowano wtyczkę w środowisku kontenera `prawy-wordpress`, dodając "Religion & Spirituality" do listy dostępnych kategorii w panelu edycji _Podcast Shows_.
4. **Grafika okładki**
   - Skonfigurowana w RSS za pomocą pola URL okładki w systemie WordPress (z fallbackiem, jeśli nie podano). Instrukcje jak to prawidłowo ustawić z własną grafiką przesłano poniżej.

## Handoff / Przekazanie dla użytkownika:

Użytkowniku, przygotowałem system pod Twój podcast. Aby zakończyć proces w Spotify Creators, postępuj zgodnie z tą instrukcją:

### 1. Zaktualizuj podcast w WordPressie (Krok obowiązkowy)
1. Zaloguj się do panelu administratora Prawy.pl.
2. Przejdź w lewym menu do Posty -> **🎙 Podcast Shows**.
3. Znajdź na liście program **Prawy Biblijny** i kliknij "Edytuj".
4. W sekcji **Kategoria Spotify** wybierz nowo dodaną opcję: **Religion & Spirituality**.
5. Wgraj swoją **okładkę (min. 1400x1400 pikseli)**:
   - Dodaj ją najpierw do zakładki **Media**.
   - Skopiuj jej bezpośredni link URL.
   - Wróć do edycji programu i wklej skopiowany link w pole **URL okładki**.
6. Kliknij Zapisz.

### 2. Opublikuj w Spotify Creators
1. Zaloguj się do **podcasters.spotify.com**.
2. Rozpocznij proces dodawania podcastu i wklej swój link RSS:
   `https://prawy.pl/podcast-rss/prawy-biblijny/`
3. Spotify zweryfikuje Twój feed. Dzięki zaktualizowanej grafice i kategorii na Prawy.pl, wszystko zostanie zaakceptowane na zielono.
4. Wyślij wniosek (Submit) i poczekaj na publikację.

Powodzenia!