# POBUDKA — vse-dev-04 | Local Transcript Windows Service

**Data:** 2026-06-15  
**Dla:** `vse-dev-04`  
**Wystawia:** Supervisor 01

---

## Stan projektu na start

Jesteś agentem `vse-dev-04` wcielanym do projektu `video-seo-engine`.

**Co jest gotowe (nie rób tego ponownie):**
- ✅ Google OAuth działa na produkcji (`/api/auth/providers` → google OK)
- ✅ `wp_post_id` jest opcjonalne w `InjectRequest` (DEV-04 gotowe w kodzie, ale `vse-api` wymaga rebuildu)
- ✅ YouTube Data API v3 działa (metadata OK)
- ✅ `docs/architecture.md` zaktualizowane — przeczytaj to jako **pierwsze** (sekcja 12 opisuje to co implementujesz)
- ✅ VPS: oracle-crimson (147.224.162.100), SSH przez `oracle-crimson.key`

**Co jest problemem (to Twoje zadanie):**
- ❌ `youtube-transcript-api` zablokowana z Oracle Cloud IP — YouTube ban data center
- ❌ Pipeline nie działa bez transkryptu (Claude nie ma danych wejściowych)

**Rozwiązanie (Twoje zadanie):** Local Transcript Runner jako Windows Service.

---

## Twoje pierwsze kroki

1. Przeczytaj przez GitHub MCP:
   - `docs/architecture.md` (sekcja 12 + pipeline diagram sekcja 6)
   - `.agents/tasks/DISPATCH-VSE-DEV-04-20260615-LOCAL-SERVICE.md` (pełna spec)
   - `.agents/tasks/SUPPLEMENT-VSE-DEV-04-20260615-SECURITY.md` (ten plik — security requirements!)

2. Wyślij heartbeat.

3. Implementuj w kolejności z dispatchu.

---

## Krytyczne wiadomości dla tego zadania

### ⚠️ OBOWIĄZEK: Przeczytaj Security Supplement przed implementacją

Plik: `.agents/tasks/SUPPLEMENT-VSE-DEV-04-20260615-SECURITY.md`

Zawiera wymagania bezpieczeństwa które **muszą być zaimplementowane** — szczególnie:
- Sanitizacja transkryptu przed przekazaniem do Claude
- Walidacja job ownership w endpointach
- Rate limiting na `/v1/jobs/pending`

### ⚠️ Rebuild `vse-api` jest wymagany

Kod `wp_post_id` optional jest w repo (commity 3b062f3, 4149f98, e482d64), ale kontener na VPS ma stary obraz.
Rebuild `vse-api` jest częścią tego dispatchu (krok 8):
```
docker compose -f docker-compose.vse.yml build vse-api && \
docker compose -f docker-compose.vse.yml up -d --no-deps --force-recreate vse-api
```

### Dostęp do VPS

SSH przez run_command (lokalny PC):
```powershell
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "komenda"
```
.env żyje w: `/home/ubuntu/vse/.env`

---

## Raportowanie po zakończeniu

Dual-write:
1. `video-seo-engine/.agents/reports/2026-06-15_vse-dev-04_local-service.md`
2. `sonic-void/.agents/reports/inbox/2026-06-15_vse-dev-04_local-service.md`

W raporcie podaj:
- SHA commitów
- Wynik testu end-to-end (URL → pipeline z Local Runner → transkrypt pobrany)
- Wersja tokenu (czy wygenerowany)
- Status `VSELocalRunner` service na PC

---

*Supervisor 01 | sonic-void | 2026-06-15 23:47*
