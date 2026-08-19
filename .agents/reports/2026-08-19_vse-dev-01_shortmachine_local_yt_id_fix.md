# Raport Implementacji: ShortMachine local file match by YouTube ID

**Data:** 2026-08-19  
**Autor:** vse-dev-01  
**Status:** Sukces / Wdrożone na GitHub

---

## 1. CO zostało zrobione
Wprowadzono priorytetowe dopasowywanie lokalnego pliku wideo po YouTube ID (`find_local_by_yt_id`) przed próbą dopasowania fingerprintem audio (`find_local_match`) w module wycinania wideo dla ShortMachine (`video_cutter.py`).

## 2. PO CO
Dla filmów prywatnych lub wymagających logowania (np. YouTube ID `yMY7NC4ZDNQ`), funkcja `find_local_match()` nie mogła pobrać próbki audio 90s przez `yt-dlp`, co skutkowało błędem `Failed to download YouTube fragment`.
Dzięki wyszukiwaniu po ID w nazwie pliku (skan `LOCAL_VIDEO_LIBRARY` oraz odpytanie `library_index.db` po kolumnie `filename`):
- Wyszukiwanie jest natychmiastowe (zero ruchu sieciowego, zero obciążenia VPS).
- Działa w 100% offline dla lokalnych plików wideo z ID w nazwie (nawet jeśli film na YouTube jest prywatny/usunięty).

## 3. JAK (Zmiany techniczne)
1. `local-runner/library_matcher.py`:
   - Zdefiniowano funkcję `find_local_by_yt_id(youtube_url: str) -> Optional[str]`, która wyciąga `yt_id` przez `_extract_yt_id()`, skanuje katalogi zdefiniowane w `LOCAL_VIDEO_LIBRARY` w poszukiwaniu plików wideo z `yt_id` w nazwie, a także przeszukuje `library_index.db` (`WHERE filename LIKE ?`).
2. `local-runner/video_cutter.py`:
   - W `_download_fragment()` zaimportowano i wywołano `find_local_by_yt_id()` jako Priorytet 1 przed fingerprint match (`find_local_match()`).

## 4. Commity i weryfikacja
- **VPS Backup:** Uruchomiono pre-deploy backup na VPS (kod wyjścia 0).
- `library_matcher.py` commit: `b3a773d86d6efbf31981dd2528f1f1774e670761`
- `video_cutter.py` commit: `948eb86a692795e01016f2e826b63395e572cfa2`
- **Weryfikacja post-push:** Potwierdzono pomyślny odczyt i integralność obu plików na branchu `main`.
