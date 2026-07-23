# DISPATCH — [vse-log-analyst-01]
## Analiza logów VSE — weryfikacja fixów 22-23.07.2026

---

## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**0. Wczytaj blok systemowy:**
```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: sonic-void
  branch: master
  path: .agents/protocols/dispatch-system-block.md
```
*(Jeśli plik nie istnieje — kontynuuj bez niego)*

---

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)

1. SSH z PowerShell: NIE interpoluj `$zmiennych` w cudzysłowach — używaj `'apostrofów'` lub write_to_file → scp → ssh
2. Klucz SSH: `C:\Users\tomas2\.ssh\oracle-crimson.key` (PEŁNA ścieżka Windows, nie ~)
3. VPS user: `ubuntu@147.224.162.100`
4. Pliki projektowe → zawsze GitHub MCP, NIE lokalny klon
5. Po każdej akcji → weryfikacja outputu

---

## 🎯 Twoje zadanie

Jesteś `[vse-log-analyst-01]`. Analizujesz logi VSE na VPS Oracle, żeby zweryfikować czy fixy z 22-23.07.2026 działają poprawnie.

**Kontekst:**
- Generowanie przez Usera NIE potwierdza działania fixów
- Supervisor zleca niezależną analizę logów
- Możliwe że fixy są w repo ale nie wylądowały na VPS (brak git pull/docker rebuild)

---

## 🔍 Co weryfikujesz

### Fix 1 — post_excerpt (commit ab1ce1f, 23.07.2026)
- **Co zmieniono:** `lead` usunięty z `post_excerpt`, zostaje tylko w `post_content`
- **Verify:** Sprawdź czy commit ab1ce1f jest na VPS (`git log --oneline -5`)
- **Sprawdź logi:** Czy po generowaniu widać że `post_excerpt` jest pusty/skrócony (nie zawiera pełnego leadu)

### Fix 2 — YouTube 403 / OAuth scope (commit 23a599f, 22.07.2026)
- **Co zmieniono:** `youtube.force-ssl` scope dodany do `_build_credentials()` — fix 403 Forbidden przy `videos.update`
- **Verify:** Sprawdź czy commit jest na VPS
- **Sprawdź logi:** Szukaj `403`, `Forbidden`, `youtube`, `scope` w logach vse-api

### Fix 3 — VTT truncation (commit 9c116257, 14.07.2026)
- **Verify:** Czy jest na VPS
- **Sprawdź logi:** Szukaj `vtt`, `transcript`, `truncat` w logach

---

## 📋 Kroki do wykonania

### Krok 1: Status VPS — czy serwis działa
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
```

### Krok 2: Który commit jest na VPS
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git log --oneline -8"
```

### Krok 3: Logi vse-api — ostatnie 200 linii
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker logs vse-api --tail 200 2>&1"
```

### Krok 4: Szukaj błędów i kluczowych słów w logach
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker logs vse-api --tail 500 2>&1 | grep -iE '403|forbidden|error|exception|vtt|truncat|excerpt|scope' | tail -50"
```

### Krok 5: Jeśli fixów NIE MA na VPS — sprawdź czy można zrobić git pull
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git fetch origin && git status"
```

> **UWAGA:** NIE wykonuj git pull ani docker rebuild bez zlecenia Supervisora. Tylko raportuj stan.

### Krok 6: Sprawdź ostatnie generowanie — co wygenerował system
Jeśli baza danych jest dostępna przez docker exec:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker exec vse-db psql -U postgres -c 'SELECT id, title, LEFT(post_excerpt, 100), updated_at FROM articles ORDER BY updated_at DESC LIMIT 5;' 2>&1"
```
*(Dostosuj nazwę kontenera i schemat jeśli inny)*

---

## 📨 Raport do Supervisora

Na końcu napisz raport w formacie:

```
📨 RAPORT DO [Supervisor 01]

## VSE Log Analysis — 23.07.2026

### Stan VPS
- Docker: [lista serwisów]
- Commit na VPS: [hash] [opis]
- Fixy: ab1ce1f ✅/❌ | 23a599f ✅/❌ | 9c116257 ✅/❌

### Logi — kluczowe obserwacje
- 403/Forbidden: [czy widać]
- VTT/truncation: [czy widać]
- post_excerpt: [czy widać zmiany]
- Inne błędy: [lista]

### Rekomendacja
- [co należy zrobić]
```

Raport zapisz:
1. `video-seo-engine/.agents/reports/2026-07-23_vse-log-analyst-01_log-verification.md`
2. `sonic-void/.agents/reports/inbox/2026-07-23_vse-log-analyst-01_log-verification.md`

---

*Dispatch: [Supervisor 01 | sonic-void 23.07.2026 19:04]*
*Priorytet: WYSOKI — weryfikacja aktywnych fixów produkcyjnych*
