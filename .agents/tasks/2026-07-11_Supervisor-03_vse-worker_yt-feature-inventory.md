# Dispatch: Inwentaryzacja YouTube feature — zbieranie danych
**Od:** Supervisor-03  
**Do:** vse-worker (Flash)  
**Data:** 2026-07-11  
**Typ:** data-collection — surowe outputy, bez analizy

---

## CEL

Zbierz dane o funkcjonalności YouTube która była w commicie 9e53a8b (zrevertowana przez Supervisor-03 z powodu błędu Rules of Hooks). Supervisor zdecyduje jak ją przywrócić poprawnie.

## ⚠️ ZNANE PUŁAPKI
1. Nie modyfikuj żadnych plików — tylko czytaj
2. SSH — pełne ścieżki Windows

## KOMENDY DO WYKONANIA

```powershell
# 1. Pełny diff commitu 9e53a8b (co było w YouTube UI)
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git show 9e53a8b -- web/src/app/dashboard/dashboard-inner.tsx"

# 2. Gdzie w dashboard-inner jest InjectModal i yt_channel
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "grep -n 'yt_channel\|ytChannel\|InjectModal\|selectedYt\|youtube' /home/ubuntu/video-seo-engine/web/src/app/dashboard/dashboard-inner.tsx | head -30"

# 3. Endpointy YT w backendzie
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "grep -n '@router\|def ' /home/ubuntu/video-seo-engine/api/routers/youtube.py | head -30"

# 4. Historia commitów dotykających dashboard
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git log --oneline -15 -- web/src/app/dashboard/"

# 5. Commity dotykające InjectModal
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git log --oneline -10 -- web/src/app/dashboard/dashboard-inner.tsx"

# 6. Czy jest osobny plik InjectModal?
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "find /home/ubuntu/video-seo-engine/web -name '*inject*' -o -name '*Inject*' 2>/dev/null"
```

## RAPORT

Dual-write:
1. `video-seo-engine/.agents/reports/2026-07-11_vse-worker_yt-feature-data.md`
2. `sonic-void/.agents/reports/inbox/2026-07-11_vse-worker_yt-feature-data.md`

Raport = surowe outputy wszystkich komend.

---
*[Supervisor-03 | sonic-void 11.07.2026]*