# Dispatch: Wdrożenie Fazy 3 (YT OAuth & Fernet Encryption)
**Data:** 2026-07-10
**Dla:** vse-dev-ops / Worker
**Od:** Supervisor (vse-strateg-01)

## 📌 Cel zadania
Przeprowadzenie czystego wdrożenia produkcyjnego Fazy 3 (Integracja wielu kanałów YT OAuth i szyfrowanie tokenów Fernet) na serwer VPS. Kod czeka na branchu `main`.

## 🛠️ Kroki do wykonania
1. Zaloguj się przez SSH i sprawdź zawartość pliku `.env` na VPS (`/home/ubuntu/video-seo-engine/.env`). Jeśli nie ma tam klucza `ENCRYPTION_KEY`, musisz go wygenerować (z użyciem modułu kryptografii) i dopisać do pliku, INACZEJ SYSTEM WYKRZACZY SIĘ po restarcie API.
2. Obowiązkowy pre-deploy Backup: `ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "/home/ubuntu/scripts/backup_pre_deploy.sh"` (Przerwij procedurę jeśli wyrzuci błąd!)
3. Pull najnowszego kodu: `git pull origin main` na serwerze w `/home/ubuntu/video-seo-engine`.
4. Twardy rebuild i restart kontenerów: `docker compose -f docker-compose.vse.yml build && docker compose -f docker-compose.vse.yml up -d`.
5. Migracja bazy danych (Alembic): `docker exec vse-api alembic upgrade head`.
6. Zweryfikuj logi i zaraportuj poprawność wdrożenia do Supervisora (`.agents/reports/inbox/`).

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)
1. GitHub MCP: po create_or_update_file ZAWSZE zweryfikuj newlines.
2. SSH: NIE buduj złożonych komend inline — write_to_file → scp → ssh (jeśli zachodzi potrzeba pisania skryptów).
3. Używaj poprawnej flagi dla nienadzorowanego połączenia z VPS: `-o StrictHostKeyChecking=no`.
4. Uważaj na brak `ENCRYPTION_KEY` — sprawdź jego istnienie na VPS jako Twój najwyższy priorytet przed rebuildem, ponieważ bez niego nowa migracja połączona ze zmianami w logice modeli nie zadziała, rzucając błąd braku klucza Fernet!