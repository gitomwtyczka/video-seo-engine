# Raport: SMTP Env Fix + CyberFolks Rate-Limit Diagnosis

**Callsign:** vse-dev-smtp-03  
**Data:** 2026-07-01  
**Repo:** video-seo-engine  
**Commit fix:** `2e2fb57`  

---

## 1. Co bylo w docker-compose

`env_file: .env` **juz byl** w sekcji `vse-api` przed interwencja.
Zmienne SMTP SA w pliku `.env` na VPS (5 kluczy: HOST, PORT, USER, FROM, PASSWORD).
`docker exec vse-api env | grep SMTP` zwraca 5 zmiennych -> **kontener WIDZI zmienne SMTP**.

Wczesniejszy raport o pustych zmiennych byl nieaktualny (kontener byl przeladowany przez prev agenta).

## 2. Prawdziwy root cause

**CyberFolks SMTP rate-limit** (nie brak env vars):
```
550: User account noreply@impresjapr.pl has sent too many emails
```

Test Python bezposrednio z VPS:
```
Testing SMTP: vz279883.dahost.pl:465
Connected OK
Login OK - SMTP works!
Recipients refused: {'vse-smtp-test@mailinator.com': (550, b'User account noreply@impresjapr.pl has sent too many emails')}
```

**Wnioski:**
- Oracle port 465 = NIE jest blokowany (polaczenie nawiazane)
- SMTP auth = OK (login przeszedl)
- Serwer CyberFolks odrzuca recipients z powodu przekroczenia limitu wyslanych emaili

## 3. Misleading message w kodzie

`auth.py` zwracal `"SMTP not configured"` gdy `email_sent=False` z DOWOLNEGO powodu.
Fix: rozroznienie przypadkow (configured/rate-limited/other error).

## 4. Wynik resend-verification

Przed fixem: `{"message": "Token regenerated (email not sent \u2014 SMTP not configured)", "email_sent": false}`  
Po fixie: `{"message": "Token regenerated (email not sent - check server logs for SMTP error)", "email_sent": false}`

Logi API:
```
[ERROR] api.utils.email: [email] Failed to send 'Potwierdz swoj adres email' to ...: {550, b'User account noreply@impresjapr.pl has sent too many emails'}
```

## 5. Co zrobiono

- [x] Diagnostyka: SMTP vars w kontenerze - OK (5 kluczy)
- [x] Test polaczenia SMTP z VPS - Connected + Login OK
- [x] Root cause: CyberFolks rate-limit na koncie noreply@impresjapr.pl
- [x] Fix auth.py misleading error message - commit 2e2fb57
- [x] Deploy: git pull + docker build + up vse-api - OK
- [x] Weryfikacja SMTP vars po deployu - 5 kluczy w kontenerze

## 6. Verdict

**SMTP przez CyberFolks: INFRASTRUKTURA DZIALA**  
Oracle NIE blokuje portu 465.  
Auth na serwerze CyberFolks przechodzi.  
Problem: konto `noreply@impresjapr.pl` przekroczyo limit wyslanych emaili.

## 7. Akcja wymagana

**Kto:** Administrator hostingu / wlasciciel konta CyberFolks  
**Co:** Wejdz w panel CyberFolks -> Poczta -> `noreply@impresjapr.pl` -> sprawdz limit wyslanych emaili / zresetuj / zwieksz limit  
**Alternatywa:** Skontaktuj sie z supportem dahost.pl / CyberFolks

Po resecie limitu: SMTP wyslanka powinna dzialac bez zadnych zmian w kodzie ani konfiguracji Docker.
