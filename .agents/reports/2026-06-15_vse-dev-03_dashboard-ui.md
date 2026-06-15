# Raport — Dashboard UI (2 ścieżki)
**Agent:** vse-dev-03  
**Data:** 2026-06-15  
**Status:** ✅ done

---

## Zakres prac

Przebudowa `web/src/app/dashboard/page.tsx` z widoku z jednym tabą JSON na pełne 2-ścieżki UX.

---

## Ścieżka A — Sekcja wyników (Free + Pro + Agency)

Wszystkie 5 pól z `schema_data` wyeksponowane jako osobne sekcje z przyciskiem **Kopiuj** per sekcja:

| Sekcja | Pole `schema_data` | Format kopii |
|---|---|---|
| Tytuł artykułu | `post_title` | plain text |
| Meta description | `meta_description` | plain text |
| Schema JSON-LD | całość | `<script type="application/ld+json">...</script>` |
| Rozdziały | `chapters` (Clip @graph) | `MM:SS — Tytuł` per linia |
| FAQ | `faq` (FAQPage @graph) | HTML `<details><summary>` |

**Przycisk Kopiuj:** feedback 2s ("✓ Skopiowano"), `navigator.clipboard.writeText`.

---

## Ścieżka B — Sekcja publikacji (Pro/Agency only)

- Widoczna warunkowo: `session.user.plan ∈ ['pro', 'agency']`
- Plan pobierany z `GET /api/v1/users/me` (Bearer token)
- Formularz: WP URL, Użytkownik, App Password, ID Posta, status Draft/Publish
- Wywołuje `POST /api/v1/inject` z pełnym `schema_data` + `site_config`
- **UWAGA:** `InjectRequest` wymaga `wp_post_id` (int) — pole obowiązkowe wg OpenAPI
- Dla free: upsell bar ("Ulepsz plan →")

---

## Dodatkowe ulepszenia UX

- Usage bar w sidebarze (użyte/quota z profilu)
- Plan label w sidebarze (dynamiczny z API)
- Komunikat o czasie generowania (~50s)
- Null-safe extraktory (chapters/faq/title/meta)
- Koćcarz CO/PO CO/JAK na wszystkich komponentach

---

## Commity

- `9e479fb` — feat(dashboard): 5-section results UI + PublishSection (pro/agency) [vse-dev-03]

---

## Deploy

- VPS: SSH + `docker compose build vse-web && up -d` — bez FILE BRIDGE
- Build: ✅ OK (39.7s)
- Kontener: ✅ Next.js Ready in 74ms
- CSRF check: ✅ csrfToken zwracany
- Dashboard /dashboard: ✅ HTTP 307 (redirect do /login — poprawne)

---

## Blokery / niezakontraktowane

- **wp_post_id wymagany** w InjectRequest — użytkownik musi znać ID posta WP.
  Rekomendacja Faza 3: wyszukiwarka postów WP po tytule lub slugu.
- **Credentials formularza** — MVP: wpisywane ręcznie. Faza 3: profil z zapisanymi portalami.
- **accessToken w NextAuth session** — musi być poprawnie przekazywany z JWT do NextAuth session.
  Jeśli `session.accessToken` jest `undefined`, fetch profilu fallbackuje do planu "Free".

---

*Raport: vse-dev-03 | 2026-06-15 | video-seo-engine*
