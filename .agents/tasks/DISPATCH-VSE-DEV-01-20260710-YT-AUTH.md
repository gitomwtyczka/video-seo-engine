# DISPATCH — Wdrożenie Kanałów YouTube (OAuth & Stopka)
**Data:** 2026-07-10 | **Dla:** vse-dev-02 | **Od:** vse-strateg-01

Zadaniem w tej iteracji jest porzucenie statycznej konfiguracji stopek z YAML na rzecz bazy danych, połączonej z uwierzytelnieniem kanałów. Zmieniamy architekturę tak, by można było przypiąć wiele kanałów do konta użytkownika VSE poprzez Google OAuth (odczytujemy kanały YouTube z powiązanego konta `youtube.channels.list(mine=true)`), a w bazie przechowujemy `refresh_token` offline do modyfikowania filmów.
Oraz **nowość:** w portalu WP dodajemy dropdown (relację) do kanału, by na sztywno łączyć Portal WP -> Kanał YT.

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)
1. **GitHub MCP:** Zawsze pracuj przez GitHub MCP `get_file_contents` / `create_or_update_file` (lokalne pliki mogą być nieaktualne - pamiętaj o newlines i sha przy aktualizacjach).
2. **KRYTYCZNE ZASADY:** Jesteś Workerem pod Supervisorem. Twoim zadaniem jest napisanie i sprawdzenie kodu w swoim środowisku, a przed podaniem zmian z `create_or_update_file` MUSISZ PRZESŁAĆ RAPORT z kodem do Supervisora. **NIE PUSZUJ NIC BEZ WYRAŹNEJ ZGODY**.
3. **Zrewertuj Śmieci:** Zanim cokolwiek napiszesz, użyj gita w worktree by usunąć commit "include youtube router in main.py [vse-dev-01]". Inny agent pobrudził tam main.

## KROKI DLA DEVA (CHECKLIST)
1. **ZREVERTUJ BRUDNY COMMIT** (użyj `run_command`: `git revert 439808ecb28d9c619d5d6fe2d83207a84184c36a --no-edit && git push origin HEAD:main` lub po prostu pracuj czysto by nie pushować go na remote).
2. Budowa modelu `YouTubeChannel` i powiązanie z `User`.
3. Budowa pola w modelu `WpPortal` wskazującego na `YouTubeChannel`.
4. Zbudowanie endpointów autoryzacyjnych do Google'a z zapisem `refresh_token`.
5. Proste UI uaktualnione o te modele (Dropdown).

Pamiętaj - napisz raport koncepcyjny i proszę o zielone światło przed puszowaniem zmian.