# DISPATCH — vse-strateg-01
# Zadanie: Faza 2 — deployment VSE jako serwis multi-tenant na oracle-crimson
# Data: 2026-06-13

---

## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

### 0a. Przedstaw się + Vitals

```
[vse-strateg-01 | video-seo-engine DD.MM.YYYY HH:MM] 📊 V1:0/40 🟢 V2:1str 🟢 V3:0pl 🟢 V4:stabilny V5:ok — online
```

Vitals aktualizuj co 3-5 kroków. Każda wiadomość MUSI zaczynać się i kończyć callsignem + vitals w jednej linii.

### 0b. Heartbeat
```bash
echo '{"callsign":"vse-strateg-01","status":"working","current_task":"VSE Faza 2 planning","timestamp":"'$(date -Iseconds)'"}' > .agents/heartbeat.json
```

### 0c. Środowisko operacyjne — AKTUALNE

> ⚠️ stellar-relay DEPRECATED. run_command dostępny natywnie.

**SSH do oracle-crimson:**
```bash
run_command: ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o BatchMode=yes ubuntu@147.224.162.100 "komenda"
```

**Wetty fallback:** https://95-179-201-157.sslip.io/ (impresja/ImpresjaWetty2026, root/Ku56Pa78)

**ANTHROPIC_API_KEY:** aktywny na oracle-crimson w /home/ubuntu/crimson-void/backend/.env.production
Lokalnie Windows: C:\Users\tomas2\.impresja\secrets\shared.env (sk-ant...)

---

## 🎯 Twoja rola

**Strateg** = produkujesz dispatch dla vse-dev-01. NIE implementujesz sam.
Analiza -> decyzja -> dispatch -> czekaj na raport.

---

## 📋 Stan z poprzedniej sesji (2026-06-13)

### Co już działa (pipeline lokalny)
- Generator v5.4 z prompt yt_title formaty A/B/C/D (commit 15758e9f)
- Claude Sonnet jako LLM_PROVIDER
- inject_video + update_video_title_and_description wdrożone
- 4 filmy przetworzone (WordPress + YouTube: opisy, tytuły, timestampy)
- OAuth YouTube (prawypl5@gmail.com) — token aktywny
- Channel Monitor (monitor.py) — gotowy
- RankMath integration — gotowy

### Co jest na oracle-crimson
```
Kontenery:
- prawy-wordpress :8081 (prawy.pl tutaj!)
- prawy-mysql 3306
- crimson-backend :8001 (ANTHROPIC_API_KEY tu jest)
- crimson-frontend :3000
- Brak kontenera VSE
```

### Strategia (decyzja Supervisora)
VSE = platforma multi-tenant, nie projekt dedykowany prawy.pl.
Faza 2 = samodzielny serwis VSE na oracle-crimson:
- Przyjmuje: (site_url, youtube_channel_id, filmy do przetworzenia)
- Zwraca: przetworzone SEO JSONy, opcjonalnie auto-inject do WP + YT
- Interfejs: FastAPI (wzoruj na crimson-backend)

---

## 📌 Twoje zadania

### 1. Zbadaj stan oracle-crimson
```bash
ssh oracle-crimson "docker ps && du -sh /home/ubuntu && df -h"
```

### 2. Sprawdź aktualny stan repo i roadmap
```
mcp_github_get_file_contents:
  repo: video-seo-engine
  path: README.md
  branch: main
```

### 3. Zaprojektuj architekturę Fazy 2
Określ:
- Struktura serwisu FastAPI
- Endpoints (priorytety)
- Jak obsuguje multi-tenant (per-site config)
- Docker compose snippet
- ANTHROPIC_API_KEY mount (z crimson-backend lub osobny .env)

### 4. Zaktualizuj roadmap w README
Dodaj Fazę 2 z konkretnymi checkboxami.

### 5. Dispatch vse-dev-01
Gotowy prompt z pełną specą implementacji.

---

## 📢 Raport do Supervisora

Dual-write po zakończeniu:
1. video-seo-engine/.agents/reports/2026-06-13_vse-strateg-01_faza2-plan.md
2. sonic-void/.agents/reports/inbox/2026-06-13_vse-strateg-01_faza2-plan.md

---

Po zakończeniu wróć do Supervisora w sonic-void i powiedz "gotowe — vse-strateg-01".
