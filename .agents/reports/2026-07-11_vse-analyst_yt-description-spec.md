# Raport Analityczny: Specyfikacja YouTube Description 2026
**Zlecenie:** Supervisor-04
**Data:** 2026-07-11

## 1. Gdzie w kodzie generowany jest obecny opis
Obecny opis generowany jest w pliku `core/generator.py`. Instrukcja dla LLM znajduje się w głównym prompcie (zmienna `prompt`):
- Linia ~431 (funkcja `generate_seo_v4`): `12. **youtube_description** — max 500 zn, z hashtagami.`
- Linia ~618 (funkcja `generate_schema_without_transcript`): `9. **youtube_description** — max 400 zn, z hashtagami.`

Rozdziały (chapters) są zwracane przez model LLM jako osobna struktura JSON (`"chapters": [{"label": "...", "anchor_text": "..."}]`), a dokładne timestampy są mapowane później w Pythonie na podstawie dopasowania fuzzy match do oryginalnego pliku VTT.

## 2. Co obecny generator produkuje
Obecnie Claude / Gemini zwraca pojedynczy, ciągły blok tekstu dla pola `youtube_description`, który wygląda najczęściej tak:
*"W dzisiejszym materiale analizujemy najnowsze zmiany w... [treść]. Dowiedz się, co to oznacza dla przyszłości. #polityka #wiadomosci #Polska"*

Nie ma tu rozdziałów, linków do pełnego artykułu WP ani stopki kanału. Jest to zwykły akapit tekstu wygenerowany ad-hoc z 2-3 hashtagami na końcu.

## 3. Co dodać / zmienić (diff koncepcyjny)
Zgodnie z najlepszymi praktykami SEO na rok 2026:
- **Hook (Pierwsze ~150 znaków):** Część widoczna bez klikania "Więcej". Musi zawierać główną frazę kluczową (najlepiej w 1-2 zdaniu) i jasno określać korzyść dla widza.
- **Czytelność i nawigacja:** Rozdziały (timestamps) są w 2026 krytyczne, budują tzw. "information gain" i wydłużają sesję.
- **Konwersja:** Bezpośredni, wyraźny link do pełnego artykułu w portalu WP tuż pod pierwszym akapitem.
- **Hashtagi:** Hashtagi stały się czysto kategoryzacyjne - optymalnie 3 sztuki umieszczone na samym dole opisu.

**Zmiana koncepcyjna:**
- W `generate.py` redefiniujemy rolę LLM. Zamiast generować cały opis, LLM powinien wygenerować TYLKO angażujący "Hook" na 2-3 zdania i ewentualnie 3 hashtagi w osobnej zmiennej.
- Resztę opisu (rozdziały z czasem, link WP, stopkę) powinno doklejać API backendu, gdy już skompletuje wszystkie potrzebne dane po publikacji w WordPressie.

## 4. Finalny zatwierdzony formatem szablon

Poniższy format prezentuje ostateczny kształt opisu (składany w post-processingu) wraz z instrukcją pod model Claude dla zmiennych.

**Szablon ostatecznego tekstu (do wklejenia na YouTube):**
```text
{seo_intro_2_3_zdania}

🔗 Pełny artykuł: {wp_article_url}

⏱️ Rozdziały:
{rozdzialy_timestamps}

{stopka_uzytkownika}
---
{hashtagi_max_3}
```

**Proponowany nowy fragment do promptu Claude (`core/generator.py`):**
Zamiast obecnego `youtube_description`, wstawiamy instrukcję na wygenerowanie samego wstępu:
```text
12. **youtube_description_hook** — max 200 znaków. Angażujący wstęp 2-3 zdania. PIERWSZE zdanie MUSI zawierać główną frazę z focus_keyphrases[0]. To jest "hook" widoczny pod wideo bez klikania. BEZ hashtagów.
13. **youtube_hashtags** — lista 3 najtrafniejszych hashtagów, np. ["#tag1", "#tag2", "#tag3"].
```

## 5. Rekomendacja
**Zdecydowanie rekomenduję zmieniać i składać ostateczny format opisu w nowym pliku `core/youtube_publish.py` (lub w module `core/injector.py` / `yt_admin.py`).**

**Dlaczego nie powinno się tego robić w samym `generate.py` (w modelu LLM):**
1. **Brak wiedzy u Claude:** LLM na etapie `generate.py` absolutnie nie wie, jaki będzie `wp_article_url` — artykuł jest tworzony dopiero w `injector.py`. 
2. **Brak timestampów:** Claude podaje tylko listę struktur z `anchor_text`, a konkretne czasy (np. `01:23`) oblicza dopiero algorytm Pythona po stronie serwera po udanym parsowaniu.
3. **Brak danych profilu:** Zmienna `{stopka_uzytkownika}` musi być zaciągana z konfiguracji konta po stronie aplikacji.

Zadaniem Claude'a w `generate.py` powinno być jedynie dostarczenie wysoce zoptymalizowanego SEO Hooka (150-200 zn) oraz wyciągniętych hashtagów. Aplikacja następnie złoży to z timestampami, stopką i linkiem do WP, po czym wypchnie przez YouTube API.