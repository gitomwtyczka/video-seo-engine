# DISPATCH: VSE-DEV-24 — D8: Linki wewnętrzne (internal_links)

**Data:** 2026-06-20  
**Priorytet:** 🟡 WAŻNY  
**Zlecający:** Supervisor 01  
**Przypisany do:** vse-dev-24  
**Repo:** video-seo-engine (branch: main)  
**VPS:** ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100

---

## Kontekst

RankMath audyt (vse-analyst-05) wskazał brak linków wewnętrznych jako ~5 pkt w scoringu. Mechanizm `internal_links` **JUŻ ISTNIEJE** w kodzie:

- `core/generator.py` linia ~228: `generate_seo_v4()` przyjmuje `internal_links: Optional[list[dict]]`
- `api/services/pipeline.py` linia ~296: `internal_links = extract_internal_links(saas_data)`
- `api/services/saas_enricher.py` linia ~307: `def extract_internal_links(saas_data, max_links=10)`

**Problem:** Nikt nie dostarcza danych. `extract_internal_links()` zwraca pustą listę bo `saas_data` nie ma pola z linkami wewnętrznymi, albo SAAS API nie zwraca tych danych.

**Cel:** Sprawić żeby pipeline dokonywał wstrzykiwania linków wewnętrznych do generowanych artykułów.

---

## Scope

### 1. Diagnoza źródła danych

Zbadaj skąd miałyby pochodzić linki wewnętrzne:

**Opcja A: Z SAAS API (crimson-void)**
- Sprawdź co zwraca `get_saas_seo_data()` — czy jest pole z linkami
- Sprawdź SAAS endpoint (`crimson-void`) czy ma dane o opublikowanych artykułach

**Opcja B: Z WordPress API portalu (self-sourcing)**
- Query WP REST API: `GET /wp-json/wp/v2/posts?per_page=10&orderby=date` → ostatnie artykuły
- Wyłącz linkowanie do siebie samego (ten sam video_id)
- Filtruj po kategorii/tagu jeśli możliwe

**Opcja C: Z registry (lokalny cache)**
- VSE ma `data/prawy/registry/` z opublikowanymi artykułami
- Każdy wpis ma `wp_url` → można użyć jako internal link

### 2. Implementacja

Po wyborze źródła:
1. Zaimplementuj pobieranie listy `[{"url": "...", "title": "..."}]`
2. Przekaz do `generate_seo_v4(internal_links=...)`
3. Generator już wstrzykuje do promptu LLM — weryfikuj że działa
4. Zweryfikuj że wygenerowany artykuł zawiera `<a href="...">` z internal links

### 3. Walidacja

- Wygeneruj artykuł testowy z internal links
- Sprawdź HTML: czy są linki do innych artykułów na tym samym portalu
- Sprawdź że linki mają poprawny `rel` (bez noreferrer — to wewnętrzne!)
- RankMath: czy "internal links" check przechodzi

### 4. Deploy

**ZASADA DEPLOY:** Przed deploy sprawdź flagę:
```bash
ssh ... "test -f /home/ubuntu/video-seo-engine/.deploy_lock && echo LOCKED || echo FREE"
```
- LOCKED → czekaj
- FREE → `touch .deploy_lock && git pull && docker compose up -d --build && rm .deploy_lock`

---

## Zasady

- ✅ Zachowaj wsteczną kompatybilność — brak linków = działa jak dotychczas
- ✅ Max 10 linków (już ograniczone w `_build_saas_prompt_section`)
- ✅ Nie linkuj do siebie samego
- VPS: `ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100`
- Pliki repo: GitHub MCP
- Złożone komendy SSH z $zmiennymi: write_to_file → scp → ssh (NIGDY inline PowerShell!)
- ⛔ NIE UŻYWAJ: file bridge, Wetty, stellar-relay

---

## Deliverables

1. Diagnoza źródła danych (A/B/C + uzasadnienie)
2. Implementacja pobierania + przekazywania internal_links
3. Test: wygenerowany artykuł z linkami wewnętrznymi
4. Deploy + weryfikacja na VPS
5. **Dual-write raport:** `video-seo-engine/.agents/reports/` + `sonic-void/.agents/reports/inbox/`

---

*Supervisor 01 | sonic-void | 20.06.2026*
