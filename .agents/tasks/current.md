# BIEŻĄCE ZADANIA

## ✅ Zamknięte
- ErrorBoundary — wdrożony na produkcji (commit 109cc4f, 395b710)
- YouTube OAuth — nowe credentials GCP 934133075831, redirect_uri fix
- YouTube kanały — podłączanie działa end-to-end
- fix: channel_id/channel_title mismatch w API (commit 429b274)
- fix: duplicate channel → yt=connected zamiast yt=error (commit 429b274)
- UX: redirect po OAuth callback + zielony/czerwony toast (vse-worker)
- Google Auth Platform — NextAuth callback URI dodany, propagacja powinna być gotowa
- Audit: zakładka YT w dashboardzie — NIE ISTNIEJE, trzeba zbudować od zera

## 🟡 W toku
- [DISPATCH OCZEKUJE] Implementacja zakładki YouTube w dashboardzie
  → dispatch task: `2026-07-11_Supervisor-03_vse-analyst_yt-dashboard-audit.md` (zakończony)
  → implementacja: DO ZLECENIA nowemu workerowi

## 🔵 Następne
- Implementacja zakładki YouTube w dashboardzie (duże wdrożenie architektoniczne)
  - backend: endpointy harmonogramu/kolejki/historii YT
  - frontend: nowa sekcja w dashboardzie
  - DB: nowe tabele (pipeline_jobs, yt_publish_queue lub podobne)
- Sprawa 2: izolacja kont (różni userzy widzą nawzajem swoje zasoby) — wymaga zbadania
- Weryfikacja logowania przez Google po propagacji GCP
