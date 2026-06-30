# Raport / Zapytanie: Rozbieżność zakresu Pre-Deploy Backup
**Data:** 2026-06-30
**Callsign:** vse-dev-ops

## Co mamy aktualnie
Podczas wdrażania procedury **Mandatory Pre-Deploy Backup**, utworzyłem skrypt `backup_pre_deploy.sh`, który wywołuje cronowy zrzut `backup_db.sh`. 
Obecnie system wykonuje błyskawiczne zrzuty bazodanowe (PostgreSQL dla VSE/SAAS oraz SQLite) przed każdym deployem. *(Uwaga poboczna: ogromny zrzut crawlera 3.3 GB z powodzeniem odseparowaliśmy na cykl tygodniowy).*

## Co chcemy / Zidentyfikowany problem
Właściciel projektu słusznie zauważył, że obecna bramka pominęła kluczowe elementy z Twojego oryginalnego dispatcha `sup-worker-backup_pre-integration.md` z 17.06.2026. 

Rozbudowany system z 17.06 (skrypt `pre_integration_snapshot.sh`) zabezpieczał dodatkowo:
1. Stan HEAD z Git (VSE i SAAS) — niezbędny by wiedzieć do czego cofać kod.
2. Zabezpieczone pliki środowiskowe `.env` — które agenci potrafią losowo uszkodzić.

## Pytanie do Supervisora
Oryginalny pełny snapshot był w zamyśle jednorazową procedurą przed startem wielkiej integracji. Z kolei `backup_db.sh` był pomyślany pod codzienne zrzuty.
Z perspektywy utrzymaniowej skopiowanie `.env` i zapisanie git SHAs wydłuża deploy-gate o dosłownie ułamek sekundy, a drastycznie podnosi bezpieczeństwo. 

Czy autoryzujesz przeniesienie tych funkcjonalności (`.env` + git SHA) z `pre_integration_snapshot.sh` prosto do wywoływanego przez nas przed kodowaniem `backup_pre_deploy.sh`? Czekamy na zielone światło na taką implementację.