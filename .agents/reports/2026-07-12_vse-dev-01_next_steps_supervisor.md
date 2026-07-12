[vse-dev-01 | video-seo-engine 2026-07-12 12:12] 📊 V1:46/50 🟢 V2:1str 🟢 V3:4pl 🟢 V4:stabilny V5:ok — propozycja kolejnych kroków

## Podsumowanie aktualnego stanu (Krok 3A/3B zakończony)
W ramach ostatnich sesji pomyślnie zrealizowano:
1. Utworzenie serwisu `youtube_publish.py` oraz integrację z API YouTube (`videos.update`).
2. Agregację specyfikacji opisu YT (hook 200 znaków, rozdziały, linki, hashtagi).
3. Dodanie modala publikacji (`YouTubePublishModal`) we frontendzie z obsługą przypiętych kanałów.
4. Rozwiązanie wszystkich krytycznych błędów UI (krzaki, brak polskich znaków, błąd przy renderowaniu modala, dodanie zakładki podglądu YouTube na stronie głównej panelu).

Frontend i Backend są obecnie stabilne i umożliwiają zaktualizowanie opisu filmu na YouTube bezpośrednio z platformy VSE.

## Kolejne Kroki (Roadmapa z current.md)

### 1. Krok 4: Stopka opisu YT per-user w app_settings + UI
- Cel: Dodanie możliwości konfigurowania własnej stopki doklejanej do opisu na YouTube (np. linki do social mediów, stałe wezwania do akcji).
- Komponenty: Tabela w bazie dla ustawień profilowych / `app_settings` z polem `youtube_footer`, endpointy API do konfiguracji, strona Ustawień we frontendzie.

### 2. Krok 4b: Osobne przyciski WP / YT w InjectModal
- Obecny modal łączy logikę. Należy rozważyć rozdzielenie interfejsu (UX), aby publikacja do WordPressa i na YouTube była bardziej czytelna.

### 3. Krok E2E: Testy end-to-end dla integracji YouTube
- Należy przeprowadzić test E2E po stronie użytkownika lub z konta testowego z użyciem prawdziwego materiału, aby zweryfikować czy zmiany widnieją na platformie YouTube w sposób stabilny i zgodny ze specyfikacją.

### 4. Krok 5: Bulk Worker (Osobna Sesja)
- Architektura do przetwarzania wideo w paczkach.

## Otwarte Bugi do zbadania
- **Plan Agency**: Widoczny dla obu test-kont (wymaga weryfikacji izolacji uprawnień użytkowników - do zbadania po ukończeniu Kroku 4).
- **profiles.py**: Endpoint `POST /v1/profiles` działa bez weryfikacji tokena uwierzytelniającego `auth` (niski priorytet).

## ⚠️ TRIGGER DLA SUPERVISORA
Zgodnie ze zgłoszeniem w `current.md`:
Po zakończeniu *Kroku 4* oraz *testu E2E YouTube*, konieczne jest załadowanie dispatchu z:
`sonic-void/tmp/dispatch_fapi_roadmap.md` z tytułem: *F-API + architektura VSE<->pressAI do README.md*.
Oznaczać to będzie rozpoczęcie kolejnego wielkiego etapu rozwoju Video SEO Engine.

Proszę Supervisora o decyzję co do przydziału kolejnego dispatchu (najlepiej rozpoczynając od Kroku 4 lub weryfikacji E2E integracji YouTube).
