# VSE — Current State (aktualizacja: 2026-07-12 21:58)

## Zakończone (sesja 2026-07-12 - vse-fix2)
- Przebudowano /v1/youtube/publish-description, aby budował opis za pomocą uild_yt_description (co pozwala na per-channel ooter_text).
- Rozszerzono YouTubePublishRequest o schema_data (wymagane z PressAI).
- Wyczyszczono frontend (usunięto budowanie opisu z dashboard-inner.tsx).
- Wdrożenie na VPS zakończone pomyślnie.

## Zakończone (wcześniej)
- Krok 3B (poprawki bugów): naprawa kodowania znaków na frontendzie, inject extractVideoId, dodanie zakładki YouTube w UI
- Krok 3A/3B: Integracja youtube_publish.py, modal frontend, agregacja opsu YT
- Security fix: POST /v1/inject wymaga JWT + user_id isolation — commit 7174fb1
- Hotfix frontend: Authorization header w fetch /v1/inject — commit bd1bbc5
- YouTube OAuth connect/disconnect, toast UX, callback redirect
- youtube_publish.py — serwis videos.update + refresh token — Krok 2 done
- YT description spec — hook (200 zn) + hashtags osobno, składane w backend
- ADR-11 dodany do docs/ARCHITECTURE_decisions.md

## W toku
- Brak aktywnych tasków. Oczekuję na dyspozycje.

## Następne (w kolejności)
- Zaimplementowanie aktualizacji tytułu na YouTube w endpoincie publish-description (obecnie modyfikowany jest tylko opis). Wymaga poszerzenia schematu API.
- Krok 4: Stopka opisu YT per-user w app_settings + UI
- Krok 4b: Osobne przyciski WP / YT w InjectModal
- E2E test YouTube: sprawdzić czy opis wideo faktycznie się zmienia
- Krok 5: Bulk Worker (osobna sesja)

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
