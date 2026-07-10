# DISPATCH — Wdrożenie Kanałów YouTube (OAuth & Stopka)
**Data:** 2026-07-10 | **Dla:** vse-dev-01 | **Od:** vse-strateg-01

Zadaniem w tej iteracji jest porzucenie statycznej konfiguracji stopek z YAML na rzecz bazy danych, połączonej z uwierzytelnieniem kanałów. Zmieniamy architekturę tak, by można było przypiąć wiele kanałów do konta użytkownika VSE poprzez Google OAuth (odczytujemy kanały YouTube z powiązanego konta `youtube.channels.list(mine=true)`), a w bazie przechowujemy `refresh_token` offline do modyfikowania filmów.

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)
1. **GitHub MCP:** Zawsze pracuj przez GitHub MCP `get_file_contents` / `create_or_update_file` (lokalne pliki mogą być nieaktualne - pamiętaj o newlines i sha przy aktualizacjach).
2. **PostgreSQL/Alembic:** Model Usera jest w `api/models/user.py`. Modele musisz zaimportować do Base, upewnij się czy mamy tam alembic, jeśli nie, SQLAlchemy `.metadata.create_all` uaktualnia schematy lokalnie (albo poleć usera do migracji bazy `docker exec`). Tworzysz plik `api/models/youtube_channel.py`.
3. **Logika autoryzacyjna (FastAPI):** Tworzysz dwa szybkie endpointy OAuth dla YT w `api/routers/youtube.py` (lub zintegrowane w innym) `/v1/youtube/oauth/login` oraz `/callback`. Trzeba wymusić "offline" żeby otrzymać `refresh_token`. W modelu `YouTubeChannel` ląduje id kanału, `refresh_token`, text stopki (z defaultem pustym).
4. **core/yt_admin.py:** Nadpisz starą metodę czytającą `.yaml` tak, by używała bazy, z której pobierze `refresh_token` i stopkę. Następnie buduje odświeżony token per wywołanie aktualizacji i dokonuje patchowania YT API za pomocą `update_video_title_and_description()`. 
5. **Testowanie:** UI na razie może być uproszczone (jakikolwiek przycisk łączący konto na dashboardzie, i zwracający potwierdzenie podpięcia z przypisanym defaultowym tekstem stopki, który będziemy edytować później).

## KROKI DLA DEVA (CHECKLIST)
1. Zbudowanie modelu `YouTubeChannel` i powiązanie z `User`.
2. Zbudowanie endpointów autoryzacyjnych do Google'a i przechwytywanie autoryzacji (zapis Kanału lub Kanałów usera wyciągniętych przez Data API do DB). Zabezpieczenie tokenów offline.
3. Przepisanie fragmentu z `core/yt_admin.py` na logikę korzystającą ze wspomnianych wyżej tabel.

Rozpocznij wdrażanie. Raportuj błędy i postępy.