# DISPATCH — vse-dev-28 — Image Descriptions Fix + Hardcoded prawy.pl

**Dispatch ID:** D14  
**Callsign:** vse-dev-28  
**Priorytet:** 🔴 WYSOKI  
**Data:** 2026-06-21  
**Wystawiony przez:** Supervisor 02  

---

## KONTEKST

E2E test na Kurier365.pl wykazał, że obrazki uploadowane do WordPressa:
- Mają **PUSTY alt text**
- Mają **PUSTY caption**  
- Mają **PUSTY description**
- Tytuł: generyczny `"Video Thumbnail: Tytus,"` (ucięty)
- W URL/nazwie pliku pojawia się **"prawy.pl"** mimo że portal to Kurier365

To blokuje RankMath scoring (wymagane: alt text z frazą kluczową).

## ZADANIE

### 1. Diagnostyka na VPS

Sprawdź logi:
```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  'docker logs vse-api --tail 500 2>&1 | grep -iE "image|thumbnail|saas|describe|upload|prawy|alt|caption"'
```

### 2. Analiza kodu — upload obrazków

Przeczytaj:
```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: video-seo-engine
  branch: main
  path: core/injector.py
```

Szukaj `_upload_image_to_wp()` lub podobnej funkcji. Sprawdź:
- Czy przekazuje `alt_text`, `caption`, `description` do WP REST API?
- WP Media REST API wymaga tych pól w POST `/wp-json/wp/v2/media`:
  - `alt_text` (meta pole)
  - `caption` (w body)
  - `description` (w body)
  - `title` (w body)

### 3. Fix — Image Metadata

Upewnij się że:
1. **Alt text** = opisowy tekst z frazą kluczową (powinien być generowany przez LLM w `image_descriptions` lub przez SAAS Vision API)
2. **Title** = pełny, nie ucięty
3. **Caption** = krótki opis
4. Wywołanie API: `POST /wp-json/wp/v2/media/{id}` z body `{"alt_text": "...", "caption": "...", "description": "..."}`

Jeśli `image_descriptions` są generowane przez LLM ale nie przekazywane do WP:
- Podłącz je w `_upload_image_to_wp()` 
- Jeśli SAAS Vision API jest skonfigurowane — użyj jeśli dostępne, fallback na LLM

### 4. Fix — Hardcoded prawy.pl

Szukaj w CELU repozytoriach:
```
mcp_github_search_code:
  q: "prawy.pl repo:gitomwtyczka/video-seo-engine"
```

Zastąp hardcoded `prawy.pl` danymi z profilu portalu (`profiles/*.yaml`).
Może być w:
- Nazwie pliku thumbnail
- Template nazwy obrazka
- Fallback URL gdziekolwiek w kodzie

### 5. Deploy + Weryfikacja

Po commit:
```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  'cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose up -d --build'
```

## OUTPUT

Raport + dual-write:
```
video-seo-engine/.agents/reports/2026-06-21_vse-dev-28_image-descriptions-d14.md
sonic-void/.agents/reports/inbox/2026-06-21_vse-dev-28_image-descriptions-d14.md
```

## CREDENTIALS

SSH: `~/.ssh/oracle-crimson.key`, user `ubuntu`, IP `147.224.162.100`
GitHub MCP: standardowy dostęp

---

*[Supervisor 02 | sonic-void 21.06.2026 17:43]*