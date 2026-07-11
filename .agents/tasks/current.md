# VSE — Current State (aktualizacja: 2026-07-11)

## ✅ Zakończone (ostatnia sesja)
- Security fix: POST /v1/inject wymaga JWT + user_id isolation — commit 7174fb1
- YouTube OAuth connect/disconnect, toast UX, callback redirect — dc51996, b25374c
- yt_channel_ids do body /v1/inject (fix InjectModal) — 5bf7946
- ErrorBoundary dashboard — wdrożony
- Logowanie Google (NextAuth) — URI w GCP Console dodany

## 🟡 W toku / Następne
- **Krok 1:** Spec opisu YouTube (analityk — YT description best practices 2026)
- **Krok 2:** `youtube_publish.py` (serwis videos.update + refresh token)
- **Krok 3:** Integracja z /v1/inject (Scenariusz A: WP → YT sekwencja)
- **Krok 4:** Stopka opisu per-user w app_settings + UI
- **Krok 5:** Bulk Worker (osobna sesja po weryfikacji kroków 1-4)

## ⚠️ Otwarte bugi
- Plan Agency widoczny dla obu test-kont (powiązane z izolacją — do zbadania)
- profiles.py: POST /v1/profiles bez auth (niski priorytet)

## Infrastruktura
- VPS: ubuntu@147.224.162.100
- Docker: docker-compose.vse.yml (vse-api, vse-web, vse-postgres)
- Deploy: `git pull origin main && docker compose -f docker-compose.vse.yml up -d --build [serwis]`
