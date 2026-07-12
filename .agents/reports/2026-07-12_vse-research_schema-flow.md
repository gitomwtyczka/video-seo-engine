# Raport: Przepływ schema_data (generate -> inject)
**Model:** Gemini Pro | **Typ:** RESEARCH
**Data:** 2026-07-12

## 1. Czy youtube_description_body jest w zwracanym dict z run_generate?
**Tak.** Zmienna zostaje pomyślnie dopisana do słownika `seo` i wypchnięta w górę przez `run_generate`:
```python
        if pressai_yt:
            seo["youtube_description_body"] = pressai_yt.get("youtube_description_body", "")
            ...
            logger.info("[pipeline] PressAI YT fields merged into schema_data")
```
Słownik `seo` (z `youtube_description_body`) jest zawarty jako wynik `"seo"`, a następnie router `/v1/generate` przypisuje go do `GenerateResponse(schema_data=result["seo"])`. Nawet przy wymuszeniu `partial_result=True` (brak transkryptu), ta ścieżka wykonuje się poprawnie (co widać było z logów).

## 2. Czy InjectRequest.schema_data to `dict | Any` czy typed model?
To czysty **`dict`**. W `api/models/request.py`:
```python
class InjectRequest(BaseModel):
    ...
    schema_data: dict
```
Ponieważ to zwykły `dict`, Pydantic nie stripuje, nie filtruje ani nie gubi nieznanych pól. Pole z PressAI jest więc bezpiecznie utrzymywane.

## 3. Jak dashboard buduje payload do inject — 1:1 z generate response czy ręcznie?
**Przekazuje dane 1:1**.
Dashboard korzysta z interfejsu `SchemaData`, który dopuszcza nieznane klucze `[key: string]: unknown`. 
Z JSON-a odbiera to pole jako `schema_data` i podaje w czystej formie przez prop `schemaData` do `InjectModal`. 
Funkcja `POST /v1/inject` wywoływana z przeglądarki wrzuca te dane bez przeróbek:
```typescript
      const body: Record<string, unknown> = {
        video_url: videoUrl,
        schema_data: schemaData, // <-- przekazywane w relacji 1:1
        post_status: postStatus,
        ...
```

## 4. Hipoteza: Gdzie ginie youtube_description_body?
Ginie poprzez "stary mechanizm" wysyłki (tzw. legacy) na rzecz podwójnej ścieżki w `inject`.

Kiedy endpoint `/v1/inject` się uruchamia, najpierw wywołuje `run_inject(..., schema_data)`.
Funkcja `run_inject` wchodzi w głąb do `core.injector.inject_video`. 
Jeżeli dany profil ma opcję `yt_update_enabled=True`, pod koniec `inject_video` uruchamia się stary system wrzucania SEO na YouTube z wykorzystaniem funkcji `core.yt_admin.update_video_title_and_description()`. 

Metoda ta korzysta ze swojej wewnętrznej funkcji budującej opis `build_description() -> _build_intro_with_bullets(seo)`, która kompletnie ignoruje obecność zmiennej `youtube_description_body`. Buduje swój opis na bazie wyciągów (snippetów) z `article_body` (starszy algorytm). To powoduje wysłanie "starego fallbacku" na serwery Google.

Po powrocie z `run_inject()`, endpoint wykonuje NOWY kod (Scenariusz A Immediate Publish). Zauważa, że użtkownik zaznaczył `yt_channel_ids` i buduje własny `build_yt_description(...)`, z użyciem poprawnego `req.schema_data.get("youtube_description_body")` i robi strzał (prawdopodobnie w tym momencie dostaje błąd Quoty/nie działa bo wysypuje się OAuth na starym module i operacja kończy się błędem/nieudokumentowanym skipnięciem, zostawiając błędy wygenerowane pierwszym rzutem "starego fallbacku").

**Podsumowanie:** Pipeline tworzy poprawny payload, jednak API przez zduplikowaną architekturę najpierw bezmyślnie wysyła na YT starszy wygenerowany algorytm (który nie wie o polu z PressAI), tworząc widoczny efekt zastąpienia go "fallbackiem".