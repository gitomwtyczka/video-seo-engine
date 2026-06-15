# API Reference — Video SEO Engine

> **CO:** Dokumentacja wszystkich endpointów FastAPI VSE z przykładami request/response.
>
> **PO CO:** Bez tego agenci i developerzy muszą czytać kod źródłowy żeby zrozumieć co każdy endpoint przyjmuje i zwraca. Ten dokument eliminuje tę potrzebę.
>
> **JAK:** Swagger UI dostępne na https://vse.impresjapr.pl/docs — interaktywne testowanie. Ten plik to statyczna referencja.

---

## Base URL

```
Produkcja:  https://vse.impresjapr.pl/api
Dev (VPS):  http://147.224.162.100:8085
Swagger UI: https://vse.impresjapr.pl/docs
```

**Routing nginx:** Żądania do `https://vse.impresjapr.pl/api/*` są strip-owane z `/api` i proxowane do FastAPI jako `/v1/*`.
Żądania do FastAPI bezpośrednio na `:8085` trafiają jako `/v1/*`.

---

## Autentykacja

**CO:** VSE używa JWT Bearer tokens dla endpointów wymagających zalogowania.

**PO CO:** Każdy request do chronionych endpointów musi potwierdzić tożsamość usera — bez tego każdy mógłby generować SEO i konsumować quota innych.

**JAK:**
1. Zaloguj się przez `POST /v1/auth/login` → otrzymujesz `access_token`
2. Dodaj header do każdego chronionego requestu:

```
Authorization: Bearer <access_token>
```

**Token lifetime:** Konfigurowany przez `JWT_EXPIRE_MINUTES` (domyślnie 60 minut).

---

## Endpointy

---

### GET /health

**CO:** Sprawdza czy API działa i jaka jest konfiguracja.
**PO CO:** Monitoring, health checks deploymentu, weryfikacja że LLM jest poprawnie skonfigurowany.
**Auth:** Nie wymagana.

**Request:**
```http
GET /health HTTP/1.1
Host: vse.impresjapr.pl
```

**Response 200:**
```json
{
  "status": "ok",
  "version": "2.0.0",
  "llm_default": "claude"
}
```

---

### POST /v1/auth/register

**CO:** Rejestruje nowego użytkownika.
**PO CO:** Tworzy konto z planem `free` (domyślny). Bez rejestracji użytkownik nie może korzystać z dashboardu.
**Auth:** Nie wymagana.

**Request:**
```http
POST /v1/auth/register HTTP/1.1
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "bezpieczneHaslo123"
}
```

**Response 201:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "plan_id": "free",
  "is_active": true,
  "created_at": "2026-06-15T12:00:00Z"
}
```

**Error 400 — email zajęty:**
```json
{"detail": "Email already registered"}
```

---

### POST /v1/auth/login

**CO:** Loguje użytkownika, zwraca JWT token.
**PO CO:** Token jest potrzebny do wszystkich chronionych endpointów. NextAuth wywołuje ten endpoint przy logowaniu przez frontend.
**Auth:** Nie wymagana.

**Request:**
```http
POST /v1/auth/login HTTP/1.1
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "bezpieczneHaslo123"
}
```

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Error 401 — złe credentials:**
```json
{"detail": "Invalid credentials"}
```

---

### POST /v1/generate

**CO:** Generuje SEO schema dla podanego URL YouTube — tytuł, opis, VideoObject JSON-LD, FAQ, rozdziały.
**PO CO:** To jest główna wartość produktu. Klient wkleja URL → dostaje gotowe dane SEO do skopiowania lub publikacji. W wersji free to jedyny krok. W wersji pro jest wstępem do automatycznej publikacji na WordPress.
**Auth:** Wymagana (Bearer token).
**Czas:** ~50 sekund (Claude Sonnet).

**Request:**
```http
POST /v1/generate HTTP/1.1
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response 200:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "article_title": "Rick Astley - Never Gonna Give You Up | Analiza i SEO",
  "meta_description": "Kompletna analiza SEO...",
  "schema_json_ld": {
    "@context": "https://schema.org",
    "@type": "VideoObject",
    "name": "Rick Astley - Never Gonna Give You Up",
    "description": "...",
    "thumbnailUrl": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
    "uploadDate": "2009-10-25T00:00:00+00:00",
    "duration": "PT3M33S",
    "contentUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "embedUrl": "https://www.youtube.com/embed/dQw4w9WgXcQ",
    "interactionStatistic": {
      "@type": "InteractionCounter",
      "interactionType": "https://schema.org/WatchAction",
      "userInteractionCount": 1500000000
    }
  },
  "faq": [
    {
      "question": "O czym jest ten film?",
      "answer": "..."
    }
  ],
  "chapters": [
    {
      "title": "Intro",
      "start_seconds": 0,
      "end_seconds": 30
    }
  ],
  "processing_time_seconds": 48.3
}
```

**Error 422 — brak video_url:**
```json
{"detail": [{"loc": ["body", "video_url"], "msg": "field required"}]}
```

**Error 500 — YouTube niedostępne:**
```json
{"detail": "Failed to fetch transcript: TranscriptsDisabled"}
```

---

### POST /v1/inject

**CO:** Publikuje wygenerowane dane SEO do wskazanego artykułu WordPress.
**PO CO:** Użytkownicy pro/agency nie chcą ręcznie kopiować JSON-LD do WordPressa. Ten endpoint robi to automatycznie — aktualizuje post przez WP REST API.
**Auth:** Wymagana (Bearer token). Tylko plany `pro` i `agency`.

**Request:**
```http
POST /v1/inject HTTP/1.1
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "wp_base_url": "https://prawy.pl",
  "wp_user": "redaktor",
  "wp_app_password": "xxxx xxxx xxxx xxxx xxxx xxxx",
  "post_id": 12345,
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "status": "draft"
}
```

> **Uwaga:** `wp_app_password` to WordPress Application Password (generuj w WP Admin → Users → Application Passwords). NIE podawaj głównego hasła.

**Pola `status`:** `"draft"` | `"publish"`

**Response 200:**
```json
{
  "success": true,
  "post_id": 12345,
  "wp_url": "https://prawy.pl/?p=12345",
  "status": "draft",
  "schema_injected": true,
  "rankmath_updated": true
}
```

**Error 403 — plan za niski:**
```json
{"detail": "Endpoint requires pro or agency plan"}
```

**Error 502 — WP niedostępne:**
```json
{"detail": "WordPress API error: 401 Unauthorized"}
```

---

### POST /v1/process

**CO:** Full pipeline w jednym kroku: fetch → generate → inject.
**PO CO:** Przeznaczony dla batch processing i integracji zewnętrznych. Dashboard używa oddzielnie `/generate` i `/inject` (daje kontrolę nad wynikami przed publikacją). Ten endpoint jest dla automatyzacji gdzie wynik pośredni nie jest potrzebny.
**Auth:** Wymagana (Bearer token). Tylko plany `pro` i `agency`.

**Request:**
```http
POST /v1/process HTTP/1.1
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "wp_base_url": "https://prawy.pl",
  "wp_user": "redaktor",
  "wp_app_password": "xxxx xxxx xxxx xxxx xxxx xxxx",
  "post_id": 12345,
  "status": "draft"
}
```

**Response 200:** Połączony output z generate + inject (patrz wyżej).

---

### POST /v1/monitor/start

**CO:** Uruchamia monitor kanału YouTube — background task sprawdzający nowe filmy.
**PO CO:** Agencje chcą zero-touch — nowy film na kanale = automatyczny artykuł draft na portalu. Ten endpoint startuje daemona który to realizuje.
**Auth:** Wymagana. Tylko `agency`.
**Status:** Zaimplementowany, wymaga testów E2E.

**Request:**
```http
POST /v1/monitor/start HTTP/1.1
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "channel_url": "https://www.youtube.com/@PrawyTV",
  "wp_base_url": "https://prawy.pl",
  "wp_user": "redaktor",
  "wp_app_password": "xxxx xxxx xxxx xxxx xxxx xxxx",
  "check_interval_minutes": 30,
  "status": "draft"
}
```

**Response 200:**
```json
{
  "monitor_id": "mon_abc123",
  "status": "started",
  "channel": "@PrawyTV",
  "check_interval_minutes": 30
}
```

---

### GET /v1/sitemap

**CO:** Generuje video sitemap XML dla skonfigurowanego portalu.
**PO CO:** Google wymaga video sitemap żeby indeksować filmy YouTube osadzone na portalu. RankMath nie wykrywa wszystkich filmów — ten endpoint generuje kompletny sitemap z danymi schema.
**Auth:** Wymagana.

**Request:**
```http
GET /v1/sitemap?wp_base_url=https://prawy.pl HTTP/1.1
Authorization: Bearer <access_token>
```

**Response 200:** XML (Content-Type: application/xml)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">
  <url>
    <loc>https://prawy.pl/artykul/przykladowy</loc>
    <video:video>
      <video:thumbnail_loc>https://i.ytimg.com/vi/VIDEO_ID/maxresdefault.jpg</video:thumbnail_loc>
      <video:title>Tytuł wideo</video:title>
      <video:description>Opis...</video:description>
      <video:content_loc>https://www.youtube.com/watch?v=VIDEO_ID</video:content_loc>
      <video:player_loc>https://www.youtube.com/embed/VIDEO_ID</video:player_loc>
      <video:duration>213</video:duration>
      <video:publication_date>2026-01-15</video:publication_date>
    </video:video>
  </url>
</urlset>
```

---

### GET /docs

**CO:** Swagger UI — interaktywna dokumentacja API.
**PO CO:** Pozwala testować endpointy bez pisania kodu. Pokazuje aktualne schematy Pydantic.
**Auth:** Nie wymagana.
**URL:** https://vse.impresjapr.pl/docs

---

## Kody błędów

| Kod | Znaczenie | Typowa przyczyna |
|---|---|---|
| 200 | OK | Sukces |
| 201 | Created | Rejestracja użytkownika |
| 400 | Bad Request | Złe dane wejściowe |
| 401 | Unauthorized | Brak lub wygasły token |
| 403 | Forbidden | Plan za niski dla endpointu |
| 422 | Unprocessable Entity | Błąd walidacji Pydantic |
| 500 | Internal Server Error | Błąd serwera (sprawdź logi) |
| 502 | Bad Gateway | nginx nie może dosięgnąć FastAPI lub WP API |
| 503 | Service Unavailable | Kontener nie działa |

---

## Przykład — pełny flow przez curl

```bash
# 1. Rejestracja
curl -X POST https://vse.impresjapr.pl/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email": "test@example.com", "password": "Haslo1234!"}'

# 2. Login → token
TOKEN=$(curl -s -X POST https://vse.impresjapr.pl/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "test@example.com", "password": "Haslo1234!"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# 3. Generate SEO
curl -X POST https://vse.impresjapr.pl/api/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'

# 4. Health check
curl https://vse.impresjapr.pl/api/health
```

---

*vse-architect-01 | video-seo-engine | 2026-06-15 — v1.0*
*Aktualizuj przy każdej zmianie endpointów — nowe pola, nowe kody błędów, zmiany w response schema.*
