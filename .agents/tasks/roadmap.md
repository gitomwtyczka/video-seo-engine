# Video SEO Engine — ShortMachine Roadmap

Aktualizacja: 2026-08-19 [vse-strateg-01]

---

## 🔴 Bieżączka (aktywne sprint)

| # | Feature | Status | Sesja |
|---|---|---|---|
| 1 | SRT sliding window fix (deduplikacja tekstu) | ✅ Done | 2026-08-19 commit `eaf50aa` |
| 2 | SRT dynamic word chunks + timestamp overlap fix | 🟡 W toku | 2026-08-19 |
| 3 | Audio fingerprinting — library_matcher.py (próbki ze środka, cookies, voting 2/3) | 🔵 Backlog | handoff 2026-08-19 |

---

## 🟡 Następny sprint

### Shorts Metadata: Tytuł + Opis + Stopka kanału

**Co:** Po wygenerowaniu kandydatów ShortMachine, AI automatycznie generuje:
- Tytuł shorta (max 70 znaków, chwytliwy, po polsku)
- Opis (2-3 zdania z treści)
- Hashtagi (3-5 tematycznych)
- Stopka kanału dołączana dynamicznie z ustawień `youtube_channels.footer_text`

**Po co:** Operator zamiast pisać opis od zera dostaje AI-draft do korekty.
Kopiuje tytul + opis + stopka jednym kliknięciem.

**Jak:**
- `core/shorts.py` — dodać pola `title`, `description`, `hashtags` do `ShortCandidate` + rozszerzyć prompt LLM
- `api/routers/shorts.py` — mapowanie nowych pól (bez migracji DB — JSONB elastyczny)
- `dashboard-inner.tsx` — UI: edytowalne pola + CopyButton + live stopka z wybranego kanału
- `footer_text` już istnieje w tabeli `youtube_channels`

**Faza 2 (po):** Pole 'wklej link YouTube Shorts' → jeśli OAuth → update tytułu/opisu przez YouTube Data API v3.

**Plan:** `.agents/tasks/2026-08-19_shorts-metadata-plan.md` (szczegółowy)

---

## 🔵 Backlog

- Browse button pełna ścieżka (priorytet niski — browser security blocker)
- runner.py source priority fix (`local` przed `youtube` gdy local_path obecne)
- YouTube Shorts publish: pola tytułu/opisu → update via API
