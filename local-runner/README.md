# VSE Local Transcript Runner

## CO to jest?

Windows Service który pobiera transkrypty YouTube **lokalnie** (na Twoim PC)
i wysyła je do VSE API na VPS.

## PO CO?

YouTube blokuje `youtube-transcript-api` wywoływane z serwerowych IP (Oracle Cloud, AWS, GCP).
Ten runner działa na Twoim PC z normalnym IP domowym/biurowym — YouTube nie blokuje.

Bez runnera: pipeline zatrzymuje się bez transkryptu, Claude nie ma danych wejściowych.

## Wymagania

- **Windows 10/11** (Windows Service)
- **Python 3.10+** na PATH
- **NSSM** (Non-Sucking Service Manager) — pobierz ze [https://nssm.cc/download](https://nssm.cc/download)
  - Skopiuj `nssm.exe` do katalogu `local-runner/` lub dodaj do PATH
- Dostęp do internetu z normalnego IP (nie VPN data center)

## Instalacja

### Krok 1: Wygeneruj token

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Skopiuj wynik — to Twój `LOCAL_RUNNER_TOKEN`.

### Krok 2: Dodaj token do VPS

Wykonaj na VPS (przez SSH):
```bash
echo 'LOCAL_RUNNER_TOKEN=<twój_token>' >> /home/ubuntu/vse/.env
echo 'LOCAL_RUNNER_MODE=true' >> /home/ubuntu/vse/.env
```

Następnie rebuild API:
```bash
docker compose -f docker-compose.vse.yml build vse-api
docker compose -f docker-compose.vse.yml up -d --no-deps --force-recreate vse-api
```

### Krok 3: Skonfiguruj local runner

```powershell
cd local-runner
copy .env.example .env
```

Edytuj `.env`:
```ini
LOCAL_RUNNER_TOKEN=<ten_sam_token_co_na_VPS>
VSE_API_BASE=https://vse.impresjapr.pl
```

### Krok 4: Zainstaluj jako Windows Service

Uruchom jako **Administrator**:
```
install.bat
```

Skrypt:
1. Instaluje zależności Python
2. Tworzy katalog logów `C:\ProgramData\VSELocalRunner`
3. Instaluje i startuje service `VSELocalRunner`

## Zarządzanie service

```powershell
# Status
nssm status VSELocalRunner

# Stop / Start / Restart
net stop VSELocalRunner
net start VSELocalRunner

# Logi
notepad C:\ProgramData\VSELocalRunner\runner.log

# Deinstalacja
uninstall.bat  # (jako Administrator)
```

Lub przez `services.msc` (Windows Services Manager).

## Weryfikacja działania

1. Zainstaluj runner
2. Wyślij request do API: `POST /v1/generate` z URL YouTube
3. W logach runnera powinno pojawić się:
   ```
   [INFO] 1 pending job(s) found
   [INFO] Processing job abc-123: https://www.youtube.com/watch?v=XfGpTCMdvCE
   [INFO] Job abc-123: OK (15234 chars)
   ```
4. Pipeline kontynuuje generowanie SEO z transkryptu

## Bezpieczeństwo

- `LOCAL_RUNNER_TOKEN` ma minimalną entropię 256 bitów
- Transkrypt jest przesyłany przez HTTPS (TLS przez Cloudflare)
- API rate-limituje endpointy runnera do 30 req/min
- Transkrypt jest sanitizowany na serwerze przed przekazaniem do Claude
- **Nie commituj `.env`** — jest w `.gitignore`

## Troubleshooting

| Problem | Rozwiązanie |
|---------|-------------|
| Service nie startuje | Sprawdź logi: `C:\ProgramData\VSELocalRunner\runner.log` |
| `LOCAL_RUNNER_TOKEN not set` | Utwórz plik `.env` w katalogu `local-runner/` |
| `Connection error` | Sprawdź czy `VSE_API_BASE` jest poprawne |
| `NSSM not found` | Pobierz ze https://nssm.cc/download |
| Brak transkryptu | YouTube nie ma transkryptu dla tego wideo (niedostępne) |

---

*vsw-dev-04 | video-seo-engine | 2026-06-15*
