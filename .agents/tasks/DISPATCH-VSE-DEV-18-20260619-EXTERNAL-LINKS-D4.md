# DISPATCH-VSE-DEV-18-20260619-EXTERNAL-LINKS-D4

**Data:** 2026-06-19  
**Supervisor:** Supervisor 01  
**Agent:** `vse-dev-18`  
**Projekt:** video-seo-engine | branch: main  
**Priorytet:** MEDIUM

---

## Cel

RankMath wymaga co najmniej jednego linku zewnętrznego w artykule, żeby dać zielony wynik SEO. Aktualnie artykuły VSE nie zawierają linków zewnętrznych — RankMath obniża scoring SEO za każdy post.

---

## Zadanie D4 — Linki zewnętrzne w artykule

### Kontekst

- Plik: `core/injector.py` → `build_post_content()`
- Artykuł generowany przez LLM (`article_body`) może (ale nie musi) zawierać linki zewnętrzne
- RankMath sprawdza obecność linku zewnętrznego w `post_content`

### Implementacja

**Opcja A (prosta, rekomendowana):** Po zakończeniu `article_body` — wstrzyknij jeden stały link zewnętrzny per profil jako inline `<p>` lub `<a>` w treści.

**Opcja B (lepsza jakość):** Generator LLM zwraca `external_links: []` — lista URL z kontekstem. Injector wstrzykuje je jako linki w `article_body`.

**Rekomendacja Supervisora:** Zacznij od Opcji A (1-2h), Opcja B jako follow-up jeśli czas pozwoli.

### Specyfikacja Opcji A

1. W `profiles/prawy.yaml` i `profiles/kurier365.yaml` dodaj pole:
   ```yaml
   seo_external_link:
     url: "https://example.com/artykul-powiazany"
     anchor: "Powiązane informacje"
   ```
2. W `build_post_content()` — wstaw `<p><a href="{url}" target="_blank" rel="noopener noreferrer">{anchor}</a></p>` po `article_body`, przed FAQ.
3. Jeśli `seo_external_link` nie zdefiniowany w profilu — pomiń (graceful skip).

### Pliki do modyfikacji

- `core/injector.py` — `build_post_content()` + helper
- `profiles/prawy.yaml` — nowe pole
- `profiles/kurier365.yaml` — nowe pole

---

## Weryfikacja

- `seo_external_link` obecny w YAML i parsowany
- Link pojawia się w `post_content` w odpowiednim miejscu
- `target="_blank" rel="noopener noreferrer"` — wymagane
- Graceful skip gdy pole nieobecne w profilu

---

## Raportowanie

Po zakończeniu:
1. Raport do `video-seo-engine/.agents/reports/2026-06-19_vse-dev-18_external-links-d4.md`
2. Kopia do `sonic-void/.agents/reports/inbox/2026-06-19_vse-dev-18_external-links-d4.md`
3. Heartbeat `status: done`

---

*Supervisor 01 | video-seo-engine | 2026-06-19*
