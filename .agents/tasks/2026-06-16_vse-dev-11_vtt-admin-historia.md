## ⚡ KROK 0

**Callsign:** `[vse-dev-11 | video-seo-engine]` | Model: Claude Sonnet

> Jeśli jesteś analitykiem vse-analyst-02 kontynuującym jako worker — masz już pełny kontekst, pomijasz diagnostykę.

---

# TASK: vse-dev-11 — Cztery poprawki + Debug logging

**Data:** 2026-06-16 | **Dispatch:** Supervisor 03

---

## 📚 KROK 0b (tylko jeśli nowy agent)

Przeczytaj `docs/ARCHITECTURE.md` i `ROADMAP.md` przez GitHub MCP.

---

## Cztery rzeczy do zrobienia

### 1. Rozdziały — fix pola (frontend)

**Plik:** `web/src/app/dashboard/page.tsx`

Backend zwraca: `{ time, label }` 
Frontend szuka: `{ startOffset, name }` ← źle

Zmień w kodzie renderowania rozdziałów: `chapter.startOffset` → `chapter.time`, `chapter.name` → `chapter.label`

Weryfikacja: po deploy rozdziały pokazują tytuły i czasy zamiast `(bez tytułu)`.

---

### 2. Admin HTTP 500 — selectinload (backend)

**Plik:** `api/routers/admin.py`

Identyczny bug jak naprawiony w `api/auth.py` przez dev-08. Brak `selectinload(User.plan)` powoduje `MissingGreenlet` w async SQLAlchemy.

Dodaj do query w endpointach admin:
```python
from sqlalchemy.orm import selectinload
# w select(User) dodaj .options(selectinload(User.plan))
```

Weryfikacja: panel admina ładuje listę użytkowników bez błędu.

---

### 3. Historia — tytuł klikalny (frontend)

**Plik:** `web/src/app/historia/page.tsx`

Tytuł joba jest w `<p>`. Zamień na klikalny link do YouTube:
```tsx
<a href={job.youtube_url} target="_blank" rel="noopener noreferrer">
  {job.title ?? job.youtube_url}
</a>
```

Weryfikacja: kliknięcie tytułu otwiera YouTube.

---

### 4. Error logging + przełącznik debug w panelu admina

**Backend — `api/main.py` lub nowy `api/middleware/logging.py`:**

Dodaj middleware który:
- Loguje każdy błąd 500 z pełnym stack trace do stdout (docker logs)
- Respektuje zmienną `DEBUG_MODE` z bazy lub env

**Backend — nowy endpoint:**
```
POST /v1/admin/debug-mode  { "enabled": true/false }
GET  /v1/admin/debug-mode  → { "enabled": bool }
```

Przechowaj stan w tabeli `app_settings` (klucz: `debug_mode`, wartość: `"true"`/`"false"`) lub w Redis jeśli dostępny. Jeśli nie ma ani jednego — użyj prostej tabeli `app_settings`:
```sql
CREATE TABLE IF NOT EXISTS app_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Frontend — `web/src/app/admin/page.tsx`:**

Dodaj sekcję "Ustawienia systemu" z przełącznikiem:
```
[●] Tryb debug  ON | OFF
```
Toggle wywołuje `POST /v1/admin/debug-mode`.

---

## Deploy

```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "cd /opt/vse && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-api vse-web"
```

> ⚠️ Złożone komendy SQL przez SSH → write_to_file + scp + ssh. Nie escapuj inline w PowerShell.

---

## Raport (dual-write)

1. `video-seo-engine/.agents/reports/2026-06-16_vse-dev-11_fixes-logging.md`
2. `sonic-void/.agents/reports/inbox/2026-06-16_vse-dev-11_fixes-logging.md`

```
[vse-dev-11 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[vse-dev-11 | video-seo-engine DD.MM.YYYY HH:MM] — raport kompletny
```

*Supervisor 03 | sonic-void | 2026-06-16 23:22*
