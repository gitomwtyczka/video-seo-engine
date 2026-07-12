# YouTube Description Spec — VSE
**Wersja:** 1.0 | **Data:** 2026-07-12 | **Status:** DO ZATWIERDZENIA

## TL;DR
Wdrażamy nową, wielosekcyjną strukturę opisu wideo dla YouTube zoptymalizowaną pod kątem SEO (2024/2025) oraz konwersji użytkowników. Zamiast samego krótkiego "hooka", system będzie generował pełnoprawny, modułowy opis zawierający hook, rozwinięcie z frazami kluczowymi, link do pełnego artykułu jako CTA, rozdziały (timestamps), stałą stopkę per-kanał oraz zoptymalizowane hashtagi.

## Aktualna struktura (stan obecny)
* **youtube_description_hook**: max 200 znaków (2-3 zdania). Posiada pierwszą frazę kluczową. Brak pełnego rozwinięcia (body opisu).
* **youtube_hashtags**: dokładnie 3 hashtagi, generowane przez LLM, dołączane na samym końcu.
* **Rozdziały**: Doklejane w kodzie (`inject.py`), jeśli istnieją w wyniku, ze znacznikiem "⏱️ Rozdziały:".
* **Brak stopki (UI/Backend)**: Brak spersonalizowanej stopki per kanał w publikowanych opisach, pomimo istnienia gotowego pola `footer_text` w modelu `YouTubeChannel`.
* **Złożenie całości (w kodzie)**: Hook + opcjonalny link do posta WP + rozdziały + hashtagi.

## Proponowana struktura (nowa)
[SEKCJA 1: HOOK — widoczne bez klikania "Więcej"]
* **Długość:** max 200 znaków (2-3 zdania).
* **Uzasadnienie:** Pierwsze 1-2 linie są decydujące dla Click-Through Rate (CTR). Jest to jedyny fragment tekstu, który widz widzi na pierwszy rzut oka (Mobile / Desktop). Musi zawierać główną frazę kluczową dla algorytmu wyszukiwania.

[SEKCJA 2: ROZWINIĘCIE I CTA DO ARTYKUŁU — po "Więcej"]
* **Długość:** ok. 150-300 znaków (1 krótki akapit).
* **Elementy:** Krótkie streszczenie (rozwinięcie hooka przez LLM) oraz wyraźne Call To Action zachęcające do przeczytania pełnego artykułu wraz z wygenerowanym linkiem do WP.
* **Uzasadnienie:** Zwiększenie nasycenia semantycznymi frazami (LSI). Badania wykazują, że tzw. mid-description CTA wykazuje wysoką konwersję na użytkownikach już zaangażowanych w dany wątek.

[SEKCJA 3: ROZDZIAŁY/TIMESTAMPS]
* **Format:** `MM:SS Tytuł rozdziału`. Min. długość segmentu 10s. Start zawsze od `00:00`.
* **Ilość:** Minimum 3 (wyliczane dynamicznie, zależnie od długości materiału).
* **Uzasadnienie:** Potężny czynnik SEO pozwalający na indeksowanie fragmentów filmu jako "Key Moments" bezpośrednio w Google Search. Znacząco poprawia retencję oraz user-experience.

[SEKCJA 4: STOPKA I CTA KOŃCOWE]
* **Elementy:** Blok tekstowy zdefiniowany w bazie na poziomie kanału (`YouTubeChannel.footer_text`) np. z linkami do social mediów, główną domeną, linkami wsparcia zbiórek.
* **Uzasadnienie:** Wzmocnienie brandingu mediów i utrzymanie użytkowników w ekosystemie witryny. Realizuje m.in. cele charytatywne/donate dla NGO.

[SEKCJA 5: HASHTAGI]
* **Ilość:** Dokładnie 3.
* **Uzasadnienie:** Umieszczane na samym dole opisu, służą główniej do podstawowej asocjacji wideo. YouTube obniża wartość filmów spamujących tagami.

## Przykład gotowego opisu (prawy.pl)
Czy Donald Tusk i obecny rząd celowo osłabiają państwo polskie? Analizujemy najnowsze decyzje rządu i ich wpływ na suwerenność. Zobacz kluczowe informacje!

W dzisiejszym materiale szczegółowo omawiamy kontrowersyjne posunięcia obecnego obozu władzy. Wraz z naszymi ekspertami dyskutujemy o procesach centralizacji władzy, zmianach w kluczowych urzędach oraz konsekwencjach w polityce zagranicznej, które mogą uderzyć w polską niezależność.
🔗 Przeczytaj pełną analizę na naszym portalu: https://prawy.pl/jakis-artykul-polityczny

⏱️ Rozdziały:
00:00 - Donald Tusk uderza w podstawy państwa polskiego
04:15 - Nowe ustawy a niezależność sądownictwa
08:30 - Relacje z Unią Europejską i uległość rządu
12:45 - Co dalej z suwerennością Polski? Podsumowanie

📺 PRAWY.PL — Niezależne media
🌐 https://prawy.pl
📘 Facebook: https://www.facebook.com/PortalPrawy/
🐦 Twitter/X: https://twitter.com/prawypl
▶️ YouTube: https://www.youtube.com/user/portalprawypl

❤️ WESPRZYJ NASZĄ MISJĘ:
👶 Fundacja S.O.S. Obrony Poczętego Życia
   Nr konta: 32 1140 1010 0000 4777 8600 1001
   KRS: 0000215438

---
#polityka #polska #rząd

## Zmiany w prompcie LLM (generator.py)
Zamiast obecnej instrukcji nr 12 (`youtube_description_hook`), proponujemy wdrożyć nową `youtube_description_body`, która wygeneruje zarówno hook, jak i merytoryczne rozwinięcie:

```text
12. **youtube_description_body** — max 500 znaków. Pełny, angażujący opis wideo dla YouTube.
    ZASADY:
    - Pierwsze 1-2 zdania to HOOK (widoczny bez rozwijania). PIERWSZE zdanie MUSI zawierać główną frazę z focus_keyphrases[0].
    - Kolejne zdania to ROZWINIĘCIE tematu, zawierające warianty fraz kluczowych. Zbudowane tak, aby zainteresować widza szerszym kontekstem.
    - BEZ hashtagów i BEZ linków (zostaną dodane automatycznie w kodzie VSE).
13. **youtube_hashtags** — lista dokładnie 3 hashtagów jako JSON array (np. ["#polityka", "#historia", "#Polska"]). Unikaj znaków specjalnych. Tylko istotne tematycznie.
```

W module `inject.py` złożenie elementów będzie dynamiczne:
`[youtube_description_body] + \n\n🔗 Przeczytaj... [url] + \n\n⏱️ Rozdziały:\n[chapters] + \n\n[channel.footer_text] + \n\n---\n[hashtags]`

## UI — stopka per-user (dashboard front-end)
* **Lokalizacja w UI:** Dashboard → "Moje Kanały YouTube" (sekcja powiązanych kont/kanałów).
* **Konfiguracja na poziom:** Per-kanał (ponieważ instancja modelu to `YouTubeChannel`, a Prawy.pl może np. mieć osobny kanał MediaNarodowe pod tym samym loginem).
* **Komponent:** Wieloliniowe pole tekstowe (Textarea) z etykietą np. "Domyślna stopka opisu wideo (dodawana pod rozdziałami)". Opcjonalnie obok okienko mockujące podgląd opisu na YT na żywo.
* **Limit znaków:** Ograniczenie Textarea do ok. 2000 znaków (aby z hookiem i rozdziałami zmieścić się w twardym limicie YouTube Data API, który wynosi 5000 znaków).
* **UX dodawania:** Standardowy modal lub panel ustawień kanału, z asynchronicznym zapisem (PUT /api/channels/:id). Przy publikacji `inject.py` połączy tekst z wygenerowanym kontentem.

## Otwarte pytania do Supervisora
1. **Delegacja kompozycji:** Czy akceptujemy złożenie całego opisu (body, link, rozdziały, footer) po stronie back-endu (`inject.py`), a nie generatora, co zagwarantuje 100% kontroli i ochronę przed błędami parsowania URLi / Footerów zapytań LLM?
2. **Kolejność Mid-CTA:** Czy link (CTA) do pełnego artykułu WP powinien zawsze znajdować się przed rozdziałami (tak jak w powyższym prompcie) czy bezpośrednio pod nimi?
3. **Draft Mode:** Czy przewidujemy fallback na tekst np. "🔗 Odwiedź nasz portal: [domena]", jeśli link na WordPress się jeszcze nie wygenerował? (wymaga domeny w konfiguracji).
4. **Scope prac:** Czy rozszerzenie front-endu o okno konfiguracji stopki robimy w ramach tego samego sprintu, czy najpierw sam silnik na back-endzie wprowadzający pole w użycie?