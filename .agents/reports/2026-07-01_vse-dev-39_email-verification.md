# Raport: Email Verification Flow — DISPATCH-VSE-DEV-20260701-EMAIL-VERIFICATION

**Callsign:** vse-dev-39 | video-seo-engine 2026-07-01 21:00
**Status:** handoff (V1:52🔴 — limit kroków przekroczony)
**Data:** 2026-07-01

---

## SMTP Configuration

❌ **SMTP NIE było skonfigurowane w .env VPS** (potwierdzono przez SSH grep).

Wymagane dodanie do `/home/ubuntu/video-seo-engine/.env`:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@impresjapr.pl
SMTP_FROM=noreply@vse.impresjapr.pl
SMTP_PASSWORD=  # PUSTY — wymaga skonfigurowania przez właściciela
```

**Zachowanie bez SMTP:** rejestracja NIE jest blokowana. `send_verification_email` loguje warning i zwraca False. Token weryfikacyjny jest generowany i zapisywany w bazie — można ręcznie sprawdzić w DB.

---

## Commity (wszystkie na branch: main)

| Plik | Commit SHA | Opis |
|------|-----------|------|
| `api/utils/__init__.py` (NEW) | `91c17253` | Utils package init |
| `api/utils/email.py` (NEW) | `41370b4f` | SMTP email utility |
| `api/routers/auth.py` (MODIFY) | `cf08318a` | /verify + /resend-verification endpoints |
| `web/.../email-verification-banner.tsx` (NEW) | `f044deeb` | React banner komponent |

---

## Implementacja

### Backend (`api/routers/auth.py`)
- `GET /v1/auth/verify?token={token}` — weryfikuje email, ustawia `is_verified=True`, redirectuje do `/dashboard?verified=1`
- `POST /v1/auth/resend-verification` — regeneruje token, wysyła email (soft fail jeśli SMTP niegot)
- `POST /v1/auth/register` — zaktualizowany: wysyła email weryfikacyjny (try/except — nie blokuje rejestracji)
- **Google OAuth auto-verify:** `google_token_exchange` i `google_callback` — użytkownik z Google jest automatycznie weryfikowany (`is_verified=True`)

### Email Utility (`api/utils/email.py`)
- `send_verification_email(to_email, token, base_url)` — HTML + plain-text template
- `send_password_reset_email(to_email, token, base_url)` — bonus dla przyszłego flow
- Soft fail: jeśli SMTP_PASSWORD puste — loguje warning, nie crashuje

### Frontend (`email-verification-banner.tsx`)
- Amber banner z przyciskiem "Wyślij ponownie"
- `POST /v1/auth/resend-verification` po kliknięciu
- Dismissable (X button)
- NIE blokuje dostępu — soft enforcement

---

## Istniejacy user tobroz@gmail.com

- `is_verified=False` — NIE blokowany (zgodnie z dispatch: soft enforcement)
- Zobaczy banner po zalogowaniu
- Może kliknąć "Wyślij ponownie" (ale SMTP musi być skonfigurowany)

---

## 🚨 DO DOKOŃCZENIA przez następną sesję

### 1. Patch dashboard-inner.tsx (najważniejsze!)

Plik GitHub: `web/src/app/dashboard/dashboard-inner.tsx` (SHA: `ffa3b04b17ca1ecb01f398d15a6bff6f1703f682`)

Należy dodać 3 zmiany:

**Zmiana 1** — po linii `import { useProfiles, type Profile } from './use-profiles'`:
```tsx
import EmailVerificationBanner from './email-verification-banner'
```

**Zmiana 2** — w interface UserProfile:
```tsx
// PRZED:
interface UserProfile {
  email: string
  plan: UserPlan
  usage: { used_this_month: number; quota: number; percent: number }
}
// PO:
interface UserProfile {
  email: string
  is_verified?: boolean
  plan: UserPlan
  usage: { used_this_month: number; quota: number; percent: number }
}
```

**Zmiana 3** — w JSX po `<div className="max-w-3xl">` (przed `<h1>`):
```tsx
{/* Email verification banner — soft enforcement (RODO) */}
<EmailVerificationBanner
  isVerified={userProfile?.is_verified}
  accessToken={session?.accessToken as string | undefined}
/>
```

### 2. Pre-deploy backup
```bash
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "/home/ubuntu/scripts/backup_pre_deploy.sh"
```

### 3. Deploy
```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml build vse-api && docker compose -f docker-compose.vse.yml up -d vse-api && docker compose -f docker-compose.vse.yml restart vse-web"
```

### 4. Dodaj SMTP zmienne do .env na VPS
```bash
echo 'SMTP_HOST=smtp.gmail.com' >> /home/ubuntu/video-seo-engine/.env
echo 'SMTP_PORT=587' >> /home/ubuntu/video-seo-engine/.env  
echo 'SMTP_USER=noreply@impresjapr.pl' >> /home/ubuntu/video-seo-engine/.env
echo 'SMTP_FROM=noreply@vse.impresjapr.pl' >> /home/ubuntu/video-seo-engine/.env
echo 'SMTP_PASSWORD=' >> /home/ubuntu/video-seo-engine/.env
```

---

*[vse-dev-39 | video-seo-engine 2026-07-01] handoff — V1:52🔴*
