# DISPATCH — D10: Smart External Links (Authority Sources)

**Callsign:** vse-dev-25  
**Dispatch:** DISPATCH-VSE-DEV-25-20260621-SMART-EXTERNAL-LINKS-D10  
**Projekt:** video-seo-engine  
**Priorytet:** 🔴 KRYTYCZNY (blokuje 80+ RankMath)  
**Data:** 2026-06-21  
**Wystawiony przez:** Supervisor 01  

---

## CEL

Rozbudowa mechanizmu linków zewnętrznych tak, aby generator LLM wplatał w artykuł **2-3 linki DoFollow do authority sources** które Google wysoko waży.

## PROBLEM

RankMath 68/100 z flagami:
- ❌ „Linkuj do zasobów zewnętrznych”
- ❌ „Dodaj DoFollow wskazujące na zasoby zewnętrzne”

D4 dodał podstawowy mechanizm external links, ale brakuje **konkretnych, autorytywnych źródeł** które Google traktuje jako sygnał jakości (E-E-A-T).

## SPECYFIKACJA IMPLEMENTACJI

### Plik: `core/generator.py` — zmiana w prompcie

W funkcji `generate_seo_v4()` w sekcji promptu „CO WYGENEROWAĆ” dodaj nowy punkt:

```
15. **external_links** — lista 2-3 linków zewnętrznych DoFollow do źródeł wysokiego autorytetu.
    Każdy link to dict: {"url": "...", "anchor_text": "...", "reason": "..."}
    ZASADY:
    a) Źródła które Google wysoko waży:
       - Wikipedia (polski artykuł tematyczny)
       - Strony .gov.pl (oficjalne źródła rządowe: sejm.gov.pl, gov.pl, prezydent.pl)
       - PAP, Reuters, AP — agencje prasowe
       - Instytucje naukowe/think-tanki (PISM, OSW, uniwersytety)
       - YouTube (link do oryginalnego wideo)
    b) Linki MUSZĄ być tematycznie powiązane z treścią artykułu
    c) anchor_text to naturalny tekst w który jest wpleciony link
       (np. "jak podaje [Polska Agencja Prasowa](https://...)")
    d) Nie wymyślaj URL-i — podaj REALNE adresy stron, które ISTNIEJĄ
    e) reason: krótkie uzasadnienie dlaczego to źródło jest authority
```

Dodaj też instrukcję w sekcji `article_body`:
```
   W article_body MUSISZ wplatać min. 2 linki DoFollow do zewnętrznych źródeł authority.
   Użyj anchor textów z pola external_links. Format: <a href="URL" target="_blank">anchor</a>
   Linki muszą brzmieć naturalnie w kontekście zdania.
```

W response JSON template dodaj:
```json
"external_links": [{"url": "...", "anchor_text": "...", "reason": "..."}]
```

### Plik: `core/injector.py` — weryfikacja

Sprawdź czy `article_body` z linkami <a href> jest poprawnie wstrzykiwany do WP.
Jeśli injector strippuje tagi HTML — upewnij się że <a> jest zachowywane.

### NIE ZMIENIAJ:
- `pipeline.py` — nie wymaga zmian (external_links to część LLM output)
- Endpointów API — bez zmian
- Frontend — bez zmian

## WERYFIKACJA

1. Wygeneru artykuł (POST /v1/generate z dowolnym video)
2. Sprawdź czy response JSON zawiera `external_links` (2-3 itemy)
3. Sprawdź czy `article_body` zawiera min. 2 tagi `<a href=` do external sources
4. Sprawdź czy linki są do realnych authority domen (wikipedia, .gov.pl, PAP itp.)
5. Inject do WP — sprawdź czy linki przetrwały (nie zostały usunięte)

## DEPLOY

Po commitach do `main`:
```powershell
# Napisz skrypt do pliku
$script = @'
cd /home/ubuntu/video-seo-engine
git pull origin main
docker compose -f docker-compose.vse.yml build vse-api
docker compose -f docker-compose.vse.yml up -d vse-api
sleep 3
curl -s http://localhost:8085/health
'@
$script | Set-Content -Path "$env:TEMP\deploy_d10.sh" -Encoding UTF8 -NoNewline
scp -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no "$env:TEMP\deploy_d10.sh" ubuntu@147.224.162.100:/tmp/deploy_d10.sh
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 'bash /tmp/deploy_d10.sh'
```

## DUAL-WRITE RAPORT

Po zakończeniu:
1. Raport do `video-seo-engine/.agents/reports/`
2. Raport do `sonic-void/.agents/reports/inbox/2026-06-21_vse-dev-25_D10-smart-external-links.md`
3. Heartbeat status: `done`

---

*[Supervisor 01 | sonic-void 21.06.2026 00:44] — dispatch D10*