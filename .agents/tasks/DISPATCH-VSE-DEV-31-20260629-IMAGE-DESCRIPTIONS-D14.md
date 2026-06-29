## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**0. Wczytaj blok systemowy:**
view_file → C:\Users\tomas2\.gemini\antigravity\playground\sonic-void\.agents\protocols\dispatch-system-block.md

---

# DISPATCH D14 — Image Descriptions Fix

**Callsign:** vse-dev-31  
**Projekt:** video-seo-engine  
**Data:** 2026-06-29  
**Priorytet:** 🔴 WYSOKI — RankMath traci punkty za brak alt/caption

---

## Twój deliverable

Działający commit na VPS + raport. Obrazki generowane przez pipeline muszą mieć wypełnione `alt`, `caption`, `description` w WordPress. Dodatkowo: usunąć hardcoded `prawy.pl` z kodu.

---

## Kontekst

E2E test z 2026-06-21 wykazał (handoff Supervisor 01 → E2E issues):

1. **WP Media screen:** Alt text = PUSTY, Caption = PUSTY, Description = PUSTY
2. **Tytuł obrazka:** `"Video Thumbnail: Tytus,"` (generyczny, ucięty)
3. **URL obrazka:** zawiera `prawy.pl` mimo że portal to Kurier365

Prawdopodobne przyczyny:
- `_upload_image_to_wp()` w `core/injector.py` NIE przekazuje `alt_text`, `caption`, `description` do WP REST API
- `prawy.pl` jest hardcoded gdzieś w kodzie (szukaliśmy, ale wróciło)

---

## Kroki diagnostyczne

### Krok 1: Przeczytaj `core/injector.py` z GitHub MCP

```
mcp_github_get_file_contents:
  owner: gitomwtyczka  repo: video-seo-engine  path: core/injector.py
```

### Krok 2: Znajdź `_upload_image_to_wp()` i sprawdź:
- Czy `alt_text` jest przekazywane do `wp.media().create()`?
- Czy `caption` i `description` są przekazywane?
- Skąd pochodzi `title` obrazka?

### Krok 3: Wyszukaj hardcoded `prawy.pl`

```
mcp_github_search_code:
  q: prawy.pl repo:gitomwtyczka/video-seo-engine
```

Lub sprawdzić generator.py, injector.py, config/ grep przez SSH:
```bash
ssh root@147.224.162.100 "grep -r 'prawy\.pl' /home/ubuntu/video-seo-engine --include='*.py' -n"
```

### Krok 4: Sprawdź logi VPS — czy SAAS Vision API było wywoływane

```bash
ssh root@147.224.162.100 "docker logs vse-api --tail 300 2>&1 | grep -i 'image\|thumbnail\|saas\|describe\|upload\|prawy'"
```

---

## Co naprawić

### Fix 1: `_upload_image_to_wp()` — przekazanie metadata

WP REST API przyjmuje `alt_text`, `caption`, `description` przy upload:
```python
# Przykład poprawnego wywołania:
response = requests.post(
    f"{wp_url}/wp-json/wp/v2/media",
    headers={"Authorization": f"Basic {auth}"},
    files={"file": (filename, image_data, mime_type)},
    data={
        "alt_text": alt_text,        # <— musi być przekazane
        "caption": caption,           # <— musi być przekazane
        "description": description,   # <— musi być przekazane
        "title": title,               # <— musi być przekazane
    }
)
```

Sprawdź czy `alt_text`/`caption`/`description` są przekazywane do funkcji `_upload_image_to_wp()` z miejsc gdzie jest wywoływana. Jeśli nie — przeciągnij je przez cały łańcuch wywołań.

### Fix 2: Usuń hardcoded `prawy.pl`

Każdy hardcoded string z `prawy.pl` zamień na dynamiczne pobranie z config/portal ustawień.
Portal URL powinien pochodzić z konfiguracji (`.env`, config.py, lub parametru funkcji).

---

## Deploy

```bash
ssh root@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose up -d --build vse-api"
```

## Weryfikacja

Po deploy sprawdź logi:
```bash
ssh root@147.224.162.100 "docker logs vse-api --tail 100 2>&1 | tail -50"
```

Jeśli masz możliwość — wygładaj 1 artykuł i sprawdzić WP Media, czy `alt` jest wypełniony.

---

## Raport końcowy

1. Raport: `.agents/reports/2026-06-29_vse-dev-31_image-descriptions-d14.md`
2. Dual-write do `sonic-void/.agents/reports/inbox/`
3. Heartbeat `status: done` z commit SHA
4. Jeśli znalazłeś bloker (np. SAAS Vision API nie wywoływane) — udokumentuj i napisz do Supervisora

---

*[Supervisor 01 | sonic-void 29.06.2026]*