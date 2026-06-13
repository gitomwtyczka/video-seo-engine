# DISPATCH — vse-dev-01
# Zadanie: VSE Faza 2 — FastAPI multi-tenant service
# Data: 2026-06-13
# Od: vse-strateg-01

---

## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

```
[vse-dev-01 | video-seo-engine DD.MM.YYYY HH:MM] online
```

Heartbeat:
```bash
# Zaktualizuj .agents/heartbeat.json przez GitHub MCP
```

---

## 🎯 Cel

Zaimplementuj VSE jako samodzielny serwis **FastAPI** na oracle-crimson.
Serwis obsługuje wiele portali (multi-tenant, stateless).
Port: **:8085**. Deployment: Docker.

---

## 📊 Kontekst z recon (2026-06-13 23:19)

### oracle-crimson — aktywne kontenery
```
crimson-nginx    :80/:443    # nginx reverse proxy
crimson-backend  :8001       # FastAPI (WZORUJ się na tej strukturze!)
crimson-frontend :3000
prawy-wordpress  :8081
app-muzeum       :8082
academy-app      :8083
lekki-szlak-web  :8084
```

**VSE = :8085** — następny wolny port.

### ANTHROPIC_API_KEY na VPS
- Ścieżka: `/home/ubuntu/crimson-void/backend/.env.production`
- Skopiuj wartość do `/home/ubuntu/vse-api/.env` (NIE linkuj pliku!)

### crimson-backend jako wzór
- Pobierz przez SSH: `cat /home/ubuntu/crimson-void/backend/main.py`
- Wzoruj się na strukturze Dockerfile + compose z tego projektu

---

## 📁 Struktura do stworzenia w repo

```
video-seo-engine/
├── api/
│   ├── __init__.py
│   ├── main.py               # FastAPI app + lifespan + logging
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── process.py        # POST /v1/process — PRIORYTET 1
│   │   ├── generate.py       # POST /v1/generate
│   │   ├── inject.py         # POST /v1/inject
│   │   ├── monitor.py        # POST /v1/monitor/start (background task)
│   │   └── sitemap.py        # POST /v1/sitemap
│   ├── models/
│   │   ├── __init__.py
│   │   ├── request.py        # Pydantic input models
│   │   └── response.py       # Pydantic output models
│   └── services/
│       ├── __init__.py
└─────   └── pipeline.py       # Orchestracja core/ dla API
├── Dockerfile.api
├── docker-compose.vse.yml
└── .env.api.example
```

---

## 📝 Implementacja krok po kroku

### KROK 1 — Pydantic Models (api/models/)

**api/models/request.py:**
```python
from pydantic import BaseModel, HttpUrl
from typing import Optional

class SiteConfig(BaseModel):
    wp_base_url: str
    wp_user: str
    wp_app_password: str

class ProcessOptions(BaseModel):
    auto_inject: bool = True
    update_youtube: bool = False
    llm_provider: str = "claude"  # "claude" | "gemini"

class ProcessRequest(BaseModel):
    video_url: str
    site_config: SiteConfig
    options: ProcessOptions = ProcessOptions()

class GenerateRequest(BaseModel):
    video_url: str
    llm_provider: str = "claude"

class InjectRequest(BaseModel):
    wp_post_id: int
    schema_json: dict
    site_config: SiteConfig

class MonitorStartRequest(BaseModel):
    channel_id: str
    site_config: SiteConfig
    check_interval_min: int = 60

class SitemapRequest(BaseModel):
    site_config: SiteConfig
    output_path: Optional[str] = None
```

**api/models/response.py:**
```python
from pydantic import BaseModel
from typing import Optional

class ProcessResponse(BaseModel):
    status: str
    video_id: str
    wp_post_id: Optional[int] = None
    schema_generated: bool = False
    injected: bool = False
    youtube_updated: bool = False
    processing_time_s: float = 0.0
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    llm_default: str
```

---

### KROK 2 — Pipeline Service (api/services/pipeline.py)

Orchestrate istniejących modułów core/:
```python
import time
import logging
from core.fetcher import fetch_video_data
from core.matcher import match_post_to_video
from core.generator import generate_schema
from core.injector import inject_to_wordpress

logger = logging.getLogger(__name__)

async def process_video(
    video_url: str,
    site_config: dict,
    options: dict
) -> dict:
    """Główna orkiestracja pipeline VSE dla jednego wideo."""
    start = time.time()
    # 1. Fetch
    # 2. Match WP post
    # 3. Generate schema
    # 4. Inject (if auto_inject)
    # 5. YouTube update (if update_youtube)
    # return ProcessResponse
```

**UWAGA:** core/ funkcje są synchroniczne. Użyj `asyncio.to_thread()` do ich wywołania z async context.

---

### KROK 3 — Router process.py (api/routers/process.py)

```python
from fastapi import APIRouter
from api.models.request import ProcessRequest
from api.models.response import ProcessResponse
from api.services.pipeline import process_video
import logging

router = APIRouter(prefix="/v1", tags=["process"])
logger = logging.getLogger(__name__)

@router.post("/process", response_model=ProcessResponse)
async def process_endpoint(req: ProcessRequest):
    """Pełny pipeline: fetch + generate schema + inject do WP."""
    ...
```

**Analogicznie generate.py, inject.py** (prostsze — jednotasowe).

---

### KROK 4 — FastAPI Main (api/main.py)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from api.routers import process, generate, inject, monitor, sitemap
from api.models.response import HealthResponse

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="VSE API",
    description="PressAI Video SEO Engine — multi-tenant",
    version="2.0.0"
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for router in [process.router, generate.router, inject.router, monitor.router, sitemap.router]:
    app.include_router(router)

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        version="2.0.0",
        llm_default=os.getenv("DEFAULT_LLM_PROVIDER", "claude")
    )
```

---

### KROK 5 — Dockerfile.api

Oparty na crimson-backend Dockerfile (Python 3.11-slim, multi-stage):

```dockerfile
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
EXPOSE 8085
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8085", "--workers", "2"]
```

---

### KROK 6 — docker-compose.vse.yml

```yaml
version: '3.8'
services:
  vse-api:
    build:
      context: .
      dockerfile: Dockerfile.api
    container_name: vse-api
    ports:
      - "8085:8085"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8085/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

### KROK 7 — .env.api.example

```bash
# VSE API — .env template
# NIGDY nie commituj wypełnionej wersji!
ANTHROPIC_API_KEY=sk-ant-api03-...
GEMINI_API_KEY=AIza...
DEFAULT_LLM_PROVIDER=claude
LOG_LEVEL=INFO
```

---

### KROK 8 — Deployment na oracle-crimson

Komendy SSH (w tej kolejności):

```bash
# 1. Git pull na VPS
ssh oracle-crimson "cd /home/ubuntu/video-seo-engine && git pull origin main"

# 2. Stwórz .env na VPS
# Pobierz wartość ANTHROPIC_API_KEY z crimson-backend .env.production
# Zapisz do /home/ubuntu/video-seo-engine/.env

# 3. Build + start
ssh oracle-crimson "cd /home/ubuntu/video-seo-engine && docker compose -f docker-compose.vse.yml up -d --build"

# 4. Health check
ssh oracle-crimson "curl -s http://localhost:8085/health"
```

**UWAGA:** Sprawdź czy repo istnieje na VPS:
```bash
ssh oracle-crimson "ls /home/ubuntu/video-seo-engine/"
```
Jeśli nie: `git clone git@github.com:gitomwtyczka/video-seo-engine.git /home/ubuntu/video-seo-engine`

---

## ⚠️ ZNANE PROBLEMY DO OBSERWACJI

1. **requirements.txt SDK mismatch** — `google-generativeai` vs `google-genai`.
   - Przed deploymentem sprawdź: `cat requirements.txt | grep google`
   - Jeśli jest `google-generativeai`, zamień na `google-genai>=0.8.0`

2. **asyncio.to_thread()** — core/ funkcje są synchroniczne, FastAPI async.
   - Użyj `await asyncio.to_thread(sync_func, args)` w routerach.

3. **OAuth YouTube** — na MVP `update_youtube=False` domyślnie.
   - Token OAuth jest lokalnie. Na VPS trzeba będzie refreshnąć lub przenieść credentials.

---

## 📝 Priorytet implementacji

1. **[MUST]** api/ struktura + models + /health endpoint — weryfikacja buildability
2. **[MUST]** /v1/generate — core generate_schema wrapped w async
3. **[MUST]** /v1/process (bez auto_inject najpierw) — full pipeline test
4. **[MUST]** Dockerfile.api + docker-compose.vse.yml
5. **[MUST]** Deployment na VPS + health check OK
6. **[SHOULD]** /v1/inject standalone
7. **[COULD]** /v1/monitor/start (background task)
8. **[COULD]** /v1/sitemap

---

## 📊 Testy

Po każdym kroku:
```bash
# lokalnie (Windows):
uvicorn api.main:app --reload --port 8085
curl http://localhost:8085/health

# Na VPS:
curl http://147.224.162.100:8085/health
```

Test /v1/generate:
```bash
curl -X POST http://localhost:8085/v1/generate \
  -H 'Content-Type: application/json' \
  -d '{"video_url": "https://www.youtube.com/watch?v=4Paw-4FYPLA", "llm_provider": "claude"}'
```

---

## 📢 Raport po wykonaniu

Dual-write:
1. `video-seo-engine/.agents/reports/2026-06-13_vse-dev-01_faza2-impl.md`
2. `sonic-void/.agents/reports/inbox/2026-06-13_vse-dev-01_faza2-impl.md`

Heartbeat z `"status": "done"` + `last_completed[]` z commit SHA.

---

*Dispatch wysłany przez vse-strateg-01 | 2026-06-13T23:22:00+02:00*
