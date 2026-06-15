# DISPATCH — vse-strateg-01 (aktualizacja)

**Data:** 2026-06-15  
**Od:** Supervisor 01  
**Dla:** `vse-strateg-01` (Strateg)  
**Repo:** `gitomwtyczka/video-seo-engine` (branch: `main`)

> ⚠️ Ten dispatch zastępuje `DISPATCH-VSE-STRATEG-01-20260615-P7P2.md`.
> P7 (YouTube IP blocking) został zamknięty przez `vse-dev-02` — VPS nie jest blokowany przez YouTube.
> Zostaje tylko P2: Google OAuth.

---

## ⛔ ZAKRES NARZĘDZI TEJ SESJI

Ta sesja: TYLKO GitHub MCP + publiczne endpointy.  
**Nie używaj:** file bridge, stellar-relay, Wetty, SSH, bash na VPS.  
Weryfikacja: `curl https://vse.impresjapr.pl/...` lub Swagger `/docs`.  
Deploy: zgłoś Supervisorowi po sesji.

---

## KONTEKST — CO I PO CO

**CO:** Skonfigurowanie logowania przez Google dla użytkowników VSE.

**PO CO:** Teraz jedyna metoda logowania to email + hasło (rejestracja ręczna).
Google OAuth obniża barierę wejścia — użytkownik loguje się jednym kliknięciem
ze swoim kontem Google, bez konieczności pamiętania hasła.
To standard SaaS w 2026 — brak Google login = utrata konwersji.

**Stan na dziś:**
- Przycisk "Zaloguj się przez Google" jest na `/login` — ale nie działa
- Kod NextAuth ma warunkową obsługę Google Provider (działa gdy są env vars)
- Brakuje tylko: `GOOGLE_CLIENT_ID` i `GOOGLE_CLIENT_SECRET` w `.env` na VPS

**OBOWIĄZKOWO przeczytaj:**
- `AGENTS.md` — sekcja GOTCHA (zwłaszcza G8/G9 — nginx + NextAuth routing)

---

## ZADANIE — P2: Google OAuth

### Krok 1 — Utwórz projekt Google Cloud

1. Idź na https://console.cloud.google.com
2. Utwórz nowy projekt (np. `video-seo-engine`) LUB użyj istniejącego
3. APIs & Services → **OAuth consent screen**:
   - User type: **External**
   - App name: `Video SEO Engine`
   - Support email: twój email
   - Scopes: `email`, `profile` (standardowe — nie wymagają weryfikacji)
   - Test users: dodaj swój adres Google
   - Status: **Testing** (wystarczy do własnego użytku)
4. APIs & Services → **Credentials** → Create Credentials → **OAuth 2.0 Client ID**:
   - Application type: **Web application**
   - Name: `vse-web`
   - Authorized redirect URIs: `https://vse.impresjapr.pl/api/auth/callback/google`
5. Skopiuj **Client ID** i **Client Secret**

### Krok 2 — Dodaj credentials do VPS

[Deploy po sesji — zgłoś Supervisorowi]

Przekazanie credentials na VPS (GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET)
wykonuje dedykowana sesja deploy po zakończeniu tej sesji konfiguracyjnej.
Określ wartości w raporcie — Supervisor przekaże je operatorowi.

**UWAGA:** Credentials są tajne — NIE commituj do repo!
`.env` jest w `.gitignore`

### Krok 3 — Rebuild frontendu

[Deploy po sesji — zgłoś Supervisorowi]

Next.js ładuje env vars przy BUILD — wymagany pełny rebuild po dodaniu credentials.
Wykonuje dedykowana sesja deploy.

### Krok 4 — Weryfikacja

```bash
# Czy CSRF działa (NextAuth aktywny)
curl https://vse.impresjapr.pl/api/auth/csrf
# Oczekiwany wynik: {"csrfToken": "..."}

# Czy Google provider jest widoczny
curl https://vse.impresjapr.pl/api/auth/providers
# Oczekiwany wynik: {"google": {...}, "credentials": {...}}
```

Następnie test manualny:
- Otwórz https://vse.impresjapr.pl/login
- Kliknij "Zaloguj się przez Google"
- Przejdź OAuth flow (Google consent)
- Lądujesz na `/dashboard` — sukces

---

## STATUS P7 (dla pamięci)

**P7 ZAMKNIĘTY.** Raport `vse-dev-02` (2026-06-15) potwierdza:
- `yt-dlp` działa na VPS bez blokady
- YouTube IP Oracle Cloud nie jest flagowany
- Pipeline end-to-end działa

Brak potrzeby cookies.txt, proxy ani alternatywnych runnerów.

---

## RAPORTOWANIE

Dual write:
```
video-seo-engine: .agents/reports/2026-06-15_vse-strateg-01_google-oauth.md
sonic-void:       .agents/reports/inbox/2026-06-15_vse-strateg-01_google-oauth.md
```

---

*Dispatch: Supervisor 01 | 2026-06-15 | video-seo-engine*
*Zaktualizowano: 2026-06-15 [sup-worker-01] — usunięto bash VPS (deploy przez Supervisora), dodano blokadę narzędzi*
