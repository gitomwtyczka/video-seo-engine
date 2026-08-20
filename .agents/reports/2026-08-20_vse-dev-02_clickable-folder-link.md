# Raport z wdrożenia: Klikalny link do folderu po renderze

## 1. Wygląd przed zmianą
Przed modyfikacją w dashboardzie (zakładka ShortMachine) pokazywał się zwykły nielinkowany tekst. Generowany komponent wyglądał następująco:
`<span>Gotowe: {smJobStatus[i].result_paths?.raw || 'plik zapisany'}</span>`

## 2. SHA commitu
Zmiany w `dashboard-inner.tsx` zostały pomyślnie zacommitowane.
**SHA:** `7aec562372cea53a1b9db90610928edf791ae6d7`

## 3. Status deployu
Deploy zakończył się sukcesem. Najpierw wykonano skrypt `backup_pre_deploy.sh`, po czym aplikacja `vse-web` została zbudowana od nowa. Kontener `vse-web` zrestartował się poprawnie (Docker build exited with code 0).

## 4. Opis działania linku
W zakładce ShortMachine, kiedy status wygenerowanego shorta to `done`, pod tekstem "Gotowe" pojawia się link z ikoną 📂 ("Otwórz folder wyjściowy"). Kod bierze ścieżkę zwróconą przez API w `result_paths.raw`, sprawdza czy zawiera w sobie nazwę pliku, odcina ją, a z reszty (ścieżki do folderu) formułuje poprawny link w formacie `file:///` podmieniając backslashe na forward slashe.

[vse-dev-02 | video-seo-engine 2026-08-20]