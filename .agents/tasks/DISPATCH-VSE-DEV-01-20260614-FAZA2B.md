# DISPATCH — vse-dev-01
# Zadanie: Faza 2B — YouTube unblock + /v1/process end-to-end test
# Data: 2026-06-14
# Od: vse-strateg-01

---

## 🎯 Kontekst

Faza 2A DONE — VSE API v2.0.0 działa na oracle-crimson :8085 (healthy, 11h uptime).
Główny bloker: Oracle Cloud IP flagowany przez YouTube → yt-dlp/youtube-transcript-api failuje na VPS.

**Twoje zadania w tej sesji:**
1. Implementacja cookies.txt strategy (YouTube unblock — krótkoterm)
2. End-to-end test `/v1/process` z realnym prawy.pl post_id
3. Aktualizacja README checkboxów Fazy 2
4. Raport z wynikami

---

## 📌 ZADANIE 1 — YouTube Unblock via cookies.txt

### Strategia (decyzja stratega)

Krótkoterm: `yt-dlp --cookies /app/youtube_cookies.txt` pass-through.
Kookies dostarczane przez Usera z przeglądarki Chrome (zalogowanej na YouTube).

### Implementacja

#### 1a. Zmodyfikuj `core/fetcher.py`

W funkcji pobierającej transkrypt i metadane przez yt-dlp:
- Dodaj parametr `cookies_path: str | None = None`
- Jeśli `cookies_path` ustawiony i plik istnieje → przekazuj `--cookies {cookies_path}` do yt-dlp
- Env var: `YT_COOKIES_PATH` (default: `/app/youtube_cookies.txt`)
- Log info jeśli cookies file nie istnieje → fallback bez cookies (może failować na VPS)

#### 1b. Zmodyfikuj `api/services/pipeline.py`

- Przekaż `cookies_path=os.getenv('YT_COOKIES_PATH')` do fetcher calls

#### 1c. Dockerfile.api

Dodaj VOLUME lub mount point:
```dockerfile
# Cookies mount point (optional, for YouTube unblocking on restricted IPs)
VOLUME ["/app/cookies"]
```

Dodaj env var default:
```dockerfile
ENV YT_COOKIES_PATH=/app/cookies/youtube_cookies.txt
```

#### 1d. docker-compose.vse.yml

Dodaj volume mount:
```yaml
volumes:
  - /home/ubuntu/video-seo-engine/cookies:/app/cookies:ro
```

I utwórz katalog na VPS:
```bash
mkdir -p /home/ubuntu/video-seo-engine/cookies
```

#### 1e. Instrukcja dla Usera (zapisz w docs/YOUTUBE_COOKIES.md)

Jak wyeksportować cookies z Chrome:
1. Zainstaluj rozszerzenie: "Get cookies.txt LOCALLY" (Chrome Web Store)
2. Przejdź na youtube.com (zalogowany)
3. Export → zapisz jako `youtube_cookies.txt`
4. Skopiuj na VPS: `scp youtube_cookies.txt ubuntu@147.224.162.100:/home/ubuntu/video-seo-engine/cookies/`
5. Zrestartuj kontener: `docker restart vse-api`

---

## 📌 ZADANIE 2 — End-to-end test /v1/process

### Kontekst
- prawy.pl WordPress API: `WP_BASE_URL` z .env.api na VPS (sprawdź)
- Credentials WP: `WP_USER` + `WP_APP_PASSWORD` z .env.api
- Test video: jeden z 4 już przetworzonych filmów (bezpieczny)
- Jeśli brak .env.api na VPS — User musi dostarczyć (STOP → raport)

### Test manualny przez Swagger
```bash
curl -X POST http://147.224.162.100:8085/v1/generate \\
  -H "Content-Type: application/json" \\
  -d '{
    "video_url": "https://youtube.com/watch?v=VIDEO_ID",
    "site_config": {
      "wp_base_url": "https://prawy.pl",
      "wp_user": "...",
      "wp_app_password": "..."
    },
    "options": {
      "llm_provider": "claude",
      "auto_inject": false
    }
  }'
```

**UWAGA:** Zacznij od `/v1/generate` (no inject) — bezpieczniejszy test.
Dopiero po success → test `/v1/process` z `auto_inject: true`.

---

## 📌 ZADANIE 3 — README checkboxy Fazy 2

Aktualizuj README.md — sekcja `### 🟡 Faza 2`:
```markdown
### ✅ Faza 2 — VSE API Service (DONE)
- [x] FastAPI app structure (api/ module) — commit d7a86e79
- [x] Pydantic models — ProcessRequest/Response, SiteConfig
- [x] POST /v1/process — full pipeline endpoint
- [x] POST /v1/generate — schema-only endpoint
- [x] POST /v1/inject — inject-only endpoint
- [x] GET /health — health check ✅ v2.0.0
- [x] Dockerfile.api + docker-compose.vse.yml
- [x] Deployment oracle-crimson :8085 — healthy
- [ ] YouTube cookies.txt strategy (IP unblock) — **Faza 2B**
- [ ] End-to-end test z realnym prawy.pl post_id — **Faza 2B**
- [ ] POST /v1/monitor/start — Channel Monitor background task
- [ ] POST /v1/sitemap — weryfikacja end-to-end
```

---

## 📌 ZADANIE 4 — Raport

Dual-write:
1. `video-seo-engine/.agents/reports/2026-06-14_vse-dev-01_faza2b.md`
2. `sonic-void/.agents/reports/inbox/2026-06-14_vse-dev-01_faza2b.md`

Raport powinien zawierać:
- Status każdego zadania
- Logi z testu /v1/generate (response JSON lub error)
- SHA commitów
- Pending items

---

## 🔧 Środowisko operacyjne

```bash
# SSH do oracle-crimson:
ssh -i C:\\Users\\tomas2\\.ssh\\oracle-crimson.key -o BatchMode=yes ubuntu@147.224.162.100 "komenda"

# Rebuild po zmianach:
docker build -f Dockerfile.api -t vse-api . && docker stop vse-api && docker rm vse-api && docker run -d --name vse-api --env-file .env.api -p 8085:8085 -v /home/ubuntu/video-seo-engine/cookies:/app/cookies:ro vse-api

# Sprawdź logi:
docker logs vse-api --tail 50
```

---

## ⚠️ STOP-CONDITIONS

Zatrzymaj i raportuj do stratega jeśli:
- Brak `.env.api` na VPS — User musi dostarczyć credentials
- YouTube test zwraca błąd nawet z cookies — eskaluj do stratega (Opcja C: hybrydowa architektura)
- Disk > 90% — alert do Supervisora

---

## 📢 Po zakończeniu

Wróć do vse-strateg-01 z raportem przez dual-write.

---
*Dispatch: vse-strateg-01 | 2026-06-14 10:35 | video-seo-engine Faza 2B*
