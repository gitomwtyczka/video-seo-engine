# DISPATCH — vse-dev-01
# Zadanie: Faza 2B — YouTube unblock + /v1/process end-to-end test
# Data: 2026-06-14 | Zatwierdzone przez: User
# Od: vse-strateg-01
# Strategia YT: Opcja A (cookies.txt, krótkoterm) + Opcja C (hybrid arch, longterm)

---

## 🎯 Kontekst

Faza 2A DONE — VSE API v2.0.0 działa na oracle-crimson :8085 (healthy, 11h uptime).
Główny bloker: Oracle Cloud IP flagowany przez YouTube → yt-dlp/youtube-transcript-api failuje na VPS.

**Zatwierdzona strategia (User, 2026-06-14):**
- **Opcja A** — cookies.txt pass-through (krótkoterm, unlock natychmiastowy)
- **Opcja C** — architektura hybrydowa (longterm, SaaS-ready)

**Twoje zadania w tej sesji:**
1. Implementacja cookies.txt strategy [Opcja A]
2. Specyfikacja `/v1/fetch` endpointu — lokalny runner [Opcja C prep]
3. End-to-end test `/v1/generate` z realnym video
4. Aktualizacja README checkboxów Fazy 2
5. Raport z wynikami

---

## 📌 ZADANIE 1 — YouTube Unblock via cookies.txt [Opcja A]

### Implementacja

#### 1a. Zmodyfikuj `core/fetcher.py`

W funkcji pobierającej transkrypt i metadane przez yt-dlp:
- Dodaj parametr `cookies_path: str | None = None`
- Jeśli `cookies_path` ustawiony i plik istnieje → przekazuj `--cookies {cookies_path}` do yt-dlp
- Env var: `YT_COOKIES_PATH` (default: `/app/cookies/youtube_cookies.txt`)
- Log INFO jeśli cookies file nie istnieje → fallback bez cookies + log WARNING

#### 1b. Zmodyfikuj `api/services/pipeline.py`

- Przekaż `cookies_path=os.getenv('YT_COOKIES_PATH')` do wszystkich fetcher calls

#### 1c. Dockerfile.api — dodaj:
```dockerfile
# Cookies mount point (optional, for YouTube IP unblocking)
VOLUME ["/app/cookies"]
ENV YT_COOKIES_PATH=/app/cookies/youtube_cookies.txt
```

#### 1d. docker-compose.vse.yml — dodaj volume:
```yaml
volumes:
  - /home/ubuntu/video-seo-engine/cookies:/app/cookies:ro
```

#### 1e. Utwórz katalog na VPS:
```bash
mkdir -p /home/ubuntu/video-seo-engine/cookies
```

#### 1f. Instrukcja dla Usera — zapisz w `docs/YOUTUBE_COOKIES.md`:
```markdown
# YouTube Cookies — instrukcja (IP Unblock)

Jeśli VSE API jest hostowane na VPS (Oracle, AWS, etc.) YouTube może blokować IP.
Rozwiązanie: dostarczenie cookies z zalogowanej sesji przeglądarki.

## Jak wyeksportować cookies z Chrome:
1. Zainstaluj rozszerzenie: "Get cookies.txt LOCALLY" (Chrome Web Store)
2. Wejdź na youtube.com (zalogowany na swoim koncie)
3. Kliknij rozszerzenie → Export → zapisz jako `youtube_cookies.txt`
4. Skopiuj na VPS:
   ```
   scp youtube_cookies.txt ubuntu@147.224.162.100:/home/ubuntu/video-seo-engine/cookies/
   ```
5. Zrestartuj kontener:
   ```
   docker restart vse-api
   ```

## Ważne
- Cookies wygasają co ~2 tygodnie — odnawiaj regularnie
- Nie commituj pliku cookies.txt do repo!
- Plik jest montowany read-only (:ro) — bezpieczne
```

---

## 📌 ZADANIE 2 — Opcja C Prep: endpoint `/v1/fetch` (lokalny runner)

### Koncepcja architektura hybrydowa

Dla klientów SaaS gdzie VPS nie może fetchować YT:
```
Klient lokalny (Windows/Mac)
   ↓ uruchamia fetcher.py lokalnie
   ↓ pobiera: transkrypt + metadane
   ↓ POST /v1/generate  ← pushuje surowe dane do VSE API
   ↓ VSE API (oracle-crimson)
   ↓ generuje schema (AI)
   ↓ POST /v1/inject → WordPress
```

### Implementacja — nowy endpoint `POST /v1/generate` przyjmuje RAW DATA

Sprawdź czy obecny `/v1/generate` akceptuje już pre-fetched transcript/metadata.
Jeśli nie — dodaj opcjonalne pola do `ProcessRequest`:
```python
class ProcessRequest(BaseModel):
    video_url: str
    # [Opcja C] Pre-fetched data (skip fetch step if provided)
    raw_transcript: str | None = None      # VTT content
    raw_metadata: dict | None = None       # yt-dlp metadata JSON
    site_config: SiteConfig
    options: ProcessOptions
    wp_post_id: int | None = None
```

Logika w `pipeline.py`:
```python
if req.raw_transcript and req.raw_metadata:
    # Opcja C: skip fetch, use provided data
    transcript = req.raw_transcript
    metadata = req.raw_metadata
else:
    # Opcja A: fetch on VPS (requires cookies or open IP)
    transcript, metadata = await fetch_video(video_url, cookies_path)
```

---

## 📌 ZADANIE 3 — End-to-end test `/v1/generate`

**Zacznij od generate (no inject) — bezpieczne:**
```bash
curl -X POST http://147.224.162.100:8085/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://youtube.com/watch?v=VIDEO_ID", "site_config": {...}, "options": {"llm_provider": "claude", "auto_inject": false}}'
```

- Jeśli brak `.env.api` na VPS → STOP, raportuj do stratega
- Jeśli YouTube blokuje nawet z cookies → STOP, raportuj
- Jeśli sukces → test `/v1/process` z `auto_inject: true` + realny `wp_post_id`

---

## 📌 ZADANIE 4 — README checkboxy Fazy 2

Sekcja `🟡 Faza 2` w README.md zamień na:
```markdown
### ✅ Faza 2A — VSE API Service (DONE)
- [x] FastAPI app structure (api/ module) — commit d7a86e79
- [x] Pydantic models — ProcessRequest/Response, SiteConfig
- [x] POST /v1/process — full pipeline endpoint
- [x] POST /v1/generate — schema-only endpoint
- [x] POST /v1/inject — inject-only endpoint
- [x] GET /health — health check ✅ v2.0.0
- [x] Dockerfile.api + docker-compose.vse.yml
- [x] Deployment oracle-crimson :8085 — healthy

### 🟡 Faza 2B — YouTube Unblock + E2E (IN PROGRESS)
- [ ] cookies.txt strategy — fetcher.py + docker volume mount [Opcja A]
- [ ] docs/YOUTUBE_COOKIES.md — instrukcja dla Usera
- [ ] raw_transcript/raw_metadata w ProcessRequest [Opcja C prep]
- [ ] End-to-end test /v1/generate z realnym video
- [ ] End-to-end test /v1/process z realnym prawy.pl post_id
- [ ] POST /v1/monitor/start — Channel Monitor background task
- [ ] POST /v1/sitemap — weryfikacja end-to-end
```

---

## 📌 ZADANIE 5 — Raport

Dual-write po zakończeniu:
1. `video-seo-engine/.agents/reports/2026-06-14_vse-dev-01_faza2b.md`
2. `sonic-void/.agents/reports/inbox/2026-06-14_vse-dev-01_faza2b.md`

Zawrzyj: status każdego zadania, logi z testów, SHA commitów, pending items.

---

## 🔧 Środowisko operacyjne

```bash
# SSH:
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o BatchMode=yes ubuntu@147.224.162.100 "komenda"

# Git pull + rebuild na VPS:
cd /home/ubuntu/video-seo-engine && git pull
docker build -f Dockerfile.api -t vse-api .
docker stop vse-api && docker rm vse-api
docker run -d --name vse-api --env-file .env.api -p 8085:8085 \
  -v /home/ubuntu/video-seo-engine/cookies:/app/cookies:ro vse-api

# Logi:
docker logs vse-api --tail 50
```

---

## ⚠️ STOP-CONDITIONS

| Sytuacja | Akcja |
|----------|-------|
| Brak `.env.api` na VPS | STOP → raport do stratega |
| YouTube blokuje z cookies | STOP → raport (Opcja C full impl.) |
| Disk > 90% | ALERT do Supervisora |
| Test /v1/process nadpisuje istniejący post | STOP → użyj test post_id |

---

*Dispatch v2 (z Opcją C): vse-strateg-01 | 2026-06-14 10:40 | video-seo-engine Faza 2B*
