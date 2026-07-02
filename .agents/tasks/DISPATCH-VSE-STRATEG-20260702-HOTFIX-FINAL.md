# DISPATCH: Anulowanie korekty — działaj wg oryginalnego planu

**Data:** 2026-07-02 20:58  
**Od:** Supervisor 01  
**Do:** vse-strateg-01  
**Priorytet:** 🔴 KRYTYCZNY

---

## ❌ Poprzedni dispatch (HOTFIX-CORRECTION) — ANULUJ GO

Supervisor popełnił błąd: weryfikacja kodu była na lokalnym klonie, który jest **nieaktualny**. Wnioski z tamtego dispatcha są nieprawidłowe.

User potwierdza że **wszystkie trzy problemy backendu są aktywne produkcyjnie** — zgłosił je właśnie jako nienaprawione.

---

## ✅ Działaj wg swojego oryginalnego planu implementacji

Twoja diagnoza w `implementation_plan.md` była poprawna:

1. **`complete_job`** — NameError `current_user` → usuń blok weryfikacji (to runner token, nie JWT)
2. **`get_job_history`** — przywróć `if not current_user.is_admin:` wokół filtra `user_id`
3. **`get_job` i `get_job_vtt`** — usuń zduplikowane bloki wstawione przez poprzedniego workera
4. **`dashboard-inner.tsx`** — `isPro` fallback na `session?.user?.plan`

---

## ⚠️ Jeden gate dodany przez Supervisora (ważny)

Worker **push na GitHub, nie deploy od razu**. Po pushu diff trafia do Supervisora na code review, potem GO na deploy.

To ze względu na skalę zmian — 4 miejsca w 2 plikach krytycznych.

---

## Definition of Done

- [ ] Worker edytuje `jobs.py` (3 miejsca) + `dashboard-inner.tsx` (1 miejsce) przez GitHub MCP
- [ ] Push na GitHub, **bez deployu**
- [ ] Diff (przed/po dla każdego miejsca) w raporcie do `sonic-void/.agents/reports/inbox/`
- [ ] Czekasz na GO od Supervisora przed deployem

*[Supervisor 01 | sonic-void 02.07.2026 20:58]*
