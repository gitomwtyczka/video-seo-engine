# DISPATCH A — vse-analyst | Diagnostyka: stopka nie trafia do opisu YT

**Data:** 2026-07-13  
**Od:** Supervisor 01  
**Do:** vse-analyst (read-only, zero zmian w kodzie)  
**Priorytet:** BLOKUJĄCY

---

## ⚡ KROK 0

```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: sonic-void
  branch: master
  path: .agents/protocols/dispatch-system-block.md
```
Heartbeat do `video-seo-engine/.agents/heartbeat.json`.

---

## 🔍 ZADANIE — tylko czytanie, zero zmian

Użytkownik zapisał stopkę kanału w Ustawieniach. Stopka:
1. Nie pojawia się w podglądzie opisu YT
2. Nie trafiła na YouTube
3. Po odświeżeniu strony pole stopki jest puste (placeholder widoczny)

Odpowiedz na 4 pytania diagnostyczne.

---

## Pytanie 1: Czy GET /v1/youtube/channels zwraca footer_text?

Sprawdź w `api/routers/youtube.py`:
- Znajdź endpoint `GET /v1/youtube/channels` (lub podobny)
- Sprawdź Pydantic model odpowiedzi — czy zawiera pole `footer_text`?
- Jeśli model odpowiedzi to np. `ChannelResponse` — znajdź jego definicję

**Oczekiwana odpowiedź:** TAK/NIE + nazwa modelu + linia kodu

---

## Pytanie 2: Czy PUT /v1/youtube/channels/{id} faktycznie zapisuje footer_text do DB?

Sprawdź w `api/routers/youtube.py`:
- Znajdź endpoint `PUT /v1/youtube/channels/{channel_id}`
- Sprawdź czy `footer_text` jest w modelu requestu (Pydantic)
- Sprawdź czy jest zapisywany do bazy (UPDATE query lub ORM)

**Oczekiwana odpowiedź:** TAK/NIE + czy pole jest w request modelu + czy jest w UPDATE

---

## Pytanie 3: Czy frontend FooterTextEditor używa właściwej nazwy pola?

Sprawdź w `web/src/app/ustawienia/page.tsx`:
- Jak `FooterTextEditor` inicjalizuje wartość: `channel.footer_text` czy inna nazwa?
- Czy przy mount komponenty ustawia `defaultValue` czy `value`?
- Jaki endpoint i payload wysyła przy zapisie?

**Oczekiwana odpowiedź:** nazwa pola, typ kontrolki (controlled/uncontrolled), payload

---

## Pytanie 4: Jak build_yt_description() dostaje footer_text?

Sprawdź w `api/routers/inject.py`:
- Jak `build_yt_description()` otrzymuje `footer_text` — z request body, z DB, czy z channel obiektu?
- Czy w momencie budowania opisu jest dostęp do danych kanału (w tym footer_text)?
- Jeśli nie — skąd powinno być pobrane?

**Oczekiwana odpowiedź:** źródło danych + czy jest gap

---

## 📨 FORMAT RAPORTU

```
video-seo-engine/.agents/reports/2026-07-13_vse-analyst_footer-diag.md
sonic-void/.agents/reports/inbox/2026-07-13_vse-analyst_footer-diag.md
```

```markdown
# Diagnostyka: footer_text

## Q1: GET zwraca footer_text?
[TAK/NIE + model + linia]

## Q2: PUT zapisuje footer_text do DB?
[TAK/NIE + szczegóły]

## Q3: Frontend — poprawna nazwa pola?
[pole, controlled/uncontrolled, payload]

## Q4: build_yt_description — skąd footer_text?
[źródło + gap jeśli jest]

## Root cause (hipoteza)
[Co jest główną przyczyną buga]

## Minimalne zmiany do naprawy
[Lista plików i co konkretnie zmienić]
```

---

*Supervisor 01 | sonic-void | 2026-07-13*
