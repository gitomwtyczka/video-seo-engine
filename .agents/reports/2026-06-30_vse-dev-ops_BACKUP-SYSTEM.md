# Raport: Zabezpieczenie systemu backupów VSE (Pre-Deploy Gate)
**Data:** 2026-06-30
**Callsign:** vse-dev-ops

## CO zrobiono
1. Zaudytowano istniejące skrypty backupów na VPS (`147.224.162.100`). System był już wdrożony zgodnie z wytycznymi `sup-worker-backup_pre-integration.md` (z 17.06.2026). W pliku `backup_db.sh` istniała już sekcja dla PostgreSQL VSE.
2. Utworzono wrapper-skrypt `/home/ubuntu/scripts/backup_pre_deploy.sh`, który wywołuje procedurę bezpieczeństwa.
3. Zaktualizowano `AGENTS.md` (deploy gate) wymuszający wywołanie powyzszego skryptu przez każdego agenta implementacyjnego przed wdrażaniem zmian na VPS.
4. Przetestowano wdrożony system wykonując ręczny trigger dumpa i weryfikując proces na produkcji.

## PO CO to zrobiono
Celem nadrzędnym było zautomatyzowanie i wymuszenie backupowania danych VSE w przypadku potencjalnych awarii podczas wdrożeń integracyjnych (VSE <-> SAAS).

## JAK to działa
- Agent przed komendami deployowymi na VPS wykonuje pre-check wywołując `backup_pre_deploy.sh`. 
- Skrypt realizuje zrzut bazodanowy z użyciem `pg_dump`, kompresuje je przez `gzip` i ładuje na zdefiniowaną retencję 7-dniową do `/home/ubuntu/backups/db/`.
- Jeśli deploy gate script fails, agent anuluje kolejne kroki wdrożenia.