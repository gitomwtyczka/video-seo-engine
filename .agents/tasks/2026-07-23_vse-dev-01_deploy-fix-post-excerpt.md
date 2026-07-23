# DISPATCH — [vse-dev-01]
## Deploy fix: git pull + rebuild vse-api

---

## ⚡ KROK 0 — Heartbeat

Zapisz heartbeat przez GitHub MCP (pobierz SHA z `get_file_contents` najpierw):
```
repo: video-seo-engine / branch: main / path: .agents/heartbeat.json
callsign: vse-dev-01 | status: working | current_task: deploy git pull + rebuild vse-api
```

---

## ⚠️ PUŁAPKI SSH

| Typ komendy | Metoda |
|---|---|
| Prosta (git pull, docker ps) | SSH inline ✅ |
| Z `$zmiennymi` / zagnieżdżonymi cudzysłowami | `write_to_file` → `scp` → `ssh` ✅ |

Klucz SSH: `C:\Users\tomas2\.ssh\oracle-crimson.key` (pełna ścieżka Windows)
Host: `ubuntu@147.224.162.100`

---

## 🎯 Zadanie

VPS jest 2 commity za `origin/main`. Fix `ab1ce1f` (post_excerpt) nie wylądował. Wykonaj deploy.

### Krok 1 — git pull
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main"
```

### Krok 2 — rebuild + restart vse-api
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && docker compose -f docker-compose.vse.yml build vse-api && docker compose -f docker-compose.vse.yml up -d vse-api"
```

### Krok 3 — weryfikacja (po ~15s)
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker ps --format 'table {{.Names}}\t{{.Status}}' && docker logs vse-api --tail 20 2>&1"
```

### Krok 4 — potwierdź który commit jest teraz na VPS
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git log --oneline -5"
```

---

## 📨 Raport

Krótki raport z wynikami (czy pull się powiódł, czy api wstało, który commit jest na VPS):

1. `video-seo-engine/.agents/reports/2026-07-23_vse-dev-01_deploy-fix-post-excerpt.md`
2. `sonic-void/.agents/reports/inbox/2026-07-23_vse-dev-01_deploy-fix-post-excerpt.md`

Heartbeat na koniec: `status: done`.

---

*Dispatch: [Supervisor 01 | sonic-void 23.07.2026 20:03]*
