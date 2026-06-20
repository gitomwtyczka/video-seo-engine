# A7: SAAS Image Description API — Analiza

**Callsign:** vse-analyst-07  
**Data:** 2026-06-21  
**Status:** ✅ Kompletny  

---

## 1. Endpoint SAAS do opisu obrazków

### 1.1 Lokalizacja w kodzie

**Plik:** `backend/routers/images.py` (29.5 KB)  
**Moduł:** `_generate_vision_seo()` — core helper (linia ~250-330)  

### 1.2 Endpointy

| Endpoint | Metoda | Auth | Opis |
|---|---|---|---|
| `/api/images/{image_id}/generate-seo` | POST | JWT (user session) | Generuj SEO dla jednego obrazka |
| `/api/images/generate-seo-batch` | POST | JWT (user session) | Batch: generuj SEO dla WSZYSTKICH obrazków artykułu |

### 1.3 Model AI

- **Model:** `gpt-4o` (OpenAI Vision)
- **Metoda:** Obraz przesyłany jako **base64** w `image_url` content block
- **Temperature:** 0.3
- **Max tokens:** 700
- **Kluczowe:** **WIDZI rzeczywisty obraz** — analizuje co jest na zdjęciu, nie zgaduje

### 1.4 Kontekst SEO (input)

Endpoint przyjmuje:
- `seo_phrase` (string, required) — główna fraza kluczowa artykułu
- `article_title` (string, optional) — tytuł artykułu
- `description_hint` (string, optional) — sugestia użytkownika co jest na zdjęciu
- **EXIF credit** — automatycznie wyciąga `Artist`/`Copyright` z EXIF metadanych

### 1.5 Wbudowane zasady anty-keyword-stuffing

Prompt zawiera explicite zasady:
- Fraza SEO **MUSI pojawić się TYLKO w polu `alt`** — naturalnie wpleciona
- W `title`, `caption`, `description` — **ZAKAZ powtarzania frazy dosłownie**
- Zamiast tego: synonimy, odmiany, frazy pokrewne

## 2. Format Request/Response

### 2.1 Request — Single Image

```http
POST /api/images/{image_id}/generate-seo
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "seo_phrase": "polityka podatkowa 2026",
  "description_hint": "minister na konferencji prasowej",
  "article_title": "Reforma podatkowa — co zmieni się w 2026?"
}
```

### 2.2 Request — Batch (per article)

```http
POST /api/images/generate-seo-batch
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "article_id": 123,
  "seo_phrase": "polityka podatkowa 2026",
  "article_title": "Reforma podatkowa"
}
```

### 2.3 Response — 5 pól SEO

```json
{
  "id": 42,
  "alt_text": "Polityka podatkowa 2026 — minister finansów przedstawia założenia reformy na konferencji",
  "seo_title": "Wystąpienie szefa resortu finansów na briefingu prasowym",
  "caption": "Szef resortu finansów omawia kluczowe założenia zmian fiskalnych na najbliższe lata.",
  "description": "Zdjęcie z konferencji prasowej w Ministerstwie Finansów. Na mównicy stoi minister, za nim ekran z prezentacją zmian fiskalnych. W tle widoczni dziennikarze z kamerami.",
  "suggested_filename": "polityka-podatkowa-2026-minister-konferencja-prasowa",
  "credit": "PAP",
  "status": "generated"
}
```

**Pola i ich przeznaczenie:**

| Pole | Długość | Przeznaczenie WP | SEO keyword? |
|---|---|---|---|
| `alt_text` | 50-125 zn. | `alt` atrybut `<img>` | ✅ TAK — naturalnie wpleciony |
| `seo_title` | 3-8 słów | title atrybut | ❌ NIE — synonim/opis sceny |
| `caption` | 1 zdanie | podpis pod obrazkiem | ❌ NIE |
| `description` | 2-3 zdania | WP Media Library opis | ❌ NIE |
| `suggested_filename` | max 80 zn. | SEO-friendly filename | ✅ TAK — prefix ze slug frazy |

## 3. Dostępność z VSE

### 3.1 Sieć

- **SAAS (crimson-void)** i **VSE (video-seo-engine)** działają na **tej samej maszynie VPS** (oracle-crimson, 147.224.162.100)
- SAAS backend (FastAPI) jest dostępny z Docker network jako `http://172.17.0.1:<PORT>` lub przez `http://localhost:<PORT>`
- Publicznie: `https://press.impresjapr.pl`

### 3.2 Auth — PROBLEM

**Aktualny stan:** Endpoint `/api/images/{image_id}/generate-seo` wymaga **JWT user session** (`Depends(get_current_user)`).

To oznacza:
- VSE musiałoby mieć konto użytkownika w SAAS
- VSE musiałoby logować się i utrzymywać JWT session
- To nie jest idealne dla M2M (machine-to-machine) komunikacji

**Istniejący M2M pattern:** SAAS ma już endpoint `/api/external/seo-data` z auth via `EXTERNAL_API_TOKEN` (Bearer static token). Ten sam wzorzec można zastosować dla image description.

### 3.3 Dodatkowy problem: Image must exist in SAAS DB

Endpoint wymaga `image_id` — obraz musi być:
1. Uploadowany do SAAS (`POST /api/images/upload`)
2. Zapisany na dysku SAAS (`data/images/`)
3. Zarejestrowany w DB SAAS (`article_images` table)

Dla VSE to oznacza dodatkowy krok: upload thumbnail → get image_id → generate SEO.

### 3.4 Czas przetwarzania

- GPT-4o Vision z base64 image: **~3-8 sekund** per obraz (szacunkowo)
- Batch: sekwencyjne, więc N obrazów × 3-8s

## 4. Rekomendacja Architektoniczna

### ✅ Rekomendacja: Opcja C — HYBRID (z nowym M2M endpoint)

```
YouTube thumbnail URL → VSE pipeline
    ├─ SAAS Image API (nowy M2M endpoint) → opisy vision-based (WIDZI obraz)
    ├─ LLM prompt (Claude) → kontekst artykułu + transkrypt
    └─ Merge: SAAS vision + LLM kontekst → finalne opisy
                                          → upload do WP Media z opisami
```

### Uzasadnienie

1. **Vision > Blind:** SAAS **WIDZI obraz** (GPT-4o Vision). VSE LLM pipeline opisuje thumbnail ślepo. Vision daje DOKŁADNIEJSZE opisy ("minister na mównicy" vs. "miniaturka wideo").

2. **Anty-keyword-stuffing:** SAAS ma wbudowane zasady rozmieszczenia keyword — fraza w alt, synonimy w title/caption/description. To jest SEO best practice.

3. **Istniejący pattern M2M:** External API router już ma `EXTERNAL_API_TOKEN` auth. Dodanie nowego endpointu `POST /api/external/describe-image` jest triwialne.

4. **Ta sama maszyna:** Zero latency sieciowej — VSE i SAAS na tym samym VPS.

### Co trzeba zaimplementować

#### W crimson-void (SAAS) — nowy M2M endpoint:

```python
# backend/routers/external.py — dodać:

class ImageDescribeRequest(BaseModel):
    image_url: str           # URL obrazka (np. YouTube thumbnail)
    seo_phrase: str          # główna fraza SEO
    article_title: str = ""  # tytuł artykułu
    description_hint: str = "" # sugestia

@router.post("/describe-image")
async def describe_image_external(
    req: ImageDescribeRequest,
    _token: str = Security(_require_token),  # M2M auth
):
    """
    M2M endpoint: pobiera obraz z URL, analizuje GPT-4o Vision,
    zwraca 5 pól SEO. Nie zapisuje do DB — stateless.
    """
    # 1. Fetch image from URL
    # 2. Base64 encode
    # 3. Call GPT-4o Vision with same prompt as _generate_vision_seo
    # 4. Return JSON with alt/title/caption/description/suggested_filename
```

#### W video-seo-engine (VSE) — D11 Faza B:

```python
# W injector lub nowym module image_seo.py:

def get_image_descriptions(thumbnail_url: str, seo_phrase: str, article_title: str) -> dict:
    """Call SAAS Image Description API (M2M)."""
    response = requests.post(
        "http://172.17.0.1:8000/api/external/describe-image",
        headers={"Authorization": f"Bearer {EXTERNAL_API_TOKEN}"},
        json={
            "image_url": thumbnail_url,
            "seo_phrase": seo_phrase,
            "article_title": article_title,
        },
        timeout=30,
    )
    return response.json()
```

### Zmiany potrzebne w D11

1. **Faza B (image description):** Zamiast ślepego LLM → wywołaj SAAS M2M endpoint
2. **Fallback:** Jeśli SAAS niedostępny → fallback na lokalne LLM (Claude prompt bez vision)
3. **Merge:** Połącz SAAS vision descriptions z kontekstem artykułu z LLM
4. **Upload do WP:** Użyj 4 pól z SAAS (`alt_text`, `seo_title`, `caption`, `description`) przy `upload_media()` call

### Zmiany potrzebne w crimson-void (SAAS)

1. **Nowy endpoint:** `POST /api/external/describe-image` w `external.py`
2. **Auth:** `EXTERNAL_API_TOKEN` (już istnieje, wartość: w `.env.production`)
3. **Logika:** Wyciągnąć prompt z `_generate_vision_seo()` do shared helper, użyć w obu endpointach
4. **Stateless:** Endpoint NIE zapisuje do DB — tylko generuje i zwraca

## 5. Alternatywy rozważone

### Opcja A: SAAS-first (tylko SAAS)
- ✅ Vision-based, SEO-aware
- ❌ Wymaga dependency na SAAS (single point of failure)
- ❌ Brak kontekstu artykułu (transkrypt, chapters) — SAAS nie wie co jest w artykule

### Opcja B: LLM-only (bez SAAS)
- ✅ Zero dependency zewnętrznych
- ❌ NIE widzi obrazka — opisy generyczne ("miniaturka wideo YouTube")
- ❌ Gorsze SEO descriptions

### Opcja C: Hybrid (REKOMENDOWANA)
- ✅ Vision-based (SAAS) + kontekst artykułu (LLM)
- ✅ Fallback na LLM jeśli SAAS padnie
- ✅ Najlepsze opisy: precyzyjne wizualnie + kontekstowe tematycznie
- ⚠️ Wymaga nowego M2M endpoint w crimson-void

## 6. Dodatkowe odkrycia

### 6.1 Image processing pipeline w SAAS

SAAS ma pełen pipeline przetwarzania obrazków:
- Resize/crop do aspect ratio (16:9, 4:3, 1:1, etc.)
- Konwersja do WebP (quality=85)
- Color profile (neutral, warm, cool, professional-dark, warm-lifestyle)
- SEO-friendly filename slugification

To może być przydatne dla D11 — zamiast uploadować surowy YouTube thumbnail do WP, przepuścić go przez SAAS image processing → lepszej jakości obraz.

### 6.2 ImageObject JSON-LD builder

SAAS ma endpoint `POST /api/images/rebuild-schema/{article_id}` który generuje `ImageObject` JSON-LD z DB. To jest dokładnie ten sam schema który D11 ma generować — można uniknąć duplikacji.

### 6.3 WP upload z opisami

SAAS `wp_client.py` → `upload_media()` już przyjmuje:
- `alt_text`, `caption`, `title`, `description`
- Uploaduje do WP Media Library i ustawia te pola

VSE `injector.py` powinien użyć tego samego wzorca.

---

*[vse-analyst-07 | video-seo-engine 21.06.2026 00:56] — raport A7 kompletny*