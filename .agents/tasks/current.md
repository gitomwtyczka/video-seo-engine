# VSE — Current State (aktualizacja: 2026-07-12)

## Zakończone (sesja 2026-07-12 - vse-dev-02)
- Zaimplementowano aktualizację tytułu na YouTube w endpoincie publish-description oraz inject (używa `yt_title` z `schema_data`).
- Zweryfikowano działanie stopki opisu YT per-user w backendzie. Dodano model i endpoint `PUT /v1/youtube/channels/{channel_id}` do zapisu `footer_text`.
- Endpoint `GET /v1/youtube/channels` zwraca teraz `footer_text` dla poprawnej integracji z UI.
- Wdrożenie na VPS zakończone pomyślnie.

## Zakończone (wcześniej)
- Przebudowano /v1/youtube/publish-description, aby budował opis za pomocą \build_yt_description.
- Rozszerzono YouTubePublishRequest o schema_data.
- Krok 3B (poprawki bugów): naprawa kodowania znaków na frontendzie, inject extractVideoId, dodanie zakładki YouTube w UI.
- Krok 3A/3B: Integracja youtube_publish.py, modal frontend, agregacja opsu YT.

## W toku
- Brak aktywnych tasków. Oczekuję na dyspozycje.

## Następne (w kolejności)
- Krok 4: UI na frontendzie do obsługi `footer_text` (w app_settings lub konfiguracji profilu).
- Krok 4b: Osobne przyciski WP / YT w InjectModal (frontend).
- E2E test YouTube: sprawdzić czy opis i tytuł wideo faktycznie się zmienia (wymaga UI i przetestowania).
- Krok 5: Bulk Worker (osobna sesja).

## TRIGGER dla Supervisora — po Kroku 4 + E2E test
PO zakończeniu Kroku 4 i potwierdzeniu E2E YouTube:
Przypomnij userowi aby wkleić dispatch z:
  sonic-void/tmp/dispatch_fapi_roadmap.md
Temat: F-API + architektura VSE<->pressAI do README.md
To jest następny główny etap rozwoju VSE.

## Otwarte bugi
- Plan Agency widoczny dla obu test-kont (izolacja, do zbadania po Kroku 4)
- profiles.py: POST /v1/profiles bez auth (niski priorytet)

## Infrastruktura
- VPS: ubuntu@147.224.162.100
- SSH key: C:\Users\tomas2\.ssh\oracle-crimson.key
- Docker: docker-compose.vse.yml (vse-api, vse-web, vse-postgres)
- Deploy API: git pull && docker compose -f docker-compose.vse.yml up -d --build vse-api
- Deploy WEB: git pull && docker compose -f docker-compose.vse.yml up -d --build vse-web
- dashboard-inner.tsx jest 80KB — przy edycji używaj gh api zamiast GitHub MCP
