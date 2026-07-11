# VSE — Current State (aktualizacja: 2026-07-11 22:30)

## Zakonczone (sesja 2026-07-11)
- Security fix: POST /v1/inject wymaga JWT + user_id isolation — commit 7174fb1
- Hotfix frontend: Authorization header w fetch /v1/inject — commit bd1bbc5
- YouTube OAuth connect/disconnect, toast UX, callback redirect
- youtube_publish.py — serwis videos.update + refresh token — Krok 2 done
- YT description spec — hook (200 zn) + hashtags osobno, skladane w backend
- ADR-11 dodany do docs/ARCHITECTURE_decisions.md

## W toku
- Krok 3: Integracja inject.py -> youtube_publish.py (Scenariusz A)
  + zmiana promptu w core/generator.py
  + dispatch wysłany do VSE worker

## Nastepne (w kolejnosci)
- Krok 4: Stopka opisu YT per-user w app_settings + UI
- Krok 4b: Osobne przyciski WP / YT w InjectModal
- E2E test YouTube: sprawdzic czy opis wideo faktycznie sie zmienia
- Krok 5: Bulk Worker (osobna sesja)

## TRIGGER dla Supervisora — po Kroku 4 + E2E test
PO zakonczeniu Kroku 4 i potwierdzeniu E2E YouTube:
Przypomnij userowi aby wkleic dispatch z:
  sonic-void/tmp/dispatch_fapi_roadmap.md
Temat: F-API + architektura VSE<->pressAI do README.md
To jest nastepny glowny etap rozwoju VSE.

## Otwarte bugi
- Plan Agency widoczny dla obu test-kont (izolacja, do zbadania po Kroku 4)
- profiles.py: POST /v1/profiles bez auth (niski priorytet)

## Infrastruktura
- VPS: ubuntu@147.224.162.100
- SSH key: C:\Users\tomas2\.ssh\oracle-crimson.key
- Docker: docker-compose.vse.yml (vse-api, vse-web, vse-postgres)
- Deploy API: git pull && docker compose -f docker-compose.vse.yml up -d --build vse-api
- Deploy WEB: git pull && docker compose -f docker-compose.vse.yml up -d --build vse-web
- dashboard-inner.tsx jest 80KB — przy edycji uzywaj gh api zamiast GitHub MCP
