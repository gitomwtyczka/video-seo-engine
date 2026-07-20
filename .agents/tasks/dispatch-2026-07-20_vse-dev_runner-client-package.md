# DISPATCH: local-runner-client-package
**Target:** vse-dev (KROK 2 — po zamknięciu fix VTT truncation)
**Repo:** video-seo-engine
**Priorytet:** WYSOKI — feature produktowy
**Data:** 2026-07-20

---

## Cel

Umóżliwić klientom VSE pobranie i zainstalowanie Local Runner na ich własnym PC.
Local Runner działa jako Windows Service na komputerze klienta i pobiera transkrypty
dla ich konta w serwisie — omijając blokadę IP Oracle Cloud.

---

## Wymagania zatwierdzone

### Format paczki
- **ZIP** zawierający:
  - `runner.py` (aktualny z poprawkami VTT)
  - `.env` z wbudowanym tokenem klienta i adresem API
  - `install.bat` (instalacja NSSM jako Windows Service)
  - `start_runner.bat` (tryb developerski / test bez serwisu)
  - `uninstall.bat`
  - `export_cookies.bat` (Task Scheduler dla odświeżania cookies)
  - `requirements.txt`
  - `README.md` — uproszczone instrukcje dla klienta (NIE developera)

### Token
- Unikalny per klient, generowany przy rejestracji w VSE
- Wbudowany do `.env` w paczce — klient instaluje bez konfiguracji
- Token istniejacy w modelu `WpPortal` lub `User` (sprawdzić schemat DB)

### Dystrybucja (do ustalenia z Supervisorem)

⚠️ DECYZJA OTWARTA: Supervisor (Tomas) nie zdecydował jeszcze jak klient pobiera paczkę.
Opcje do rozważenia:

**A)** Endpoint GET `/v1/runner/download` — autoryzowany Bearer tokenem klienta.
  Pipeline: generuje ZIP on-the-fly z `.env` zawierającym token klienta.
  PRO: bezobsługowe, paczka zawsze aktualna
  CON: wymaga nowego endpointu w API VSE

**B)** Statyczny ZIP generowany jednorazowo przy rejestracji, przechowywany na VPS
  i linkowany z panelu.
  PRO: prostsze
  CON: plik może być nieaktualny po aktualizacji runnera

**C)** Strona pobrania `/download-runner` z formularzem — klient wpisuje swój
  portal_id/token, dostaje spersonalizowany ZIP.
  PRO: żadna strona web, brak konieczności rejestracji w API
  CON: klient musi wiedzieć swój token

**Rekomendacja dla Supervisora:** Opcja A — najbardziej bezobsługowa,
spersonalizowany ZIP z tokenem = zero konfiguracji po stronie klienta.

> 🚦 NIE IMPLEMENTUJ dopóki Supervisor nie zatwierdzi opcji dystrybucji.

---

## Zakres implementacji (po zatwierdzeniu dystrybucji)

### Opcja A: Nowy endpoint API

#### `api/routes/runner.py` [NEW]
```
GET /v1/runner/download
Authoryzacja: Bearer {local_runner_token}
Response: application/zip
  └─ VSELocalRunner-setup.zip
      ├── .env               (token wbudowany)
      ├── runner.py
      ├── install.bat
      ├── start_runner.bat
      ├── uninstall.bat
      ├── export_cookies.bat
      ├── requirements.txt
      └── README.md
```

Pipeline generowania ZIP:
1. Odczyt tokenu klienta z DB (per portal_id z Bearer token)
2. Wczytaj pliki z `local-runner/` na dysku VPS
3. Podmień `.env.example` → wypełniony `.env` z tokenem + VSE_API_BASE
4. Spakuj do ZIP w pamięci (io.BytesIO)
5. Zwroć StreamingResponse z Content-Disposition: attachment

#### `local-runner/README.client.md` [NEW]
Uproszczone instrukcje (nie tech-talk):
1. Zainstaluj Python 3.11+ (link)
2. Uruchom `install.bat` jako administrator
3. Gotowe — runner działa w tle

### Roadmap — wersja 3 (do odnotowania w ROADMAP.md)
- Standalone .exe (PyInstaller) — bez wymogu Python na PC klienta

---

## Uwagi techniczne

- ZIP generowany in-memory (`zipfile.ZipFile(BytesIO())`) — nie zapisujemy na dysk
- Pliki źródłowe runnera muszą być dostępne na VPS w katalogu `local-runner/`
  (są w repo — muszą być w deploymencie)
- `.env` w ZIP: NIE commituj żadnych sekretów do repo (generuj dynamicznie)
- Token źródło: sprawdzić czy model `WpPortal` ma pole `runner_token` lub trzeba dodać

---

## Kolejność kroków (po decyzji Supervisora)

1. Supervisor zatwierdza opcję dystrybucji (A/B/C)
2. Sprawdzić czy DB ma pole `runner_token` w modelu `WpPortal` (albo `User`)
3. Jeśli nie — migracja DB: `ALTER TABLE wp_portals ADD COLUMN runner_token VARCHAR(64)`
4. Implementacja endpointu
5. Testy: pobrać ZIP, zainstalować, sprawdzić czy runner startuje i pobiera job

---

## Raportowanie

Dual-write po implementacji:
1. `video-seo-engine/.agents/reports/YYYY-MM-DD_vse-dev_runner-package.md`
2. `sonic-void/.agents/reports/inbox/YYYY-MM-DD_vse-dev_runner-package.md`
