# DISPATCH — VSE-ANALYST-01 | 2026-05-19

**Od:** vse-dev-01 (Worker)
**Do:** vse-analyst-01
**Priorytet:** 🔴 WYSOKI — blokuje pipeline scheduled videos
**Workspace:** `/home/tobroz/projects/video-seo-engine`

---

## Problem do zbadania

**Teza Workera (wymaga weryfikacji):**  
YouTube Data API v3 nie zwraca prywatnych/scheduled filmów w `playlistItems` nawet po autoryzacji OAuth. Supervisor podważa tę tezę i uważa, że OAuth powinien dawać pełny dostęp do zarządzania kontem.

**Pytania do odpowiedzi:**

1. Jakie **scopy OAuth** są wymagane do listowania prywatnych/scheduled filmów przez API?
2. Czy `playlistItems.list` z OAuth zwraca prywatne filmy — czy jest to ograniczenie API?
3. Jaki jest poprawny endpoint/parametr do **listowania scheduled premieres** na kanale przez OAuth?
4. Czy można przez API **zarządzać czasem publikacji** (scheduledStartTime) zaplanowanej premiery?
5. Jak sprawdzić jakie scopy ma aktualny refresh token w `.env`?

---

## Dane środowiskowe

```
CHANNEL_ID=UCoH2G9By4OX3kcLsc8lHgDw   (Studio Prawy_PL)
YT_CLIENT_ID=779032474349-612itvmd9jusj8n3vu8q119e0ap7h4u3.apps.googleusercontent.com
# YT_REFRESH_TOKEN — jest w .env
```

**Weryfikacja działania OAuth (udowodnione):**
- `videos.update` dla `hN0Lp8B0L70` → HTTP 200 ✅ (update opisu działa)
- `channels.list?mine=true` → zwraca konto osobiste `UUIBzmtDQ1SrE0r7jtWbiTNw` (nie kanał Prawy)
- `playlistItems.list?playlistId=UUoH2G9By4OX3kcLsc8lHgDw` (OAuth) → 15 filmów, tylko publiczne

**Obserwacja:** OAuth zarządza Prawy TV jako brand account, ale `mine=true` wskazuje na konto osobiste. Scheduled filmy nie pojawiają się w playlistItems.

---

## Kontekst operacyjny

4 zaplanowane premiery Prawy TV (ze screenshota YT Studio):

| Tytuł (skrócony) | Data premiery | Status YT |
|---|---|---|
| IDEALNA KANDYDATKA NA ŻONĘ (Stopińska, Halwa) | 2026-05-19 | Scheduled |
| TUSK CHCE BYĆ LEPSZY OD HITLERA (Jakubiak, Płużański) | 2026-05-20 | Scheduled |
| TUSK UKRADŁ POLSKIM DZIECIOM SERDUSZKA | 2026-05-21 | Scheduled |
| 10 MLN POLAKÓW — OFIARY II WOJNY (Jakubiak, Płużański) | 2026-05-22 | Scheduled |

Pipeline potrzebuje YT ID każdego z tych filmów (są prywatne przed premierą) żeby:
- Stworzyć WP post z datą = czas premiery + 5 min
- Pobrać VTT (gdy dostępne)
- Zaktualizować opis YT z rozdziałami

---

## Oczekiwany deliverable

Raport decyzyjny zawierający:
1. Poprawne scopy OAuth dla pełnego dostępu do prywatnych filmów
2. Czy obecny token je ma — jak sprawdzić (endpoint tokeninfo)
3. Endpoint + przykład zapytania zwracający scheduled/private filmy
4. Czy i jak przez API ustawić `scheduledStartTime` (czas premiery)
5. Rekomendację: naprawić token scope vs. inne podejście

**Format:** `.agents/reports/2026-05-19_vse-analyst-01_yt-oauth-scopes.md`

*dispatch | vse-dev-01 | 2026-05-19T13:32Z*
