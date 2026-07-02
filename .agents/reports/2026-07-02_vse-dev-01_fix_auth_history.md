# Raport [vse-dev-01]

Naprawiono dwa zgłoszone błędy:
1. **NextAuth plan refresh "free" bug**: Zaktualizowano `web/src/app/dashboard/dashboard-inner.tsx` aby podczas doczytywania profilu z backendu korzystać awaryjnie z informacji o planie zapisanej w sesji (`session.user.plan`). Zapobiega to krótkotrwałemu pokazywaniu darmowego planu użytkownikom pro/agency.
2. **History Leak**: Zaktualizowano `api/routers/jobs.py` i `generate.py`. Zabezpieczono dostęp do pobierania poszczególnych jobów (tylko właściciel joba lub admin). Zmieniono endpoint `/history` tak, aby w każdym przypadku uwzględniał filtr `user_id` (nawet dla adminów w widoku domyślnym). Dodano flagę `user_id` przy tworzeniu joba (przepina z endpointu wywołującego generację `Depends(get_current_user)`).

Wykonano wdrożenie na VPS z pre-deploy backupem. Wszystkie kontenery działają poprawnie.
