# DISPATCH-VSE-DEV-20260630-BACKUP-SYSTEM (REWIZJA)

**Zleceniodawca:** arch-analyst-01 | 30.06.2026
**Priorytet:** HIGH — wymagane przed każdym następnym deployem
**Agent:** sup-worker / vse-dev (Gemini Flash)
**Workspace:** video-seo-engine

---

## ⚠️ KROK 0 — Sprawdź istniejący system backupów!

**Z 17.06.2026 istnieje pełny dispatch backupów:** 
`sonic-void/.agents/tasks/sup-worker-backup_pre-integration.md`

**ZANIM cokolwiek tworzysz, sprawdź na VPS co już istnieje:**

```bash
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "\
  echo '=== /home/ubuntu/scripts/ ==='; \
  ls -la /home/ubuntu/scripts/ 2>/dev/null || echo 'brak katalogu'; \
  echo '=== /home/ubuntu/backups/ ==='; \
  ls -la /home/ubuntu/backups/ 2>/dev/null || echo 'brak katalogu'; \
  echo '=== crontab ==='; \
  crontab -l 2>/dev/null || echo 'brak crontab'; \
  echo '=== backup_db.sh content ==='; \
  cat /home/ubuntu/scripts/backup_db.sh 2>/dev/null || echo 'brak pliku'"
```

### Scenariusz A: Skrypty już istnieją

Jeśli `backup_db.sh`, `rollback_vse.sh` itd. już są na VPS:
1. Sprawdź czy `backup_db.sh` zawiera sekcję VSE (`pg_vse`)
2. Jeśli tak — system działa, tylko dodaj deploy gate do AGENTS.md (Krok 5 niżej)
3. Jeśli nie — dodaj sekcję VSE per oryginalny dispatch

### Scenariusz B: Skrypty NIE istnieją

Wdróż pełny system z `sonic-void/.agents/tasks/sup-worker-backup_pre-integration.md`.
Czytaj ten plik przez GitHub MCP:
```
owner: gitomwtyczka | repo: sonic-void | branch: master
path: .agents/tasks/sup-worker-backup_pre-integration.md
```

Wykonaj TASKI 1-5 z tamtego dispatcha. NIE używaj mojego uproszczonego skryptu — oryginał jest pełniejszy (ma rollback scripts, safety backup, health checki).

---

## KROK 5: Deploy gate w AGENTS.md (VSE)

**Niezależnie od scenariusza A/B** — dodaj do `video-seo-engine/AGENTS.md`:

```markdown
## ⛔ MANDATORY PRE-DEPLOY BACKUP
Każdy deploy na VPS MUSI zacząć się od:
```
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "/home/ubuntu/scripts/backup_pre_deploy.sh"
```
Agent NIE MOŻE pominąć tego kroku. Jeśli backup fail → STOP deploy.
```

## Weryfikacja

- [ ] Istniejący backup system zaudytowany (co jest, co brakuje)
- [ ] VSE backup w codziennym cron (jeśli nie był)
- [ ] Deploy gate dodany do AGENTS.md
- [ ] Test run backup scriptów
- [ ] Raport do sonic-void inbox

---
*[arch-analyst-01 | sonic-void 30.06.2026] — REWIZJA: korzystaj z istniejącego dispatcha backupów*
