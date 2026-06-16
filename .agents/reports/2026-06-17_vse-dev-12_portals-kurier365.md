# Raport: vse-dev-12 — Portal Management MVP + Kurier365

**Data:** 2026-06-17 | **Callsign:** vse-dev-12

---

## Podsumowanie

Zaimplementowano pełny system zarządzania portalami WordPress (MVP) — od modelu bazy danych, przez API CRUD, po integrację z frontendem.

## Commits

| SHA | Opis |
|-----|------|
| `f7dd746` | feat: add WpPortal model for portal management MVP |
| `ce1520e` | feat: add portals relationship to User model |
| `85ef818` | feat: export WpPortal from models __init__ |
| `869874a` | feat: add CRUD portals router /v1/portals |
| `6f49fff` | feat: register portals router + WpPortal auto-create in main.py |
| `e1d830e` | feat: add usePortals hook for portal management |
| `a1f1f8b` | feat: InjectModal portal dropdown with auto-fill from /v1/portals |

## Co zrobiono

### Backend (Python/FastAPI)
- **`api/models/portal.py`** — model WpPortal z FK do users, CASCADE delete
- **`api/models/user.py`** — dodano relationship `portals` z cascade
- **`api/routers/portals.py`** — pełny CRUD:
  - `GET /v1/portals` — lista (bez haseł)
  - `POST /v1/portals` — dodaj portal
  - `GET /v1/portals/{id}/credentials` — z hasłem (osobny endpoint)
  - `PATCH /v1/portals/{id}` — edytuj
  - `DELETE /v1/portals/{id}` — usuń
- **`api/main.py`** — zarejestrowano router, WpPortal auto-create w startup

### Frontend (Next.js/TypeScript)
- **`use-portals.ts`** — hook `usePortals()` z fetchPortals, getCredentials, createPortal, deletePortal
- **`dashboard-inner.tsx`** — InjectModal przebudowany:
  - Dropdown z zapisanymi portalami (auto-select default)
  - Auto-fill credentials po wyborze portalu
  - Fallback na ręczne wpisanie (localStorage)
  - Informacja o wybranym portalu (URL + user)

### Database seed
- Kurier365 dodany do DB dla tobroz@gmail.com (`is_default=true`)
- Credentials NIE commitowane do repo

## Weryfikacja

- ✅ Tabela `wp_portals` utworzona automatycznie (auto-create)
- ✅ Kurier365 w DB (`INSERT 0 1`)
- ✅ API healthy (`/health` → 200)
- ✅ OpenAPI spec zawiera endpointy portali (25 referencji)
- ✅ Next.js build ✓ Compiled successfully
- ✅ Deploy OK — oba kontenery running

## Ograniczenia MVP

- Hasła przechowywane jako plaintext (szyfrowanie AES-256 w Faza 5+)
- Brak limitu portali per plan (do dodania w przyszłości)

---

*[vse-dev-12 | video-seo-engine 17.06.2026 00:15] — raport kompletny*
