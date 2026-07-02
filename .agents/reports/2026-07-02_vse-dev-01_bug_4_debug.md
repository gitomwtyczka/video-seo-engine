# Raport z wdrożenia (Bug 4 - Object Object i DEBUG_MODE)

## Zmiany w kodzie

1. **Backend (`core/injector.py`)**:
   Zgodnie z poleceniem, dodano obsługę zmiennej środowiskowej `DEBUG_MODE` oraz zrzucanie logów dla obciążenia (`WP Error Payload`) i odpowiedzi (`WP Error Response`). Dodano to przed `resp.raise_for_status()` w funkcjach dokonujących zrzutów do WP REST API:
   - w `update_rankmath_meta` (linia ~377)
   - w `update_post` (linia ~1193 - tutaj tuż przed wyciągnięciem `link` i sprawdzeniem HTTP status)
   
2. **Frontend (`web/src/app/dashboard/dashboard-inner.tsx`)**:
   Zabezpieczono obiekt błędu przed wyrzucaniem czystego ciągu `[object Object]` podczas błędu publikacji (funkcja `handlePublish`). W przypadku gdy serwer zwraca skomplikowany obiekt zamiast płaskiego stringa, aplikacja przetwarza go poprzez `JSON.stringify`.

## Status wdrożenia

- **GitHub**: Zmiany zostały wrzucone na repozytorium GitHub (branch `main`).
- **Pre-deploy Backup**: Kopia zapasowa na serwerze (skrypt `backup_pre_deploy.sh`) wykonała się poprawnie i poinformowała o sukcesie.
- **Deploy**: Próba automatycznego deployu (wykonania `git pull`, `docker compose build/up -d` oraz `restart vse-api`) poprzez połączenie SSH uległa zablokowaniu (timeout na prompt oczekujący na zatwierdzenie uprawnień `run_command`).

## Wymagane akcje po stronie użytkownika

Z powodu braku zatwierdzenia przez administratora komendy deploy (w systemie UAC/prompt na połączenie), proszę o manualne wykonanie poniższej komendy:

```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml build vse-web vse-api && docker compose -f docker-compose.vse.yml up -d vse-web vse-api && docker compose -f docker-compose.vse.yml restart vse-api"
```

## Status: Zakończono (czekam na manualny deploy)
