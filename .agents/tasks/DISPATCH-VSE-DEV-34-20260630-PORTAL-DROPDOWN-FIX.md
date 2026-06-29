# DISPATCH VSE-DEV-34 — Fix portal dropdown handlers (modal + ręczne wpisywanie)

**Callsign:** vse-dev
**Data:** 2026-06-30
**Zlecający:** Supervisor 01
**Priorytet:** 🟠 PILNY — klik w dropdown nie działa
**Model rekomendowany:** Claude Opus (chirurgiczny fix na dużym pliku)

---

## Problem (zdiagnozowany przez Supervisora)

Na `https://vse.impresjapr.pl/dashboard` dropdown portali wyświetla się, ale:
- Klik `+ Dodaj nowy portal` — **nic się nie dzieje** (modal nie otwiera się)
- Klik `✏️ Wpisz ręcznie` — **nic się nie dzieje**

**Wizualny fix `)}` z DISPATCH-33 działa** — `)}` zniknęło, grid się renderuje.

### Przyczyna (analiza kodu)

**Plik:** `web/src/app/dashboard/dashboard-inner.tsx` — SHA: `1d4541fe5a1dd629aa38dd1fe6d155797b1132fc`

**Bug 1 — `__add__` gdy portals=0:**
```tsx
// Linie ~1076-1081 — blok "portals.length === 0"
<select
  value="__add__"  // ← PROBLEM: value jest stałe "__add__"
  onChange={(e) => { if (e.target.value === '__add__') setShowAddPortalModal(true) }}
>
  <option value="" disabled>Brak portali — dodaj pierwszy portal</option>
  <option value="__add__">+ Dodaj nowy portal...</option>
  <option value="__manual__">✏️ Wpisz ręcznie...</option>
</select>
```

Problemy:
1. `value="__add__"` jest hardcoded — klik `__add__` nie zmienia wartości → `onChange` NIE odpala
2. Nie ma handlera dla `__manual__` — onChange sprawdza tylko `__add__`
3. Nawet gdyby onChange odpalil — po otwarciu modalu `value` wraca do `__add__` (brak state)

**Bug 2 — `__add__` gdy portals>0:**
```tsx
// Linie ~1087-1097 — blok "portals.length > 0"
onChange={(e) => {
  const val = e.target.value;
  if (val === '__add__') {
    setShowAddPortalModal(true)
    e.target.value = selectedPortalId  // ← reset do poprzedniego
  } else {
    setSelectedPortalId(val)
  }
}}
```
Ten blok wygląda poprawniej, ale `e.target.value = selectedPortalId` to mutacja DOM która React nadpisze. Brak handlera `__manual__`.

---

## Twoje zadanie — FIX

### Poprawka 1: Blok `portals.length === 0`

Zamień `<select value="__add__"...>` na:
```tsx
<select
  value=""
  onChange={(e) => {
    const val = e.target.value;
    if (val === '__add__') {
      setShowAddPortalModal(true);
    } else if (val === '__manual__') {
      setSelectedPortalId('__manual__');
    }
  }}
  className="..."  // zachowaj oryginał
  style={{...}}     // zachowaj oryginał
>
  <option value="" disabled>Brak portali — dodaj pierwszy portal</option>
  <option value="__add__">+ Dodaj nowy portal...</option>
  <option value="__manual__">✏️ Wpisz ręcznie...</option>
</select>
```

Klucz: `value=""` z `disabled` na pustym option → każda zmiana odpala onChange.

### Poprawka 2: Blok `portals.length > 0`

Dodaj handler `__manual__`:
```tsx
onChange={(e) => {
  const val = e.target.value;
  if (val === '__add__') {
    setShowAddPortalModal(true);
  } else if (val === '__manual__') {
    setSelectedPortalId('__manual__');
  } else {
    setSelectedPortalId(val);
  }
}}
```
Usuń linię `e.target.value = selectedPortalId` — React kontroluje value.

### Poprawka 3: Upewnij się że `<AddPortalModal>` jest renderowany

Sprawdź czy w return DashboardInner jest:
```tsx
{showAddPortalModal && (
  <AddPortalModal
    onClose={() => setShowAddPortalModal(false)}
    onSuccess={(newId) => {
      setSelectedPortalId(newId);
      setShowAddPortalModal(false);
    }}
  />
)}
```
Jeśli jest — nie zmieniaj. Jeśli nie — dodaj przed zamknięciem return.

---

## Deploy po commicie

```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml build vse-web && docker compose -f docker-compose.vse.yml up -d vse-web"
```

Po deploy: `docker compose -f docker-compose.vse.yml logs vse-web --tail 10` — brak błędów kompilacji.

---

## Deliverable

- [ ] Fix onChange w bloku portals=0 (value="" + handler __add__ i __manual__)
- [ ] Fix onChange w bloku portals>0 (handler __manual__, usunięcie DOM mutation)
- [ ] Weryfikacja AddPortalModal render
- [ ] Commit na main
- [ ] Deploy vse-web na VPS
- [ ] Logi bez błędów

**Dual-write raport:**
- `video-seo-engine/.agents/reports/2026-06-30_vse-dev_portal-dropdown-fix.md`
- `sonic-void/.agents/reports/inbox/2026-06-30_vse-dev_portal-dropdown-fix.md`

Heartbeat `status: done`.

---

## Zasady

- Czytaj plik przez **GitHub MCP** (nie lokalny klon!)
- Kopiuj className i style 1:1 z oryginału — nie przepisuj
- Po commicie: `docker exec vse-web npm run build 2>&1 | tail -5` — weryfikacja TypeScript PRZED deploy
- Jeśli build failed — STOP, nie deployuj, raportuj

---

*[Supervisor 01 | sonic-void 30.06.2026]*
