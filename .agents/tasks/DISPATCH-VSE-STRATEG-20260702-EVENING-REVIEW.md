# DISPATCH: VSE Strateg — Evening Review + Krytyczny Bug

**Data:** 2026-07-02 19:22  
**Od:** Supervisor 01  
**Do:** vse-strateg-01  
**Priorytet:** 🔴 KRYTYCZNY (jeden bug aktywny w produkcji)

---

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)

1. GitHub MCP: po create_or_update_file ZAWSZE zweryfikuj newlines
2. SSH: złożone komendy → write_to_file → scp → ssh (nie inline)
3. Stripe: używaj obj["key"] lub obj.attribute, NIGDY .get()
4. Portal routing: sprawdź jak frontend przekazuje `portal_id` / `site_config` do `/v1/inject` — tam już był bug 422

---

## 🔴 BUG KRYTYCZNY: Publikacja na Złym Portalu

**Symptom:** Użytkownik wybrał w dropdownie portal **kurier365.pl**, modal potwierdził "Publikujesz na: kurier365.pl" (URL: https://kurier365.pl), kliknął Opublikuj. Artykuł trafił na **biznesciti** zamiast na kurier.  
**Wynik:** Sukces! Nowy artykuł (ID: 28536) — ale na złym portalu.

**Priorytet:** P0 — aktywny błąd produkcyjny, każda kolejna publikacja może trafić nie tam gdzie trzeba.

**Twoje zadania:**
1. Sprawdź jak frontend buduje request do `/v1/inject` — czy przekazuje poprawny `portal_id` czy `site_config`
2. Sprawdź logi Docker (tryb debug jest włączony!) — poszukaj żądania HTTP dla ID 28536, jaki portal_id dotarł do backendu
3. Ustal czy to bug frontendowy (zły portal_id w request) czy backendowy (ignoruje portal_id, bierze z innego miejsca)
4. Po zidentyfikowaniu — dispatch workera z fixem

**SSH logi:**
```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker logs vse-api --tail 100 2>&1 | grep -A5 -B5 '28536'"
```

---

## 🟡 Bug 3: History Leak — Weryfikacja Stanu

**Kontekst:** Były 2x twarde zwisy w sesji debugowania, diagnoza niepewna.  
**Zadanie:** Sprawdź przez SSH czy endpoint `GET /jobs/history` faktycznie wycieka dane między userami. Prosty test:

```bash
# Zaloguj się jako tobroz i sprawdź czy widać generacje verinarto lub odwrotnie
# Możesz też przez docker exec sprawdzić zapytanie SQL
ssh ... "docker exec vse-postgres psql -U postgres -c \"SELECT user_id, id FROM jobs ORDER BY created_at DESC LIMIT 20;\""
```

Jeśli leak istnieje — dispatch workera z fixem (dodanie `WHERE user_id = current_user_id` do zapytania).  
Jeśli nie ma — zaktualizuj `current.md` i zamknij task.

---

## ✅ Aktualizacje Statusów (zrób przy okazji)

### 1. SETTINGS-MINIMAL — oznaczyć jako zamknięte
User potwierdził że zostało wdrożone. Przenieś z "W toku" do "Zamknięte" w `current.md`.

### 2. Email Verification — SMTP
User potwierdził że tobroz@ dostał mail weryfikacyjny i weryfikacja przeszła. Sprawdź czy SMTP_PASSWORD jest w `.env` na VPS:
```bash
ssh ... "docker exec vse-api env | grep SMTP"
```
Jeśli jest — wykreśl "SMTP .env na VPS" z listy "Następne" w `current.md`.  
Jeśli brak — eskaluj jako osobny fix.

### 3. README — Zsynchronizuj z current.md
Roadmapa w README ma kilka nieaktualności:
- `Email verification — flow TBD` → powinno być `✅ DONE` (commit cf08318, c78d5bd)
- `Google OAuth login — flow TBD` → powinno być `✅ DONE` (commit 35afbc4)
- `Terms of Service + Privacy Policy` → powinno być `✅ DONE` (commit 7770748, c08952e)
- `Pre-deploy backup system` → sprawdź status

---

## ℹ️ Kontekst operacyjny

- Portal `vse.impresjapr.pl` jest **operacyjny** — user pracuje na nim aktywnie
- **Tryb debug Docker jest włączony** — logi są bogate, korzystaj z nich
- Bug 2/4/5 (422) był już raz naprawiony przez poprzedniego workera — uważaj żeby patch na nowy bug nie cofnął tamtej poprawki
- Stripe double-billing (brak `subscription_update`) — analityk dostarczył gotowy patch. Wrócimy do tego w osobnym dispatchu po zamknięciu buga portalu.

---

## Definition of Done (ta sesja)

- [ ] Zdiagnozowany root cause buga złego portalu (z logami jako dowodem)
- [ ] Dispatch workera z fixem lub fix wdrożony jeśli trivialny
- [ ] Bug 3 (History Leak) — potwierdzony lub obalony
- [ ] `current.md` zaktualizowany
- [ ] README zsynchronizowany z rzeczywistym stanem
- [ ] Raport → `sonic-void/.agents/reports/inbox/2026-07-02_vse-strateg-01_evening-review.md`

*[Supervisor 01 | sonic-void 02.07.2026 19:22]*
