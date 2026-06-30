# DISPATCH-VSE-DEV-EMAIL-VERIFICATION

**Zleceniodawca:** arch-analyst-01 | 30.06.2026
**Priorytet:** MEDIUM — potrzebne przed otwarciem rejestracji
**Agent:** vse-dev (Gemini Flash)
**Workspace:** video-seo-engine

---

## Cel

Implementacja email verification flow. Kolumny `verification_token` i `is_verified` już istnieją w modelu User.

## Kroki

1. **POST /v1/auth/register** — po rejestracji generuj `verification_token` (UUID), wyślij email z linkiem
2. **GET /v1/auth/verify?token=XXX** — zweryfikuj token, ustaw `is_verified=True`
3. **Email sending** — SMTP lub transactional (SendGrid/Resend). Najprostsze: SMTP przez Gmail.
4. **Guard** — opcjonalnie: nie pozwól na generate/inject jeśli `is_verified=False`

## Zmienne .env

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@impresjapr.pl
SMTP_PASSWORD=...
VERIFICATION_URL=https://vse.impresjapr.pl/verify
```

## Pre-deploy

⛔ **OBOWIĄZKOWY BACKUP:** `ssh ubuntu@147.224.162.100 "/home/ubuntu/scripts/backup_pre_deploy.sh"`

---
*[arch-analyst-01 | sonic-void 30.06.2026]*
