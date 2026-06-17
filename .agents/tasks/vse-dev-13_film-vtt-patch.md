# Task: vse-dev-13 — Format "Film" + VTT badge link

**Dispatch by:** Supervisor 04  
**Data:** 2026-06-17  
**Projekt:** video-seo-engine  
**Repo:** gitomwtyczka/video-seo-engine | branch: main  
**VPS:** `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100`  
**App:** https://vse.impresjapr.pl

---

## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

Przeczytaj blok systemowy:
```
video-seo-engine/.agents/protocols/dispatch-system-block.md (jeśli istnieje)
```
lub użyj SSH do zapoznania się ze strukturą projektu.

---

## Kontekst

Dev-12 wdrożył obsługę portali WordPress (Kurier365 i inne). Test wysyłki przeszedł pomyślnie.
Dwa elementy nie weszły do produkcji:
1. **Format "Film"** — brakuje go w oknie publikacji VSE (modal publish)
2. **VTT badge → link** — w /historia badge z liczbą rozdziałów nie linkuje do pliku VTT

---

## Zadanie 1 — Format "Film" w oknie publikacji

### Co zrobić
W oknie modalnym publikacji VSE (frontend — prawdopodobnie komponent `PublishModal` lub podobny) brakuje opcji formatu wpisu "Film".

Sprawdź:
- Frontend: jakie formaty wpisu są dostępne w modalu publikacji
- Porównaj z formatami WordPress (standard, aside, image, video, **film** / post-format)
- Dodaj opcję "Film" do selecta / radio buttons w formularzu publikacji
- Upewnij się że format jest przekazywany do WordPress API przy publikacji (`post_format` lub `format` w WP REST API)

### Kroki implementacji
1. Znajdź komponent modalu publikacji w frontendzie VSE
2. Sprawdź jak inne formaty są zdefiniowane
3. Dodaj format "Film" (value: `video` w WP API)
4. Zweryfikuj że payload do WP REST API zawiera `format: video`
5. Test: opublikuj testowy wpis z formatem Film, sprawdź na portalu

---

## Zadanie 2 — VTT badge → link do pliku transkrypcji

### Co zrobić
W widoku /historia każdy artykuł z transkrypcją VTT pokazuje badge z liczbą rozdziałów.
Badge powinien być klikalny i linkować do pliku VTT (lub otwierać podgląd).

Sprawdź:
- Komponent historii — gdzie renderowany jest badge z liczbą rozdziałów
- Czy ścieżka/URL do pliku VTT jest dostępna w danych artykułu
- Dodaj `<a href={vttUrl}>` owijający badge (lub przycisk obok)
- Jeśli URL VTT nie jest w danych — sprawdź endpoint API i czy można go dodać

### Kroki implementacji
1. Znajdź komponent badge'a VTT w /historia
2. Sprawdź strukturę danych (czy vtt_url lub vtt_path jest dostępny)
3. Dodaj link do pliku VTT
4. Jeśli VTT jest serwowany statycznie — upewnij się że URL jest publiczny
5. Test: kliknij badge, sprawdź czy otwiera plik VTT

---

## Definition of Done

- [ ] Format "Film" widoczny i działający w modalu publikacji
- [ ] VTT badge linkuje do pliku transkrypcji
- [ ] Zmiany zdeployowane na VPS (`docker compose up -d --build` lub odpowiednik)
- [ ] Raport do Supervisora: `video-seo-engine/.agents/reports/2026-06-17_vse-dev-13_film-vtt.md`
- [ ] Ten sam raport do `sonic-void/.agents/reports/inbox/`
- [ ] Heartbeat zaktualizowany (`status: done`)

---

## Raport końcowy (szablon)

```
📋 RAPORT — vse-dev-13
🎯 Agent: [callsign]
## Zadanie 1 (Format Film): [status + co zmieniono]
## Zadanie 2 (VTT badge): [status + co zmieniono]
## Commity: [SHA]
## Blokery: [jeśli były]
```
