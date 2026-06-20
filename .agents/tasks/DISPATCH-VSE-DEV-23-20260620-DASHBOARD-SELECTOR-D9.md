# DISPATCH: VSE-DEV-23 — Dashboard: selektor portalu i typu publikacji

**Data:** 2026-06-20  
**Priorytet:** 🔴 KRYTYCZNY (blokuje testowanie D6b+D7)  
**Zlecający:** Supervisor 01  
**Przypisany do:** vse-dev-23  
**Repo:** video-seo-engine (branch: main)  
**VPS:** ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100

---

## Kontekst

D6b dodał backend: multi-site architekturę (kanały, profile, publication_type). D7 dodał SEO scoring. Ale **dashboard nie ma selektora portalu** — user nie może wybrać na który portal idzie artykuł. Bez tego nie da się przetestować żadnej z nowych funkcji.

**Cel:** Dodać do dashboardu możliwość wyboru portalu (profilu) i opcjonalnie typu publikacji PRZED generowaniem artykułu.

---

## Scope

### 1. Backend: endpoint lista profili

Sprawdź czy istnieje endpoint zwracający listę aktywnych profili. Jeśli nie:

```python
# GET /profiles → [{"id": "prawy", "display_name": "Prawy.pl", "active": true, "source_channels": [...]}]
```

Dane z katalogu `profiles/*.yaml` — filtruj tylko `active: true`.

### 2. Frontend: selektor w dashboardzie

**Plik główny:** `web/src/app/dashboard/dashboard-inner.tsx`

Dodaj PRZED przyciskiem generowania:
- **Dropdown "Portal"** — lista profili z endpointu
- **Dropdown "Typ publikacji"** (opcjonalny) — `full_analysis` / `watching_page` / `discover` (default: `full_analysis`)
- Wybrany portal propagowany do wywołania `/generate` jako parametr

UI powinno być spójne z istniejącym designem dashboardu.

### 3. API: przekazanie profilu do pipeline

Sprawdź jak `/generate` obecnie określa profil (prawdopodobnie `_resolve_site_url_from_env()`). Zmień żeby akceptował parametr `profile_id` z requestu:
- Jeśli podany → użyj tego profilu
- Jeśli nie podany → fallback na .env (wsteczna kompatybilność)

### 4. Deploy

**ZASADA DEPLOY:** Przed deploy sprawdź flagę deploy:
```bash
ssh ... "test -f /home/ubuntu/video-seo-engine/.deploy_lock && echo LOCKED || echo FREE"
```
- Jeśli LOCKED → czekaj (inny agent deployuje)
- Jeśli FREE → stwórz lock, deploy, usuń lock:
```bash
ssh ... "cd /home/ubuntu/video-seo-engine && touch .deploy_lock && git pull origin main && docker compose up -d --build && rm .deploy_lock"
```

---

## Zasady

- ✅ Zachowaj wsteczną kompatybilność — pipeline bez parametru = działa jak dotychczas
- ✅ Unit testy dla nowego endpointu
- ✅ Test na VPS po deploy
- VPS: `ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100`
- Pliki repo: GitHub MCP
- Złożone komendy SSH z $zmiennymi: write_to_file → scp → ssh (NIGDY inline PowerShell!)
- ⛔ NIE UŻYWAJ: file bridge, Wetty, stellar-relay

---

## Deliverables

1. Endpoint `/profiles` (lub potwierdzenie że istnieje)
2. Selektor w dashboardzie
3. Propagacja profilu do `/generate`
4. Deploy + test na VPS
5. **Dual-write raport:** `video-seo-engine/.agents/reports/` + `sonic-void/.agents/reports/inbox/`

---

*Supervisor 01 | sonic-void | 20.06.2026*
