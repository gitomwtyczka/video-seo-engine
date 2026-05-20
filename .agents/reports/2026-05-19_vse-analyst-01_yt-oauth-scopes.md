# Raport: YouTube OAuth — Dostęp do Scheduled/Private Videos

> **Agent:** vse-analyst-01 | video-seo-engine | 2026-05-19
> **Dispatch:** DISPATCH-VSE-ANALYST-01-20260519-YT-OAUTH
> **Źródła:** YouTube Data API v3 docs, Google OAuth tokeninfo, live API tests

---

## 1. Kontekst / stan obecny

Worker (vse-dev-01) nie mógł pobrać listy 4 zaplanowanych filmów Prawy TV przez OAuth.
Teza: "API nie zwraca prywatnych scheduled w `playlistItems`".
Supervisor podważa — słusznie.

---

## 2. Analiza / wyniki

### 2.1 Root Cause — Token ma właściwy scope, ale KONTO jest złe

**Sprawdzony scope tokenu:**
```
scope: https://www.googleapis.com/auth/youtube.force-ssl
```

`youtube.force-ssl` = **pełny dostęp**, identyczny jak `youtube` scope — różni się tylko wymuszeniem SSL. Scope NIE jest problemem.

### 2.2 Właściwy Problem — `mine=true` wskazuje osobiste konto

```
channels?mine=true → UUIBzmtDQ1SrE0r7jtWbiTNw  (konto osobiste)
CHANNEL_ID docelowy → UCoH2G9By4OX3kcLsc8lHgDw  (Studio Prawy_PL)
```

OAuth token należy do konta osobistego, które ZARZĄDZA brand account Prawy TV.
Gdy `playlistItems.list` prosi o `UUoH2G9By4OX3kcLsc8lHgDw` — YouTube zwraca tylko publiczne filmy, bo **ten playlist ID jest publiczny i nie wymaga auth** → odpowiedź jest identyczna jak dla API key.

### 2.3 Weryfikacja API — co działa, co nie

| Test | Wynik | Przyczyna |
|------|-------|-----------|
| `videos.update` dla Prawy TV | ✅ HTTP 200 | Konto osobiste ma write-access do brand account |
| `playlistItems.list?playlistId=UUoH2G9By4OX3kcLsc8lHgDw` | ❌ Tylko publiczne | Odpowiada jak public endpoint |
| `channels?mine=true` | ✅ Działa — ale zwraca konto osobiste | Poprawne zachowanie |
| `channels?id=UCoH2G9By4OX3kcLsc8lHgDw` | ✅ Zwraca uploads playlist | Ale playlist jest publiczna |

### 2.4 Jak uzyskać scheduled/private z brand account przez OAuth

**Poprawna metoda (z dokumentacji YT API):**

Aby uzyskać prywatne/scheduled filmy brand account przez konto managera:

```python
# Krok 1 — Pobierz uploads playlist BRAND ACCOUNT (nie mine=true)
channels.list(
    part='contentDetails',
    id='UCoH2G9By4OX3kcLsc8lHgDw',  # brand account ID
    # headers: Authorization: Bearer <token>   ← kluczowe
)
# → uploadPlaylistId = UUoH2G9By4OX3kcLsc8lHgDw

# Krok 2 — Listuj items (z OAuth)
playlistItems.list(
    part='snippet,contentDetails',
    playlistId='UUoH2G9By4OX3kcLsc8lHgDw',
    maxResults=50,
    # headers: Authorization: Bearer <token>
)
# → powinno zwrócić private + scheduled (jeśli token ma dostęp do brand account)
```

**Problem:** Konto osobiste (manager) ma write access (dowiodła aktualizacja opisu), ale YT API nie traktuje go jako właściciela playlist brand account. `playlistItems.list` na playlist brand account + OAuth managera = public response.

### 2.5 Poprawne rozwiązanie

**Potrzebny jest refresh token KONTA BRAND ACCOUNT** (właściciela kanału Prawy TV), NIE konta managera.

Alternatywnie — YouTube Studio API (beta, wymaga whitelist) lub YouTube Reporting API.

**Zarządzanie scheduledStartTime przez API:** TAK, jest możliwe przez:
```
videos.update(part=status, body={status: {publishAt: "2026-05-20T18:00:00Z"}})
```

---

## 3. Rekomendacja

### ✅ Krótkoterminowe (odblokowanie natychmiastowe)

**Opcja A — Nowy refresh token jako właściciel kanału:**
Właściciel konta Prawy TV musi przejść przez flow OAuth i wygenerować refresh token. Wymaga fizycznego logowania przez przeglądarkę.

**Opcja B — YT Studio URL jako źródło IDs (0 dev cost):**
Ze screenshota w YT Studio URL każdego scheduled filma zawiera `videoId`. Użytkownik przekazuje 4 IDs → pipeline działa natychmiast.

**Opcja C — Poczekaj na publikację (automatycznie):**
Pierwsza premiera (19.05, dziś ~20:00 CET) będzie publiczna za ~2-4h. Po publikacji `playlistItems` zwróci ID → `vse watch` złapie automatycznie.

### 🔄 Długoterminowe (architektura)

Dodać do `oauth_setup.py` flow generowania tokenu bezpośrednio dla brand account (on behalf of channel owner). Documented scope: `youtube` lub `youtube.force-ssl` + `onBehalfOfContentOwner`.

---

## 4. Ryzyka

| Ryzyko | Poziom | Mitygacja |
|--------|--------|-----------|
| Brak tokenu dla brand account | 🟡 Średni | Opcja B lub C jako fallback |
| `scheduledStartTime` zmiana przez API | 🟢 Niski | API to wspiera, gdy mamy właściwy token |
| Premiere features ograniczone w API | 🟡 Średni | Opis + VTT dostępne post-publication |

---

## 5. Następne kroki (po akceptacji Supervisora)

1. **Decyzja:** Opcja A, B czy C?
2. **Jeśli A** → Worker uruchamia `oauth_setup.py` dla właściciela kanału (wymaga logowania przez przeglądarkę)
3. **Jeśli B** → Supervisor podaje 4 YT IDs ze Studio → Worker puszcza pipeline dla każdego
4. **Jeśli C** → Worker uruchamia `vse watch` który złapie premiery automatycznie dziś i w kolejnych dniach

---

*vse-analyst-01 | video-seo-engine | 2026-05-19T13:45Z — raport kompletny*
