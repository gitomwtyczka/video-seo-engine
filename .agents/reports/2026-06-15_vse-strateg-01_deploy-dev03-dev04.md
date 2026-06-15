# Deploy Report: DEV-03 + DEV-04
**Agent:** vse-strateg-01  
**Data:** 2026-06-15  
**Środowisko:** oracle-crimson (147.224.162.100)  
**Commit wdrożony:** b4d0909

---

## Status wykonania

### ✅ Krok 1 — Git pull
- `git fetch origin main && git reset --hard origin/main`
- HEAD: `b4d0909` — heartbeat: vse-strateg-01 P2 DONE
- Zakres: `34e2f91..b4d0909`

### ✅ Krok 2 — Docker build vse-web
- `docker compose -f docker-compose.vse.yml build vse-web`
- Build z cache — wszystkie warstwy CACHED, nowy manifest SHA wyeksportowany
- Image: `video-seo-engine-vse-web:latest`

### ✅ Krok 3 — Restart vse-web
- `docker compose -f docker-compose.vse.yml up -d --no-deps --force-recreate vse-web`
- Container: `vse-web` → Recreated → Started
- Uptime: ~1 min (zdrowy)

---

## Weryfikacja

### ✅ Endpoint 1 — Google OAuth
```
curl https://vse.impresjapr.pl/api/auth/providers
```
**Wynik:**
```json
{"google":{"id":"google","name":"Google","type":"oauth","signinUrl":"https://vse.impresjapr.pl/api/auth/signin/google","callbackUrl":"https://vse.impresjapr.pl/api/auth/callback/google"},"credentials":{...}}
```
✅ Klucz `"google"` obecny — OAuth aktywny.

### ⚠️ Endpoint 2 — wp_post_id optional w InjectRequest

**Oczekiwane:** `wp_post_id` jako optional w `InjectRequest`  
**Faktyczny stan (openapi.json z vse-api):**
```json
"InjectRequest": {
  "required": ["wp_post_id", "video_url", "schema_data", "site_config"]
}
```
`wp_post_id` nadal figuruje jako **required** w działającym kontenerze `vse-api`.

**Przyczyna:** Kontener `vse-api` NIE był przebudowywany (dispatch: "nie rebuild api").  
Kod w repo (`api/models/request.py`) jest **poprawny** — `wp_post_id: Optional[int] = None` — ale kontener ma stary obraz.

---

## Bloker — wymagana decyzja

**Pytanie do Supervisora:**  
Czy wykonać `docker compose -f docker-compose.vse.yml build vse-api && docker compose ... up -d --no-deps --force-recreate vse-api`?

**Ryzyko:** Restart vse-api przerywa aktywne przetwarzanie. Czas rebuild: ~2-5 min.  
**Brak działania:** Weryfikacja DEV-04 niemożliwa. Dokumentacja vs. zachowanie są rozbieżne.

---

## Stan kontenerów po deploy

```
vse-api      UP 6h+    port 8085
vse-postgres UP 31h    port 5434
vse-web      UP ~1min  port 3001  ← właśnie odświeżony
```

**Serwis publiczny:** https://vse.impresjapr.pl — ONLINE
