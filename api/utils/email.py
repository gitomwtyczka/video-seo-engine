"""
CO: Email utility — wysyłanie emaili transakcyjnych (weryfikacja, reset hasła).

PO CO: Rejestracja użytkownika wymaga weryfikacji emaila (RODO).
        Serwis wysyła email z tokenem do potwierdzenia konta.
        Jeśli SMTP nie jest skonfigurowany — loguje ostrzeżenie, NIE crasha.

JAK: Używa smtplib ze standardowej biblioteki Python (TLS/STARTTLS).
     Konfiguracja przez zmienne środowiskowe:
       SMTP_HOST     (domyślnie: smtp.gmail.com)
       SMTP_PORT     (domyślnie: 587)
       SMTP_USER     (np. noreply@impresjapr.pl)
       SMTP_PASSWORD (wymagane do wysyłania — jeśli puste, tryb dry-run)
       SMTP_FROM     (np. noreply@vse.impresjapr.pl)
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)


def _is_smtp_configured() -> bool:
    """Return True if SMTP credentials are fully configured."""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def _send_email(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    """
    Internal SMTP sender.

    Returns True on success, False on failure.
    Never raises — all exceptions are caught and logged.
    """
    if not _is_smtp_configured():
        logger.warning(
            "[email] SMTP not configured (SMTP_PASSWORD empty). "
            "Would send to=%s subject='%s'",
            to_email,
            subject,
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_FROM or SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Port 465 = SSL/TLS (SMTP_SSL), port 587 = STARTTLS
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM or SMTP_USER, to_email, msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM or SMTP_USER, to_email, msg.as_string())

        logger.info("[email] Sent '%s' to %s", subject, to_email)
        return True

    except Exception as exc:  # noqa: BLE001
        logger.error("[email] Failed to send '%s' to %s: %s", subject, to_email, exc)
        return False


def send_verification_email(to_email: str, token: str, base_url: str) -> bool:
    """
    CO: Wysyła email weryfikacyjny z linkiem potwierdzającym konto.

    PO CO: Spełnia wymogi RODO — użytkownik musi potwierdzić adres email.

    JAK: Generuje link verify_url na podstawie base_url + token.
         Wysyła HTML + plain-text (fallback) przez SMTP.
         Jeśli SMTP nie skonfigurowany — loguje warning i zwraca False.

    Args:
        to_email: Adres odbiorcy.
        token: Token weryfikacyjny (secrets.token_urlsafe(32)).
        base_url: Base URL aplikacji (np. https://vse.impresjapr.pl).

    Returns:
        True jeśli email wysłany, False jeśli SMTP nie skonfigurowany lub błąd.
    """
    verify_url = f"{base_url.rstrip('/')}/v1/auth/verify?token={token}"

    subject = "Potwierdź swój adres email — Video SEO Engine"

    html_body = f"""
<!DOCTYPE html>
<html lang="pl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f1a; color: #e2e8f0; margin: 0; padding: 0;">
  <div style="max-width: 560px; margin: 40px auto; background: #1a1a2e; border: 1px solid #2d2d44; border-radius: 16px; overflow: hidden;">
    <div style="background: linear-gradient(135deg, #7c3aed, #a855f7); padding: 32px; text-align: center;">
      <h1 style="color: #fff; margin: 0; font-size: 24px; font-weight: 700;">Video SEO Engine</h1>
      <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0; font-size: 14px;">Weryfikacja konta</p>
    </div>
    <div style="padding: 40px 32px;">
      <h2 style="color: #e2e8f0; font-size: 20px; margin: 0 0 16px;">Potwierdź swój adres email</h2>
      <p style="color: #94a3b8; font-size: 15px; line-height: 1.6; margin: 0 0 24px;">
        Dziękujemy za rejestrję! Kliknij poniższy przycisk, aby potwierdzić swój adres email i aktywować konto.
      </p>
      <div style="text-align: center; margin: 32px 0;">
        <a href="{verify_url}"
           style="display: inline-block; background: linear-gradient(135deg, #7c3aed, #a855f7);
                  color: #fff; text-decoration: none; font-size: 16px; font-weight: 600;
                  padding: 14px 32px; border-radius: 10px; letter-spacing: 0.025em;">
          ✓ Potwierdź email
        </a>
      </div>
      <p style="color: #64748b; font-size: 13px; line-height: 1.5;">
        Jeśli nie rejestrowałeś(-aś) się w Video SEO Engine, zignoruj tę wiadomość.
      </p>
      <div style="margin-top: 24px; padding-top: 24px; border-top: 1px solid #2d2d44;">
        <p style="color: #64748b; font-size: 12px; margin: 0;">
          Link do weryfikacji:
          <a href="{verify_url}" style="color: #a855f7; word-break: break-all;">{verify_url}</a>
        </p>
      </div>
    </div>
  </div>
</body>
</html>
"""

    text_body = f"""Potwierdź swój adres email — Video SEO Engine

Dziękujemy za rejestrjcję!

Kliknij poniższy link, aby potwierdzić swój adres email:
{verify_url}

Jeśli nie rejestrowałeś(-aś) się w Video SEO Engine, zignoruj tę wiadomość.
"""

    return _send_email(to_email, subject, html_body, text_body)


def send_password_reset_email(to_email: str, token: str, base_url: str) -> bool:
    """
    CO: Wysyła email z linkiem do resetowania hasła.

    PO CO: Umożliwia odzyskanie dostępu do konta bez kontaktu z supportem.

    JAK: Generuje link reset_url i wysyła przez SMTP (analogicznie jak weryfikacja).

    Args:
        to_email: Adres odbiorcy.
        token: Token resetowania hasła.
        base_url: Base URL aplikacji.

    Returns:
        True jeśli email wysłany, False jeśli błąd.
    """
    reset_url = f"{base_url.rstrip('/')}/reset-password?token={token}"

    subject = "Reset hasła — Video SEO Engine"

    html_body = f"""
<!DOCTYPE html>
<html lang="pl">
<head><meta charset="UTF-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f1a; color: #e2e8f0; margin: 0; padding: 0;">
  <div style="max-width: 560px; margin: 40px auto; background: #1a1a2e; border: 1px solid #2d2d44; border-radius: 16px; overflow: hidden;">
    <div style="background: linear-gradient(135deg, #7c3aed, #a855f7); padding: 32px; text-align: center;">
      <h1 style="color: #fff; margin: 0; font-size: 24px;">Video SEO Engine</h1>
      <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0; font-size: 14px;">Reset hasła</p>
    </div>
    <div style="padding: 40px 32px;">
      <h2 style="color: #e2e8f0; font-size: 20px; margin: 0 0 16px;">Resetowanie hasła</h2>
      <p style="color: #94a3b8; font-size: 15px; line-height: 1.6; margin: 0 0 24px;">
        Otrzymaliśmy prośbę o reset hasła dla tego adresu email. Kliknij poniższy przycisk, aby ustawić nowe hasło.
      </p>
      <div style="text-align: center; margin: 32px 0;">
        <a href="{reset_url}"
           style="display: inline-block; background: linear-gradient(135deg, #7c3aed, #a855f7);
                  color: #fff; text-decoration: none; font-size: 16px; font-weight: 600;
                  padding: 14px 32px; border-radius: 10px;">
          Resetuj hasło
        </a>
      </div>
      <p style="color: #64748b; font-size: 13px;">Link ważny przez 1 godzinę.</p>
      <p style="color: #64748b; font-size: 13px;">
        Jeśli nie prosiłeś(-aś) o reset hasła, zignoruj tę wiadomość.
      </p>
    </div>
  </div>
</body>
</html>
"""

    text_body = f"""Reset hasła — Video SEO Engine

Otrzymaliśmy prośbę o reset hasła.

Kliknij poniższy link, aby ustawić nowe hasło:
{reset_url}

Link ważny przez 1 godzinę.
Jeśli nie prosiłeś(-aś) o reset hasła, zignoruj tę wiadomość.
"""

    return _send_email(to_email, subject, html_body, text_body)
