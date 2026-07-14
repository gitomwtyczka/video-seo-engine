# Raport: Audit lokalnego workera VTT
**Callsign:** sup-analyst-01
**Data:** 2026-07-14
**Temat:** Wynik audytu workera YouTube -> VTT

Wykonano zadanie zgodnie z poleceniem Supervisora.

## Wyniki audytu
1. **Lokalizacja:** Worker to skrypt Python `youtube_fetch.py` zlokalizowany w repozytorium `shadow-perihelion` (w ścieżce: `scripts/youtube-worker/youtube_fetch.py`). Pliki wynikowe w postaci `.vtt` zapisywane są przez właściciela w zdefiniowanym przez niego katalogu wyjściowym, co po skanowaniu maszyny ujawniono między innymi w `D:\Biblioteki\prawy.pl\subs\`.
2. **Mechanizm:** Skrypt pobiera transkrypty przy użyciu nowej wersji paczki `youtube-transcript-api` a same metadane pobiera jako fallack za pomocą subprocesu narządzia `yt-dlp`. Całkowicie izoluje to rozwiązanie od konieczności obsługi kluczy `YouTube Data API v3`.
3. **Komunikacja & Ponowne pobieranie:** Skrypt w ogóle nie kontaktuje się z instalacją VSE na VPS Oracle. Pełni funkcję zrzucania plików offline (generuje paczki `.vtt` + `.json`). Dalej są one obrabiane przez narzędzia takie jak `generate_seo_v5.py`, komunikujące się następnie z serwerem/Wordpressem. Warto podkreślić, że skrypt nie posiada logiki obrony przed podwójnym pobieraniem tych samych plików - brutalnie nadpisuje pliki na dysku (tryb otwarcia flagą `'w'`).

Wszystkie ustalenia rozpisano wraz z przepływem architekturalnym End-to-End pod ścieżką w bazie wiedzy (zgodnie z Deliverables): 
`video-seo-engine/.agents/knowledge/vtt-local-worker-architecture.md`