# Raport: Fix VTT Truncation dla długich filmów (runner)

**Cel:** Rozwiązanie problemu ucinania plików VTT podczas pobierania przez yt-dlp.

## Wynik wdrożenia
- Zmodyfikowano skrypt `local-runner/runner.py`.
- **SHA backupu** (`local-runner/runner.py.bak-2026-07-20`): `2a19b605485f74193f1fb69957860c2f7f615a3e`
- **SHA zaktualizowanego runnera** (`local-runner/runner.py`): `33fe7329cfcb88e4f9a076591de602d066fe60ed`

## Wprowadzone zmiany

1. **Flagi yt-dlp**: Dodano flagi zapobiegające chunkowaniu oraz błędom połączenia w `_try_ytdlp_with_cookies_file` i `_try_ytdlp_with_browser`:
   ```python
   "--extractor-args", "youtube:player_client=tv_embedded",
   "--no-part",
   "--retries", "10",
   "--fragment-retries", "10"
   ```
2. **Walidacja pokrycia**: Dodano funkcję pomocniczą `_get_segments_duration(segments: list) -> float` oraz logowanie pokrycia po sparsowaniu segmentów VTT.
   *Przykładowy log w środowisku produkcyjnym będzie wyglądać następująco:*
   ```
   VTT coverage: last segment at 4850s (80m 50s) — 2341 segments
   ```

## Nierozwiązane edge case'y
- Jeżeli YouTube zbanuje/odrzuci profil `tv_embedded`, może być wymagana zmiana na inny `player_client` (np. `web_creator` lub `android_embedded`), co będzie wymagało ręcznej zmiany.
- Jeśli napisy auto-generated faktycznie kończą się przed końcem filmu ze względu na błąd na YouTube, skrypt zaloguje ich rzeczywisty czas.
