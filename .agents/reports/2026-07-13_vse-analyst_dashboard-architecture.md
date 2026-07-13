# Analiza architektoniczna: dashboard-inner.tsx

## Pomiar
- Linie: 7865
- Rozmiar: 101.3 KB (103825 bajtów)
- Liczba komponentów wewnętrznych: 9
- Lista komponentów:
  1. `CopyButton` (linia 881)
  2. `ResultSection` (linia 1013)
  3. `TabBar` (linia 1173)
  4. `InjectModal` (linia 1381)
  5. `AddPortalModal` (linia 3017)
  6. `ManageSubscriptionLink` (linia 4385)
  7. `DashboardInner` (export default, linia 4579)
  8. `NavItem` (linia 7574)
  9. `WpQuickPanel` (linia 7714)

## Metody dostępu — ocena

**Metoda 1: GitHub MCP `get_file_contents`**
- Działa, ale ma krytyczne ukryte ograniczenie. Przy dużym rozmiarze zwrotu (powyżej pewnego progu) narzędzie MCP zapisuje wynik do pliku pośredniego (`.../output.txt`). Gdy agent automatycznie próbuje go odczytać używając standardowego `view_file` bez określonego Start/End line, widzi jedynie pierwsze 800 linii. System w tym wypadku nie zwraca błędu, tylko cicho ucina treść, dając agentowi złudzenie pracy na pełnym pliku (skutkiem są hotfixy i modyfikacje złych sekcji). `download_url` w odpowiedzi MCP daje link do pełnego pliku, ale trzeba go świadomie użyć.

**Metoda 2: SSH grep (current workaround)**
- Działa całkiem dobrze jako narzędzie nawigacyjne. Wykonanie np. `grep -n 'function '` mapuje zgrubną strukturę pliku. Ograniczeniem jest brak pewności, gdzie dokładnie dany blok się kończy (zależność od identacji i nawiasów). Daje to pogląd na to "gdzie szukać", ale nie pozwala wprost "zmodyfikować".

**Metoda 3: SSH `sed -n 'X,Yp'` (czytanie fragmentów)**
- Działa i jest bardzo niezawodny. Wiedząc z grepa, że dany komponent startuje w linii 1381, można z użyciem `sed -n '1381,1800p'` bez problemu przeczytać tylko interesujący kontekst. Ogranicza to wpadanie w pulapkę cięcia okien kontekstu i minimalizuje rozmiar czytanych danych z pominięciem blokad narzędziowych.

**Metoda 4: Podział pliku (refactor)**
- Plik jest doskonałym kandydatem do podziału. Aż 8 komponentów pobocznych można po prostu wydzielić. Struktura `app/dashboard` i środowisko Next.js naturalnie wspierają umieszczanie wydzielonych plików jako `components/...` lub obok w tym samym folderze. Wówczas z 7865 linii zrobiłoby się 9 plików, a sam `DashboardInner` uległby ogromnej miniaturyzacji do ok. połowy obecnej wielkości. 

## Rekomendacja krótkoterminowa
Agent, który dostaje zadanie modyfikacji `dashboard-inner.tsx` musi natychmiast zaprzestać ufania ślepemu czytaniu z MCP. Prawidłowy flow czytania (zapis do AGENTS.md):
Najpierw użyj mapowania pliku przez `grep` aby poznać numery linii modyfikowanej funkcji. Następnie czytaj wycinek przez:
`ssh ... "sed -n 'START,ENDp' path/to/file"` aby zapoznać się z logiką, a samą edycję docelowo buduj na zasadzie znalezienia i podmiany w tym konkretnym bloku lub używaj `multi_replace_file_content` na z góry namierzonej przez grepa próbce.

## Rekomendacja Średnioterminowa
Wyodrębnić niezależne struktury: `CopyButton`, `ResultSection`, `TabBar`, `InjectModal`, `AddPortalModal`, `ManageSubscriptionLink`, `NavItem`, `WpQuickPanel` do osobnych plików (np. do katalogu `web/src/app/dashboard/components/`). Główny plik `dashboard-inner.tsx` powinien jedynie je importować. Każdy wydzielony plik będzie wielkości rzędu 200-800 linii, co rozwiąże całkowicie problem okna kontekstu.

## Rekomendacja długoterminowa
Oddzielenie warstwy stanów (state/hooks) od warstwy widoku w samym `DashboardInner`. Stworzenie custom hooka (np. `useDashboardLogic.ts`), który będzie agregował wywołania pobierania danych, trzymania flag modalów itp., i pozostawi plik `.tsx` jako cienką warstwę wyświetlania.

## Standard operacyjny (do dodania do AGENTS.md)
```markdown
## ⚠️ PUŁAPKA CZYTANIA: Duże pliki i MCP
Zawsze, gdy modyfikujesz plik powyżej 800 linii (zwłaszcza `dashboard-inner.tsx`):
1. **ZAKAZ** polegania na surowym odczycie pełnego pliku, który trafia do bufora `output.txt` (widzisz wtedy tylko 800 linii, to iluzja!).
2. **NAKAZ** mapowania przed pracą: wykonaj najpierw `ssh ... "grep -n 'function [Nazwa]' plik"` by odnaleźć pozycję.
3. **NAKAZ** odczytu wąskiego: czytaj logikę blokami z użyciem `ssh ... "sed -n 'StartLine,EndLinep' plik"`.
4. Modyfikacji dokonuj przez precyzyjny `create_or_update_file` po uprzednim przetestowaniu poprawnego zmapowania linii w oknie narzędzia.
```