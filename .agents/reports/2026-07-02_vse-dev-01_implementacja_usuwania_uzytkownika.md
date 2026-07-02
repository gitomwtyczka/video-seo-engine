# Raport z wdrożenia: Usuwanie użytkowników i naprawa webhooków Stripe
**Callsign**: vse-dev-01
**Data**: 2026-07-02
**Status**: Czekam na wdrożenie (Deploy blocked by permission timeout)

## 1. Co zostało zrobione
Zgodnie z zatwierdzonym planem wdrożeniowym zrealizowano implementację obu funkcjonalności:

### A. Bezpieczne usuwanie użytkowników (z kaskadą)
1. **Model Bazy Danych (`api/models/user.py`)**
   - Dodano `cascade="all, delete-orphan"` do relacji `usage_logs`, `api_keys` i `portals`. Dzięki temu usunięcie rekordu w tabeli `users` bezpiecznie usunie powiązane logi i klucze API bez osieroconych rekordów.
2. **API Backend (`api/routers/admin.py`)**
   - Zaimplementowano endpoint `DELETE /v1/admin/users/{user_id}`.
   - Endpoint wywołuje API Stripe w celu anulowania aktywnej subskrypcji (`stripe.Subscription.delete`), przechwytuje potencjalne błędy, a następnie wykonuje operację `db.delete(user)` by usunąć rekord i jego kaskadowe zależności z bazy.
3. **Panel Frontend (`web/src/app/admin/page.tsx`)**
   - Dodano przycisk "Usuń" w tabeli użytkowników (obok zmiany planu).
   - Stworzono nowy komponent modalu z potwierdzeniem `DeleteUserModal`.
   - Zintegrowano operację usuwania z API i lokalnym stanem komponentu (usunięty user od razu znika z listy, a licznik spada).

### B. Naprawa race-condition w webhookach Stripe
1. **API Backend (`api/routers/payments.py`)**
   - W webhooku `customer.subscription.updated` dodano weryfikację pola `status`.
   - Jeśli status subskrypcji nie jest `active` ani `trialing`, system zdejmuje plan z użytkownika (degraduje do `free`) zamiast przydzielać mu nowy plan na podstawie `price_id`. Zapobiega to omyłkowemu przyznawaniu darmowego planu premium gdy subskrypcja wygasa.

## 2. Zmiany w kodzie (Push do repozytorium)
Zmiany zostały zacommitowane i wysłane (push) na branch `main` w repozytorium `video-seo-engine`.
Commit SHA: `2e58c4d19351ca337c9c49a99a196170ae1562ca`
Wiadomość: `feat: usuwanie konta (kasadowe + stripe) oraz fix webhooków downgrade [vse-dev-01]`

## 3. Aktualny problem (Dlaczego wdrożenie nie jest ukończone)
Próba uruchomienia skryptu backupu oraz komend wdrożeniowych (Docker Compose) przez połączenie SSH na serwerze VPS (`147.224.162.100`) **zakończyła się niepowodzeniem z powodu braku zgody użytkownika** (Permission Prompt Timeout). 
Z tego powodu kod znajduje się w repozytorium zdalnym GitHub, lecz **nie jest jeszcze wdrożony na serwer produkcyjny.**

## 4. Dalsze kroki (Do wykonania podczas następnej sesji / przez użytkownika)
Gdy Użytkownik powróci do komputera, należy ręcznie wywołać deploy lub poprosić agenta o ponowienie komend:
1. `ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "/home/ubuntu/scripts/backup_pre_deploy.sh"`
2. `ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml build vse-api && docker compose -f docker-compose.vse.yml up -d vse-api"`
3. `ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml build vse-web && docker compose -f docker-compose.vse.yml up -d vse-web"`