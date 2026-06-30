# DISPATCH-VSE-DEV-BACKUP-SYSTEM

**Zleceniodawca:** arch-analyst-01 | 30.06.2026
**Priorytet:** HIGH — wymagane przed każdym następnym deployem
**Agent:** sup-worker / vse-dev (Gemini Flash)
**Workspace:** video-seo-engine

---

## Cel

Wdrożenie systemu backupów DB na VPS Oracle ARM. Trzy warstwy:
1. Pre-deploy backup script (obowiązkowy)
2. Scheduled backup (cron 3x/dzień, 2-day retention)
3. Deploy gate w AGENTS.md

## Kontekst

Obecnie: brak backupów DB. Rollback = `git reset --hard` (tylko kod). Deploy z migracją DB + crash = utrata danych.

Katalogi już stworzone na VPS:
- `/home/ubuntu/backups/vse/`
- `/home/ubuntu/backups/pressai/`
- `/home/ubuntu/scripts/`

## Kroki

### KROK 1: Stwórz pre-deploy backup script

SSH: `ubuntu@147.224.162.100`
Klucz: `~/.ssh/oracle-crimson.key`

Stwórz plik `/home/ubuntu/scripts/backup_pre_deploy.sh`:
```bash
#!/bin/bash
set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/ubuntu/backups"

# VSE
echo "[⚓] Backup VSE DB..."
docker exec vse-postgres pg_dump -U postgres vse | gzip > $BACKUP_DIR/vse/pre_deploy_$TIMESTAMP.sql.gz
echo "✅ VSE backup: $BACKUP_DIR/vse/pre_deploy_$TIMESTAMP.sql.gz"

# PressAI (jeśli kontener istnieje)
if docker ps --format '{{.Names}}' | grep -q crimson-db; then
    echo "[⚓] Backup PressAI DB..."
    docker exec crimson-db pg_dump -U postgres pressai | gzip > $BACKUP_DIR/pressai/pre_deploy_$TIMESTAMP.sql.gz
    echo "✅ PressAI backup: $BACKUP_DIR/pressai/pre_deploy_$TIMESTAMP.sql.gz"
else
    echo "⚠️ crimson-db not running — skip PressAI backup"
fi

echo "✅ All backups complete: $TIMESTAMP"
```

Następnie: `chmod +x /home/ubuntu/scripts/backup_pre_deploy.sh`

### KROK 2: Stwórz scheduled backup script

Stwórz plik `/home/ubuntu/scripts/backup_scheduled.sh`:
```bash
#!/bin/bash
set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/ubuntu/backups"
RETENTION_DAYS=2

# VSE
if docker ps --format '{{.Names}}' | grep -q vse-postgres; then
    docker exec vse-postgres pg_dump -U postgres vse | gzip > $BACKUP_DIR/vse/scheduled_$TIMESTAMP.sql.gz
    echo "$(date): VSE backup done" >> /var/log/backup_scheduled.log
fi

# PressAI
if docker ps --format '{{.Names}}' | grep -q crimson-db; then
    docker exec crimson-db pg_dump -U postgres pressai | gzip > $BACKUP_DIR/pressai/scheduled_$TIMESTAMP.sql.gz
    echo "$(date): PressAI backup done" >> /var/log/backup_scheduled.log
fi

# Cleanup: usuń starsze niż 2 dni
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "$(date): Cleanup done" >> /var/log/backup_scheduled.log
```

Następnie: `chmod +x /home/ubuntu/scripts/backup_scheduled.sh`

### KROK 3: Ustaw cron

```bash
(crontab -l 2>/dev/null; echo '0 */8 * * * /home/ubuntu/scripts/backup_scheduled.sh') | crontab -
```

Weryfikacja: `crontab -l`

### KROK 4: Test

```bash
/home/ubuntu/scripts/backup_pre_deploy.sh
ls -la /home/ubuntu/backups/vse/
```

### KROK 5: Deploy gate w AGENTS.md (VSE)

GitHub MCP → `video-seo-engine/AGENTS.md` — dodaj sekcję:
```markdown
## ⛔ MANDATORY PRE-DEPLOY BACKUP
Każdy deploy na VPS MUSI zacząć się od:
```
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "/home/ubuntu/scripts/backup_pre_deploy.sh"
```
Agent NIE MOŻE pominąć tego kroku. Jeśli backup fail → STOP deploy.
```

## Weryfikacja

- [ ] `backup_pre_deploy.sh` działa (test run)
- [ ] `backup_scheduled.sh` działa (test run)
- [ ] cron jest ustawiony (`crontab -l`)
- [ ] AGENTS.md zaktualizowany
- [ ] Raport do sonic-void inbox

---
*[arch-analyst-01 | sonic-void 30.06.2026]*
