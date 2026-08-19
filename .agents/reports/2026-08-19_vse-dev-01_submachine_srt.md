# Raport: Generowanie single-line SRT dla SubMachine w video_cutter.py

**Data:** 2026-08-19 23:46
**Autor:** vse-dev-01
**Status:** Zakończone sukcesem ✅

## Cel
Dodanie generowania drugiego pliku SRT (`_submachine.srt`) o formacie jednolitym (single-line na wpis bez znaku `\n` w tekście), w pełni kompatybilnego z wtyczką SubMachine dla Adobe Premiere Pro.

## Zmiany w `local-runner/video_cutter.py`
1. `_generate_srt(vtt_segments, clip_start_sec, clip_end_sec, single_line=False)`:
   - Dodano parametr `single_line: bool = False`.
2. `_flush_screen(steps, all_chunks, words_per_line, gap, single_line=False)`:
   - Gdy `single_line=True`, łączy słowa w jeden ciąg bez podziału na dwie linie (`text = ' '.join(accumulated_words)`).
   - Gdy `single_line=False`, zachowuje dotychczasowy podział karaoke na dwie linie (`line1 \n line2`).
3. `cut_video(config)`:
   - Po zapisaniu standardowego `short.srt` następuje wygenerowanie `_submachine.srt` z parametrem `single_line=True` i zapis do ścieżki `[nazwa]_submachine.srt`.

## Weryfikacja
- Kompilacja składniowa AST (`py_compile`) — sukces.
- Test generowania standardowego SRT vs SubMachine SRT — potwierdzono brak nowych linii w blokach tekstowych SubMachine oraz obecność formatowania wieloliniowego w standardowym SRT.
- Commit na GitHubie: `516d9c4bfccfb2ed0cf49d13c05ce57c1f3bdc95`.
- Weryfikacja zawartości przez `get_file_contents` po commitowaniu — potwierdzono zgodność wszystkich 4 kryteriów.
