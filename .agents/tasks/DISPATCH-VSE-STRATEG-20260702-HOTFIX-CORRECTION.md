# DISPATCH: Korekta planu hotfix — tylko frontend fix

**Data:** 2026-07-02 20:56  
**Od:** Supervisor 01  
**Do:** vse-strateg-01  
**Priorytet:** 🟡 P1 (korekta planu, nie emergency)

---

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)

1. GitHub MCP: po create_or_update_file ZAWSZE zweryfikuj newlines
2. Backend `jobs.py` — NIE TYKAMY. Każda zmiana tam ryzykuje regresję.
3. Lokalny klon może być nieaktualny — weryfikuj stan przez GitHub MCP przed edycją

---

## 🛑 Korekta Twojego planu implementacji

Supervisor wykonał niezależną weryfikację kodu (research subagent + GitHub MCP). Wynik:

### Backend (`api/routers/jobs.py`) — **NIE WYMAGA ZMIAN**

| Problem z Twojego planu | Rzeczywisty stan kodu |
|---|---|
| `complete_job` ma `current_user` → NameError | ❌ Nie ma — endpoint czysty, tylko `_verify_runner_token` (L.390) |
| Brak filtra admina w `get_job_history` | ❌ Filtr już istnieje (L.373: `if not current_user.is_admin`) |
| Zduplikowane bloki w `get_job`/`get_job_vtt` | ❌ Brak duplikacji — normalny pattern 404 |

**Najprawdopodobniej vse-dev-01 naprawił te problemy w poprzedniej sesji** (heartbeat: `status: done`, `last_completed: ["Bug 3: History Leak", "NextAuth plan refresh"]`).

**Wniosek: Nie wysyłaj workera do backendu. Ryzyko regresji jest realne.**

---

## ✅ Jedyny realny problem — Frontend

**Plik:** `web/src/app/dashboard/dashboard-inner.tsx`  
**Problem:** `isPro` bazuje wyłącznie na `fetchUserProfile` (API call do `/v1/users/me`). Brak fallbacku na `session`.

```typescript
// Obecny kod (L.1116-1118) — PROBLEM
const isPro =
    userProfile != null &&
    ['pro', 'agency'].includes(userProfile.plan.id)
// Jeśli API fail → userProfile = null → isPro = false → Pro user widzi Free UI
```

**Skutek:** Przy chwilowym failurze `/v1/users/me` użytkownik Pro traci dostęp do sekcji publikacji bez żadnego komunikatu. Silent catch, zero feedbacku.

---

## 🎯 Zadanie dla Workera (precyzyjny scope)

Wyślij **jednego workera** (`vse-dev-02` lub nowy callsign) z dokładnie tym zadaniem:

### Fix: Fallback `isPro` na session w `dashboard-inner.tsx`

**Przed:**
```typescript
const isPro =
    userProfile != null &&
    ['pro', 'agency'].includes(userProfile.plan.id)
```

**Po:**
```typescript
const isPro =
    (userProfile != null && ['pro', 'agency'].includes(userProfile.plan.id)) ||
    (userProfile == null && ['pro', 'agency'].includes((session?.user as any)?.plan ?? ''))
```

Logika:
- Jeśli `userProfile` jest załadowany → używa go (jak dotychczas)
- Jeśli `userProfile` jest `null` (API fail lub ładowanie) → fallback na `session.user.plan` z JWT
- Session JWT jest lokalny, nie zależy od stanu API

### Wymagania dla workera:
1. Edytuj tylko tę jedną linię w `dashboard-inner.tsx` przez GitHub MCP
2. **NIE deployuj** — tylko push na GitHub
3. W raporcie podaj SHA commita i dokładny diff (przed/po)
4. Supervisor robi code review diffa przed GO na deploy

---

## Definition of Done (ta sesja)

- [ ] Worker edytuje tylko `dashboard-inner.tsx` — jedną linię `isPro`
- [ ] Push na GitHub (nie deploy)
- [ ] Diff w raporcie do `sonic-void/.agents/reports/inbox/`
- [ ] Czekasz na GO od Supervisora przed deployem

*[Supervisor 01 | sonic-void 02.07.2026 20:56]*
