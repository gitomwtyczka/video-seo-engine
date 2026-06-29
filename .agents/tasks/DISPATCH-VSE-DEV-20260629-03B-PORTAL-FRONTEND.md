## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

Przeczytaj protokół dispatch:
`sonic-void/.agents/protocols/dispatch-system-block.md` (GitHub MCP)

Przeczytaj raport z Dispatch A (obowiązkowy kontekst):
`video-seo-engine/.agents/reports/2026-06-29_vse-dev_portal-backend.md`

Sprawdź że API backendu działa zanim zaczniesz:
```bash
curl https://vse.impresjapr.pl/api/v1/portals
# Powinno zwrócić: [] (pusta lista po Dispatch A)
```
Jeśli API nie odpowiada lub zwraca błąd — STOP. Zgłoś do Supervisora, nie kontynuuj.

---

# DISPATCH VSE-DEV-03B — Portal Management: Frontend (UI)

**Callsign:** vse-dev (Pro High)  
**Projekt:** video-seo-engine  
**Data:** 2026-06-29  
**Priorytet:** 🔴 WYSOKI  
**Część:** B/2 — wymaga ukończonego Dispatch A

---

## Cel

Zbudować warstwę UI zarządzania portalami:
- Dropdown "Portal docelowy" ładuje portale z DB (nie hardcoded)
- Opcja `+ Dodaj nowy portal` bezpośrednio w dropdown
- Modal "Wyślij do portalu" bez pól credentials
- Clean slate: usunięte hardcoded i localStorage portale
- Deploy + instrukcja testu dla właściciela

---

## Kontekst

### Po Dispatch A mamy:
- `GET /v1/portals` — zwraca listę portali z DB (bez haseł)
- `POST /v1/portals` — tworzy nowy portal
- `DELETE /v1/portals/{id}` — usuwa portal
- Pipeline: wybranie `portal_id` w Generate = automatyczny inject z credentials z DB

### Obecny frontend (do wymiany):
- Dropdown "Portal docelowy": hardcoded lista (Kurier365.pl, Prawy.pl)
- localStorage: portale zapisywane ręcznie
- Modal "Wyślij do portalu": pola URL, user, app_password — wpisywane ręcznie

### Decyzja właściciela:
> Dropdown ładuje TYLKO z DB. Pola credentials w modalu są usunięte.
> Użytkownik doda Prawy.pl i Kurier365 przez formularz po implementacji.

---

## Zakres

### 1. Dropdown "Portal docelowy" — nowa implementacja

**Usuń z frontendu:**
- Hardcoded lista portali (wszelkie `["Kurier365.pl", "Prawy.pl"]` lub podobne)
- Wszelki kod `localStorage.getItem("portals")` lub `localStorage.setItem("portals")`

**Nowy dropdown:**
```
Portal docelowy ▼
───────────────────────
  [lista portali z GET /v1/portals]
───────────────────────
  + Dodaj nowy portal...
```

**Logika:**
- Przy załadowaniu strony: `GET /v1/portals` → zapełnij dropdown
- Jeśli lista pusta: wyświetl komunikat "Brak portali — dodaj pierwszy portal"
- Wybór portalu z listy: zapisz `portal_id` (int) do stanu komponentu
- Ten `portal_id` trafia do `GenerateRequest` (nie `profile_id` jak było wcześniej)

### 2. Modal `+ Dodaj nowy portal`

Otwiera się kliknięciem opcji `+ Dodaj nowy portal` w dropdown.

```
┌─────────────────────────────────────────┐
│  Dodaj nowy portal                     │
│                                       │
│  Nazwa portalu:  [________________]    │
│  URL WordPress:  [https://...      ]   │
│  Użytkownik WP:  [________________]    │
│  App Password:   [________________]    │
│  Profil treści:  [prawy ▼           ]  │
│                   prawy               │
│                   kurier365           │
│                   (brak profilu)      │
│                                       │
│           [Zapisz portal] [Anuluj]    │
└─────────────────────────────────────────┘
```

**Logika modalu:**
- Kliknij `Zapisz portal` → `POST /v1/portals` z danymi formularza
- Po sukcesie: zamknij modal, odśwież dropdown (`GET /v1/portals`), wybierz nowo dodany portal
- Błąd 400 (zły `profile_id`) → wyświetl komunikat użytkownikowi
- App Password: pole type=password, nie zapisuj w localStorage

**Profil treści — lista:**  
Wczytaj dostępne profile z katalogu `profiles/` na backendzie LUB hardcode nowe opcje: `prawy`, `kurier365`, `(brak profilu)`. Prostsze: hardcode, bo profile rzadko się zmieniają.

### 3. Modal "Wyślij do portalu" — uproszczenie

**Usuń z modalu:**
- Pole URL portalu WordPress
- Pole Użytkownik WP  
- Pole Application Password
- Dropdown "Portal WordPress" (zastąpiony przez główny dropdown w kroku 1)
- Tekst "Dane logowania zapamiętane w przeglądarce (localStorage)"

**Zostaw w modalu:**
- Nazwa/informacja wybranego portalu (np. "Publikujesz na: Prawy.pl")
- ID posta WP (puste = nowy post)
- Status publikacji: Szkic / Publikuj
- Format wpisu (Film/video)
- Przycisk "Opublikuj na portalu"

**Logika:**
- `portal_id` (z dropdown w kroku 1) jest częścią payloadu do inject
- Backend sam pobiera credentials z DB na podstawie `portal_id`
- Użytkownik NIE musi niczego wpisywać

### 4. Opcja "Wpisz ręcznie" (fallback)

Zachowaj opcję "Wpisz ręcznie..." w dropdown jako ostatnią pozycję po `+ Dodaj nowy portal`.

Przy wyborze "Wpisz ręcznie": modal "Wyślij" pokazuje pola credentials (jak teraz).
To backward compat dla przypadków gdy ktoś nie chce zapisywać portalu.

---

## Deploy

```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  "cd /home/ubuntu/video-seo-engine && docker compose -f docker-compose.vse.yml build vse-web && docker compose -f docker-compose.vse.yml up -d vse-web"
```

---

## Test po deploy (wykonuje właściciel produktu)

1. Otwórz `https://vse.impresjapr.pl/dashboard`
2. Dropdown "Portal docelowy" → pusty / komunikat "Brak portali"
3. Kliknij `+ Dodaj nowy portal` → wypełnij formularz dla **Prawy.pl** (profil: prawy)
4. Kliknij `+ Dodaj nowy portal` → wypełnij formularz dla **Kurier365.pl** (profil: kurier365)
5. Dropdown: widoczne Prawy.pl i Kurier365.pl
6. Wybierz **Kurier365.pl** → generuj artykuł
7. Kliknij "Wyślij do portalu" → brak pól credentials → kliknij "Opublikuj"
8. Sprawdź w WP admin kurier365:
   - Artykuł stworzony ✓
   - Fraza kluczowa RankMath ustawiona ✓
   - Alt-text thumbnajla: `[keyphrase] | Kurier365` (nie "Prawy TV") ✓
9. Sprawdź RankMath score — cel: 70+

---

## Deliverable

- [ ] Usunięte hardcoded portale z frontendu
- [ ] Usunięty kod localStorage dla portali
- [ ] Dropdown ładuje portale z `GET /v1/portals`
- [ ] Komunikat "Brak portali" gdy lista pusta
- [ ] Modal `+ Dodaj nowy portal` z formularzem
- [ ] `POST /v1/portals` wywoływany z formularza
- [ ] Dropdown odświeża się po dodaniu portalu
- [ ] Modal "Wyślij" bez pól credentials
- [ ] Fallback "Wpisz ręcznie" zachowany
- [ ] `portal_id` przekazywany w GenerateRequest
- [ ] Deploy frontendu na VPS

**Dual-write raport:**
- `video-seo-engine/.agents/reports/2026-06-29_vse-dev_portal-frontend.md`
- `sonic-void/.agents/reports/inbox/2026-06-29_vse-dev_portal-frontend.md`

Heartbeat `status: done` po zakończeniu.

---

*[Supervisor 01 | sonic-void 29.06.2026]*
