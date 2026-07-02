# DISPATCH: vse-dev — Hotfix P0 (jobs.py + dashboard-inner.tsx)

**Data:** 2026-07-02 21:01  
**Od:** Supervisor 01  
**Do:** vse-strateg-01 → przekazuje do workera (vse-dev-*)  
**Priorytet:** 🔴 P0 — aktywne awarie produkcyjne  
**SHA `jobs.py` (GitHub main):** `7c0bee0239f01f0a76d21621b36884d6bc44d451`

---

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)

1. Edycja przez **GitHub MCP** (`create_or_update_file`) — nie przez lokalny klon
2. Przed edycją pobierz aktualny SHA pliku przez `get_file_contents`
3. Po edycji zweryfikuj newlines przez ponowny `get_file_contents`
4. **NIE deployuj** po edycji — push na GitHub, raport z diffem, czekaj na GO od Supervisora
5. Nie tykaj niczego poza 4 wskazanymi miejscami poniżej

---

## Plik 1: `api/routers/jobs.py`

### Fix 1A — `get_job_history`: przywróć filtr admina

**Problem:** Historia znika dla wszystkich użytkowników. Zapytanie filtruje po `user_id` BEZ warunku admina — admin nie widzi starych jobów z `user_id = NULL`.

**Obecny kod (do zmiany):**
```python
query = select(TranscriptJob).where(TranscriptJob.user_id == current_user.id)
```

**Po zmianie:**
```python
query = select(TranscriptJob)
if not current_user.is_admin:
    query = query.where(TranscriptJob.user_id == current_user.id)
```

---

### Fix 1B — `complete_job`: usuń zduplikowany blok z `current_user`

**Problem:** Endpoint `POST /{job_id}/result` ma w ciele funkcji **dwa identyczne bloki** sprawdzające `current_user.is_admin`, mimo że `current_user` nie jest parametrem tej funkcji (auth = runner token). Powoduje `NameError` przy każdym wywołaniu przez runnera.

**Obecny kod (do usunięcia — oba bloki, całością):**
```python
    if job.user_id is None:
        if not current_user.is_admin:
            raise HTTPException(403, "Access denied")
    elif job.user_id != current_user.id:
        if not current_user.is_admin:
            raise HTTPException(403, "Access denied")

    if job.user_id is None:
        if not current_user.is_admin:
            raise HTTPException(403, "Access denied")
    elif job.user_id != current_user.id:
        if not current_user.is_admin:
            raise HTTPException(403, "Access denied")
```

**Po zmianie:** oba bloki usuń, nie zastepować niczym. Endpoint jest już chroniony przez `_verify_runner_token`.

---

### Fix 1C — `get_job` i `get_job_vtt`: usuń zduplikowane bloki

**Problem:** Każdy z tych endpointów ma ten sam blok sprawdzający `current_user` **dwa razy** z rzędu (identyczny). To nie powoduje crash ale jest błędem logicznym po poprzednim workerze.

**Akcja:** W każdym z tych dwóch endpointów zostaw **jeden** blok:
```python
    if job.user_id is None:
        if not current_user.is_admin:
            raise HTTPException(403, "Access denied")
    elif job.user_id != current_user.id:
        if not current_user.is_admin:
            raise HTTPException(403, "Access denied")
```
Usuń duplikat tuż poniżej.

---

## Plik 2: `web/src/app/dashboard/dashboard-inner.tsx`

### Fix 2 — `isPro`: dodaj fallback na session

**Problem:** `isPro` bazuje wyłącznie na `fetchUserProfile` (API call). Jeśli `/v1/users/me` nie odpowie (błąd, timeout, restart kontenera), `userProfile = null` → `isPro = false` → użytkownik Agency/Pro widzi UI Free bez żadnego komunikatu. **Potwierdzone live przez Usera.**

**Znajdź linię:**
```typescript
const isPro =
    userProfile != null &&
    ['pro', 'agency'].includes(userProfile.plan.id)
```

**Zamień na:**
```typescript
const isPro =
    (userProfile != null && ['pro', 'agency'].includes(userProfile.plan.id)) ||
    (userProfile == null && ['pro', 'agency'].includes((session?.user as any)?.plan ?? ''))
```

Logika: jeśli API zwróciło dane — używaj ich. Jeśli nie — fallback na `session.user.plan` z JWT (lokalny, nie zależy od API).

---

## Definition of Done

- [ ] Edycja `jobs.py` przez GitHub MCP: Fix 1A + 1B + 1C
- [ ] Edycja `dashboard-inner.tsx` przez GitHub MCP: Fix 2
- [ ] Weryfikacja po edycji: `get_file_contents` dla obu plików
- [ ] **Push na GitHub — BEZ deployu**
- [ ] Raport z diffem (przed/po dla każdego fixa) do `sonic-void/.agents/reports/inbox/2026-07-02_[callsign]_hotfix-jobs-dashboard.md`
- [ ] Czekasz na GO od Supervisora przed `docker compose up`

*[Supervisor 01 | sonic-void 02.07.2026 21:01]*
