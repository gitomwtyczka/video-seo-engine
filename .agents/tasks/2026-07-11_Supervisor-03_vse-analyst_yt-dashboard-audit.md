# Dispatch: Audyt — zakładka YouTube w dashboardzie
**Od:** Supervisor-03  
**Do:** vse-analyst (Flash — tylko odczyt, zero zmian w kodzie)  
**Data:** 2026-07-11  
**Typ:** ANALITYKA — tylko read, raport, zero implementacji

---

## CEL

Ustaleć czy zakładka/sekcja z treściami przeznaczonymi na YouTube (harmonogram, kolejka, historia publikacji YT) jest już zaimplementowana w backendzie i/lub frontendzie, czy też jesteśmy przed implementacją.

---

## ⚠️ ZNANE PUŁAPKI
1. Nie modyfikuj żadnych plików — tylko czytaj.
2. Używaj GitHub MCP do odczytu (nie lokalny klon).
3. SSH tylko jeśli potrzebujesz sprawdzić żywe logi lub DB schema.

---

## CO SPRAWDZIĆ

### 1. Frontend — nawigacja dashboardu

Pobierz i sprawdź:
- `web/src/app/dashboard/` — jakie zakładki/strony istnieją?
- `web/src/components/` lub podobne — czy jest komponent z listą/harmonogramem YT?
- Czy w nawigacji (sidebar) jest pozycja związana z YouTube poza Ustawieniami?

Szczególnie szukaj: `youtube`, `schedule`, `queue`, `publikacja`, `video`, `yt`

### 2. Backend — endpointy YT poza OAuth

Pobierz `api/routers/youtube.py` — jakie endpointy istnieją poza `/oauth/login`, `/oauth/callback`, `/channels`?

Czy istnieją routery/pliki dla:
- harmonogramu publikacji
- kolejki materiałów
- historii publikacji na YT
- statusu pipeline

Grep po repo:
```
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "find /home/ubuntu/video-seo-engine/api -name '*.py' | xargs grep -l 'youtube\|video\|publish\|schedule' 2>/dev/null"
```

### 3. DB Schema — tabele YT

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker exec vse-postgres psql -U vse -d vse -c '\dt'"
```

Jakie tabele istnieją? Czy są tabele dla harmonogramu/publikacji/historii YT?

### 4. Dashboard — strona główna

Pobierz `web/src/app/dashboard/page.tsx` lub `dashboard-inner.tsx` — co jest aktualnie wyświetlane? Jakie sekcje/zakładki?

---

## FORMAT RAPORTU (dual-write)

Zapisz raport do:
1. `video-seo-engine/.agents/reports/2026-07-11_vse-analyst_yt-dashboard-audit.md`
2. `sonic-void/.agents/reports/inbox/2026-07-11_vse-analyst_yt-dashboard-audit.md`

### Struktura raportu:

```markdown
# Audyt: Zakładka YouTube w dashboardzie

## Status implementacji
[ ] Nie istnieje — trzeba zbudować od zera
[ ] Częściowo — backend jest, frontend brakuje
[ ] Częściowo — frontend jest, backend brakuje  
[ ] Istnieje ale nie jest widoczne w nawigacji

## Frontend — znalezione pliki i komponenty
[lista]

## Backend — znalezione endpointy
[lista]

## DB — tabele powiązane z YT
[lista]

## Dashboard — aktualne sekcje
[lista]

## Wniosek
[Co jest, czego brakuje, co trzeba zbudować]

## Szacunek zakresu pracy (jeśli implementacja konieczna)
[orientacyjnie: małe/średnie/duże + główne pliki do stworzenia]
```

---

*[Supervisor-03 | sonic-void 11.07.2026]*