# DISPATCH — vse-strateg-01

**Data:** 2026-06-15  
**Od:** Supervisor 01  
**Dla:** `vse-strateg-01` (Strateg)  
**Repo:** `gitomwtyczka/video-seo-engine` (branch: `main`)  
**Priorytet:** 🔴 P7 WYSOKI / 🟡 P2 SREDNI

---

## KONTEKST STARTOWY

Projekt `video-seo-engine` ma działający frontend + auth na https://vse.impresjapr.pl.
Core pipeline (YT URL → SEO output) wymaga decyzji strategicznych, które blokują `vse-dev-02`.

**OBOWIĄZKOWO przeczytaj:**
- `.agents/handoff/2026-06-14_vse-dev-01_handoff.md`
- `AGENTS.md` w root repo

---

## ZADANIE 1 — P7: YouTube IP Blocking na Oracle VPS

### Problem
Oracle Cloud VPS (`147.224.162.100`) może być zablokowany przez YouTube. `yt-dlp` używany przez pipeline do pobierania metadanych wideo może zwracać HTTP 403 / bot detection.

To jest **krytyczny bloker** dla core produktu — bez metadanych YT nie ma SEO output.

### Twoje zadanie

**Krok 1 — Diagnoza (przez FILE BRIDGE):**
```bash
# Na VPS oracle-crimson
docker exec vse-api yt-dlp --version
docker exec vse-api yt-dlp --dump-json --no-download \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 2>&1 | tail -30
```

Możliwe wyniki:
- ✅ JSON z metadanymi — brak blokady, pipeline może działać
- ❌ HTTP Error 429 / 403 / bot detection — IP zablokowane
- ❌ Timeout / connection refused — inne ograniczenie

**Krok 2 — Decyzja strategiczna (wybierz opcję):**

| Opcja | Opis | Koszt | Złożoność |
|---|---|---|---|
| **A. cookies.txt** | Eksport cookies z zalogowanego YT konta, mount do kontenera | 🟢 0 PLN | 🟡 średnła |
| **B. YouTube Data API v3** | Oficjalne API Google, bez yt-dlp | 🟡 $0-15/mies | 🟡 średnła |
| **C. Proxy rotating** | Zewnętrzny proxy (np. ScraperAPI, Bright Data) | 🔴 $49+/mies | 🟢 prosta |
| **D. VPS lokalny runner** | Komenda na local-pc przez FILE BRIDGE | 🟢 0 PLN | 🔴 złożona archit. |
| **E. Vultr LLM VPS** | Uruchom yt-dlp na Vultr VPS (inny IP) | 🟡 już płacimy | 🟡 średnła |

**Rekomendacja Supervisora:** Zacznij od opcji A (cookies.txt) — zero kosztu, szybkie. Jeśli YT cookies wygasają lub pipeline jest zbyt wolny — przejdź do opcji B (YT Data API v3).

**Krok 3 — Implementacja wybranej opcji:**

Dla **Opcji A (cookies.txt):**
```bash
# 1. Wygeneruj cookies z przeglądarki (rozszerzenie: Get cookies.txt LOCALLY)
# 2. Wgraj na VPS: scp cookies.txt ubuntu@147.224.162.100:/home/ubuntu/video-seo-engine/
# 3. Dodaj do docker-compose.vse.yml — mount
#    volumes:
#      - ./cookies.txt:/app/cookies.txt:ro
# 4. W api/processor.py użyj:
#    yt_opts = {'cookiefile': '/app/cookies.txt', ...}
```

Dla **Opcji B (YouTube Data API v3):**
- Załóż projekt w Google Cloud Console (można ten sam co OAuth P2)
- Aktywuj YouTube Data API v3
- Pobierz API key
- Dodaj `YOUTUBE_API_KEY=...` do `.env` na VPS
- Przełącz `api/processor.py` na requests do `https://www.googleapis.com/youtube/v3/videos`
- Endpointy: `snippet`, `contentDetails`, `statistics`

**Weryfikacja P7:**
```bash
curl -X POST https://vse.impresjapr.pl/api/v1/process \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
# Oczekiwany wynik: JSON z title, description, tags, SEO output
# Czas odpowiedzi: <30s (może być długi ze względu na AI generation)
```

---

## ZADANIE 2 — P2: Google OAuth (niska pilność)

### Problem
Logowanie przez Google jest wyświetlone na /login (przycisk) ale nie działa — brak credentials w `.env`.

### Wymagane credentials
```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

### Kroki

**Krok 1 — Google Cloud Console:**
1. Otwórz https://console.cloud.google.com
2. Utwórz projekt (lub użyj tego samego co YouTube Data API)
3. APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
4. Application type: Web application
5. Authorized redirect URIs: `https://vse.impresjapr.pl/api/auth/callback/google`
6. Skopiuj Client ID i Client Secret

**Krok 2 — OAuth consent screen:**
1. Configure consent screen — External
2. App name: Video SEO Engine
3. Scopes: `email`, `profile`
4. Test users: dodaj swoje konto Google
5. Status: Testing (nie trzeba weryfikacji dla własnego użytku)

**Krok 3 — Dodaj do .env na VPS:**
```bash
# Edytuj przez FILE BRIDGE lub SSH
echo 'GOOGLE_CLIENT_ID=xxx' >> /home/ubuntu/video-seo-engine/.env
echo 'GOOGLE_CLIENT_SECRET=yyy' >> /home/ubuntu/video-seo-engine/.env

# Restart Next.js (zmienne env — wymagany rebuild!)
docker compose -f docker-compose.vse.yml build web
docker compose -f docker-compose.vse.yml up -d --no-deps --force-recreate web
```

**UWAGA:** Credentials są TAJNE. Zapisz je w bezpiecznym miejscu (manager haseł). NIE commituj do repo.

**Weryfikacja P2:**
- Otwórz https://vse.impresjapr.pl/login
- Kliknij "Zaloguj się przez Google"
- Przechodzi przez OAuth flow i ląduje na /dashboard

---

## KOLEJNOŚĆ WYKONANIA

1. **P7 diagnoza najpierw** — `yt-dlp` test na VPS (2 minuty)
2. **P7 implementacja** — opcja A lub B
3. **P2** — Google OAuth (można równolegle jeśli P7 czeka na zewnętrzne akcje)
4. **Raport zbiorczy** → dual write

---

## RAPORTOWANIE

Po zakończeniu — dual write:

**Repo projektu:**
```
gitomwtyczka/video-seo-engine
branch: main
path: .agents/reports/2026-06-15_vse-strateg-01_[temat].md
```

**Supervisor inbox:**
```
gitomwtyczka/sonic-void
branch: master
path: .agents/reports/inbox/2026-06-15_vse-strateg-01_[temat].md
```

**Format raportu minimalny:**
```markdown
# Raport — P7/P2 [wynik]
**Agent:** vse-strateg-01
**Status P7:** ✅/⚠️/❌
**Status P2:** ✅/⚠️/❌
**Opcja wybrana (P7):** A/B/C/D/E
**Commit SHA:** ...
**Blokery:** ...
```

---

## LINKI OPERACYJNE

- Repo: https://github.com/gitomwtyczka/video-seo-engine
- Site: https://vse.impresjapr.pl
- Swagger: https://vse.impresjapr.pl/docs
- VPS: `147.224.162.100` (Oracle ARM, Vultr LLM jako fallback)
- Docker compose: `docker-compose.vse.yml`
- Google Cloud Console: https://console.cloud.google.com
- YT Data API: https://console.cloud.google.com/apis/library/youtube.googleapis.com

---

*Dispatch: Supervisor 01 | 2026-06-15 | video-seo-engine*
