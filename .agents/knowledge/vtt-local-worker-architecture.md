# Architektura: Lokalny Worker VTT

**Data audytu:** 2026-07-14
**Audytor:** sup-analyst-01

## 1. Lokalizacja workera

Worker znajduje się w repozytorium **`shadow-perihelion`**:
- Ścieżka: `scripts/youtube-worker/youtube_fetch.py`
- Dokumentacja: `scripts/youtube-worker/README.md`
- Pliki docelowe na komputerze właściciela lądują często w `D:\Biblioteki\prawy.pl\subs\` oraz `D:\Biblioteki\prawy.pl\Transkrypcje\`, co zdiagnozowano na podstawie skanowania lokalnego środowiska.

## 2. Mechanizm działania

- **Sposób uruchamiania:** Skrypt Python działający z linii poleceń (CLI). Uruchamiany manualnie lub przez batch dla list URL (np. `python youtube_fetch.py --video <URL>` lub `python youtube_fetch.py --batch urls.txt --output-dir ./data`).
- **Używane biblioteki / API:** 
  - Głównie pakiet `youtube-transcript-api` (wersja v1.2.4+ z użyciem API obiektowego) do pobierania transkryptów z YouTube.
  - Narzędzie `yt-dlp` wywoływane jako subproces do pobierania metadanych wideo (`--dump-json`) oraz jako fallback, jeśli pobieranie przez API zawiedzie (`yt-dlp --write-auto-sub --write-sub`).
  - Worker **nie wymaga klucza YouTube Data API**.
- **Źródło listy wideo:** Parametry przekazywane z CLI przez użytkownika - obsługuje tryb pojedynczy (`--video`), pobieranie kanału (`--channel`), pobieranie playlisty (`--playlist`) oraz pobieranie wsadowe z pliku tekstowego z adresami/ID URL (`--batch urls.txt`).
- **Miejsce zapisu:** Domyślnie zapisuje pliki do `./output` lub folderu wybranego przez flagę `--output-dir`. Zapisuje dwa pliki na każdy URL wideo: plik z transkryptem (`<video_id>.<lang>.vtt`, domyślnie `pl`) i plik JSON z metadanymi (`<video_id>.json`).
- **Komunikacja z serwerem VSE (VPS Oracle):** Worker **nie komunikuje się** bezpośrednio z serwerem VSE. Jest narzędziem typu offline-first. Utworzone pliki `.vtt` i `.json` służą jako wejście dla innych, lokalnych narzędzi (jak np. `scripts/video-seo/generate_seo_v5.py`), z których to poziomów realizowane jest przesyłanie wygenerowanych treści na API systemu VSE (VPS Oracle) lub bezpośrednio do CMS-u (WordPress).
- **Mechanizm ponownego pobrania:** Z kodu skryptu wynika brak kontroli przed ponownym pobraniem pliku. W metodzie `process_video` skrypt każdorazowo wykonuje pobieranie (zarówno metadanych, jak i napisów z YouTube), a otwierając plik zapisu flagą `'w'` (write) - **zawsze nadpisuje** istniejący już plik, bez weryfikacji zawartości.

## 3. Przepływ end-to-end (Flow)

Proces pobierania VTT od momentu zapotrzebowania przez Właściciela do powiązania z VSE wygląda następująco:

```mermaid
flowchart LR
    U[Użytkownik (CLI / urls.txt)] -->|Inicjuje zadanie| YF(youtube_fetch.py)
    YF -->|API / yt-dlp| YT[YouTube]
    YT -->|Transkrypt + Metadane| YF
    YF -->|Zapis pliku (nadpisuje)| Dysk[(D:\Biblioteki\...)]
    Dysk -->|Wczytanie .vtt i .json| LocalSEO[Skrypty lokalne np. generate_seo_v5.py]
    LocalSEO -->|Wysłanie danych SEO (REST API)| VSE[Serwer VSE / API - VPS Oracle]
```

Warto zaznaczyć celowe nazewnictwo plików (zgodnie ze specyfiką pipeline'u wideo): `<video_id>.pl.vtt`, które odpowiada konwencji istniejących skryptów `match_prawy_tv.py` i pozwala na bezproblemową dalszą iterację zadań na tym pliku.