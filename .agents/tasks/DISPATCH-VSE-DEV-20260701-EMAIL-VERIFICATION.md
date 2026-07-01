# DISPATCH: VSE-DEV-20260701 — Email Verification Flow

**Zlecenie od:** Supervisor 02 (sonic-void)
**Data:** 2026-07-01
**Priorytet:** Sredni-wysoki — wymaganie prawne RODO przed komercjalizacja
**Estymacja:** 1 dzien

## Problem

Model User ma pole verification_token i is_verified, ale flow weryfikacji emaila nie istnieje:
- Przy rejestracji: brak wysylania emaila z tokenem
- Brak endpointu GET /v1/auth/verify?token=...
- User moze logowac sie bez weryfikacji emaila

## Co zaimplementowac

### Krok 1: Infrastruktura SMTP

Sprawdz api/.env lub docker-compose.yml czy sa zmienne SMTP. Jesli nie — dodaj do .env:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@impresjapr.pl
SMTP_PASSWORD=...
SMTP_FROM=noreply@vse.impresjapr.pl
```

Utwoz api/utils/email.py z funkcja send_verification_email(to_email, token, base_url).

### Krok 2: Modyfikacja rejestracji

W api/routers/auth.py (endpoint POST /v1/auth/register):
- Wygeneruj verification_token = secrets.token_urlsafe(32)
- Zapisz do user.verification_token
- Wywolaj send_verification_email
- Zwroc 201 z info ze email weryfikacyjny zostal wyslany

### Krok 3: Endpoint weryfikacji

GET /v1/auth/verify?token=... — znajdz usera po tokenie, ustaw is_verified=True, wyczysc token, redirect do /dashboard?verified=1

### Krok 4: Frontend (soft enforcement)

Na /dashboard jesli user.is_verified == False: pokaz banner "Zweryfikuj email". NIE blokuj dostepu — soft enforcement aby nie zablokowac obecnych uzytkownikow.

Dodaj przycisk "Wyslij ponownie" → POST /v1/auth/resend-verification

### Krok 5: Google OAuth auto-verify

Google OAuth users powinni byc auto-verified (google_id != null powinno ustawiac is_verified=True przy pierwszym logowaniu).

## ZNANE PULAPKI
1. Istniejacy uzytkownik tobroz@gmail.com ma is_verified=False — NIE blokuj go
2. Google OAuth users — auto-verify przez google_id != null
3. SSH user: ubuntu (NIE root)
4. SMTP credentials — jesli nie ma w .env, zaraportuj do Supervisora
5. Sprawdz jak konfiguracja (settings) jest zarzadzana w projekcie przed dodaniem nowych zmiennych

## Deployment

1. Commit przez GitHub MCP
2. SSH: git pull && docker compose up -d --build vse-api
3. Test: sprawdz logi API czy email zostal wyslany przy rejestracji

## Raport koncowy
- Czy SMTP byl skonfigurowany (co znalazles w .env)
- Commit SHA
- Wynik testu rejestracji
- Czy Google OAuth users sa obsluzeni
