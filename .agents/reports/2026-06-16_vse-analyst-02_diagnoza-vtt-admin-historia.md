# Raport Diagnostyczny: VTT Rozdziały / Admin 500 / Historia Linki

**Agent:** `vse-analyst-02` | **Data:** 2026-06-16  
**Dispatch:** Supervisor 03 | **Rola:** DIAGNOZA (bez implementacji)

---

## Problem 1 — Rozdziały: `(bez tytułu)` i `?` zamiast tekstu

### Root Cause: **Field name mismatch** — backend zapisuje `time`/`label`, frontend szuka `startOffset`/`name`

**Stan w bazie (potwierdzony SSH + psql):**
- `schema_data` w DB zawiera `chapters` z **14 elementami** ✅
- Struktura każdego chapter:
```json
{"time": 0, "label": "Początki w klubach fantastyki – Proxima i Swan Fan", "matched": true, "anchor_text": "czytałem fantastykę właściwie odkąd pamiętam..."}
```
- Klucze: `time` (int, sekundy), `label` (string), `matched` (bool), `anchor_text` (string)

**Stan we frontendzie (kod z GitHub MCP):**

Plik `web/src/app/dashboard/dashboard-inner.tsx` — `extractChapters()` (linie ~84-97):

```typescript
function extractChapters(schema: SchemaData | null | undefined): ChapterItem[] {
  // 1. Szuka @graph → Clip (JSON-LD format)
  //    → schema nie ma @graph (potwierdzone DIAG 3: false)
  // 2. Fallback: schema.chapters → Array<{name?, startOffset?, endOffset?}>
  if (Array.isArray(schema.chapters)) return schema.chapters  // ← tu trafia
  return []
}
```

Interface `ChapterItem`:
```typescript
interface ChapterItem {
  name?: string        // ← oczekiwane, w DB nie ma — jest "label"
  startOffset?: number // ← oczekiwane, w DB nie ma — jest "time"  
  endOffset?: number   // ← oczekiwane, w DB nie ma — brak
}
```

Rendering w zakładce Rozdziały:
```typescript
<span>{secToTimestamp(ch.startOffset)}</span>  // → secToTimestamp(undefined) → "?"
<span>{ch.name ?? '(bez tytułu)'}</span>       // → undefined ?? '(bez tytułu)' → "(bez tytułu)"
```

> **IMPORTANT:** Badge "14" na zakładce Rozdziały **działa poprawnie** bo liczy `chapters.length`. Ale rendering **failuje** bo czyta pola które nie istnieją w obiekcie.

### Pliki do zmiany

| Plik | Co zmienić |
|------|-----------|
| `web/src/app/dashboard/dashboard-inner.tsx` | `extractChapters()` — mapować `label→name`, `time→startOffset` |

### Proponowany fix

**Opcja A (Frontend — rekomendowana, szybka):**  
W `extractChapters()` dodać mapping:

```typescript
if (Array.isArray(schema.chapters)) {
  return schema.chapters.map((c: Record<string, unknown>) => ({
    name: (c.name as string) ?? (c.label as string),
    startOffset: (c.startOffset as number) ?? (c.time as number),
    endOffset: c.endOffset as number | undefined,
  }))
}
```

**Opcja B (Backend — nie rekomendowane):**  
Zmienić `core/generator.py` aby chapters miały pola `name` i `startOffset` zamiast `label` i `time`. Wymaga re-generowania i nie naprawi istniejących danych w DB.

### Ryzyko
- Fix frontendowy jest **zero-risk** — backward compatible z obu formatami
- Istniejące 2 joby w DB od razu będą działać po deployu

---

## Problem 2 — Admin Panel: HTTP 500 przy ładowaniu użytkowników

### Root Cause: **MissingGreenlet** — lazy loading relacji `User.plan` w async kontekście SQLAlchemy

**Traceback z logów `vse-api` (potwierdzony SSH):**
```
GET /v1/admin/users?limit=500 → 500 Internal Server Error
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; 
can't call await_only() here.
```

**Analiza kodu:**

`api/auth.py` — `get_current_user()` **ma fix** (`selectinload(User.plan)`) ✅  
`api/routers/admin.py` — `list_users()` **NIE MA fixa** ❌:

```python
result = await db.execute(
    select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
    # ← brak selectinload! → lazy load User.plan → MissingGreenlet crash
)
# ...
plan = user.plan  # ← CRASH
```

> **IMPORTANT:** Fix `selectinload` istnieje w auth.py ale **nie został zastosowany** w admin.py. Identyczny root cause.

### Pliki do zmiany

| Plik | Co zmienić |
|------|-----------|
| `api/routers/admin.py` | Dodać `selectinload(User.plan)` do 3 queries + import |

### Proponowany fix

```python
from sqlalchemy.orm import selectinload

# list_users(), get_user(), change_user_plan():
result = await db.execute(
    select(User).options(selectinload(User.plan))  # ← DODAĆ
    .offset(skip).limit(limit).order_by(User.created_at.desc())
)
```

### Ryzyko
- **Zero-risk** — eager load zamiast lazy load
- `/v1/admin/stats` nie jest dotknięty (potwierdzone logami: 200 OK)

---

## Problem 3 — Historia: Linki nie klikają

### Root Cause: **Kod wygląda poprawnie** — ale większość jobów nie ma `has_schema=true`

**Analiza:**
- "Otwórz wyniki →" renderuje się TYLKO gdy `job.has_schema === true`
- Z 8 jobów w DB, **tylko 2 mają schema** (b43b0d6b i a30a233d). Reszta = `fetched` bez schema_data.
- Link "YT →" wymaga `job.video_id !== null`
- Tytuł i URL pod nim to `<p>` tagi **bez linków** — to nie bug, to brakująca feature

### Diagnoza warunkowa

Prawdopodobna przyczyna: raportujący widział joby bez schema (większość) — przyciski "Otwórz wyniki" nie renderowały się.

Jeśli problem dotyczy kliknięcia w sam tytuł/URL — to **feature request** (tytuł nie jest linkiem w kodzie).

### Pliki do zmiany (jeśli feature)

| Plik | Co zmienić |
|------|-----------|
| `web/src/app/historia/page.tsx` | Tytuł → Link do `dashboard?job_id=X`, URL → `<a>` |

### Ryzyko
- Zero-risk — zmiana renderowania
- Wymaga potwierdzenia co dokładnie nie klika

---

## Podsumowanie

| Problem | Severity | Root Cause | Fix effort |
|---------|----------|-----------|------------|
| 1. Rozdziały | 🔴 **High** | Field name mismatch: `label/time` vs `name/startOffset` | 15 min — 1 plik |
| 2. Admin 500 | 🔴 **High** | Brak `selectinload(User.plan)` w admin.py | 10 min — 1 plik |
| 3. Historia linki | 🟡 **Medium** | `has_schema=false` dla większości jobów / brak linków na tytule | 10 min — 1 plik |

*[vse-analyst-02 | video-seo-engine 16.06.2026 23:15] — raport kompletny*