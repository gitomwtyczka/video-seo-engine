# DISPATCH-VSE-DEV-ORG-ID-PREP

**Zleceniodawca:** arch-analyst-01 | 30.06.2026
**Priorytet:** LOW — przy najbliższej migracji DB
**Agent:** vse-dev (Gemini Flash)
**Workspace:** video-seo-engine

---

## Cel

Dodanie nullable `org_id` column do modelu User — przygotowanie pod przyszły Org/Tenant layer.
Zero impact na istniejące queries. Jedna linia kodu + jedna migracja.

## Kroki

### KROK 1: Modyfikuj `api/models/user.py`

Dodaj do klasy `User` (po `is_admin`):
```python
    # Prepared for Org layer — Faza 5 ecosystem integration
    org_id = Column(UUID(as_uuid=True), nullable=True, index=True)
```

### KROK 2: Generuj migracja Alembic

```bash
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 \
  "cd /home/ubuntu/vse && docker exec vse-api alembic revision --autogenerate -m 'add_org_id_nullable_to_users'"
```

**UWAGA:** Jeśli VSE nie używa Alembic jeszcze (auto_migrate), dodaj komentarz w kodzie i skip migracji.

### KROK 3: Weryfikacja

- [ ] Column dodana (nullable, UUID, indexed)
- [ ] Żadne istniejące testy nie failą
- [ ] Commit z message: `prep: add org_id nullable to users [vse-dev]`

## Zasada

**NIE** twórz tabeli `organizations`. **NIE** dodawaj FK. Tylko nullable column.

---
*[arch-analyst-01 | sonic-void 30.06.2026]*
