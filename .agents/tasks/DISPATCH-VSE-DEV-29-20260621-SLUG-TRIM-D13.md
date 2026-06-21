# DISPATCH — vse-dev-29 — Slug Trim (Twardy Limit 60 zn)

**Dispatch ID:** D13  
**Callsign:** vse-dev-29  
**Priorytet:** 🟡 ŚREDNI  
**Data:** 2026-06-21  
**Wystawiony przez:** Supervisor 02  

---

## KONTEKST

E2E test pokazał slug 81 znaków. Google preferuje <60.
Prompt mówi "max 60 zn" ale LLM ignoruje — brak twardego limitu w kodzie.

Dodatkowo: RankMath flaguje _"Fraza kluczowa nieznaleziona w adresie URL"_
bo stop-word `i` zostało usunięte z frazy "Tytus Romek i Atomek".
To prawdopodobnie false positive (Google rozumie kontekst),
ale warto zachować polskie spójniki (`i`, `w`, `z`, `na`) w slug
gdy są częścią frazy kluczowej.

## ZADANIE

### 1. Fix — Twardy Limit Slug

W `core/generator.py`, w `process_video()` (lub odpowiedniej funkcji),
po `json.loads()` odpowiedzi LLM, dodaj:

```python
slug = result.get("wp_slug", "")
if len(slug) > 60:
    # Trim to last full word within 60 chars
    slug = slug[:60].rsplit("-", 1)[0]
    result["wp_slug"] = slug
```

### 2. Fix — Stop-words w polskich frazach

Jeśli istnieje funkcja slugify/sanitize:
- Zachowaj polskie spójniki (`i`, `w`, `z`, `na`, `do`, `o`) w slug
  gdy są częścią frazy kluczowej
- LUB: nie usuwaj stop-words z slug — Google sam je pomija w matching

Jeśli WP sam robi slugify — upewnij się że VSE wysyła slug z tymi słowami.

### 3. Deploy + Weryfikacja

Po commit:
```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  'cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose up -d --build'
```

## OUTPUT

Raport + dual-write:
```
video-seo-engine/.agents/reports/2026-06-21_vse-dev-29_slug-trim-d13.md
sonic-void/.agents/reports/inbox/2026-06-21_vse-dev-29_slug-trim-d13.md
```

## CREDENTIALS

SSH: `~/.ssh/oracle-crimson.key`, user `ubuntu`, IP `147.224.162.100`
GitHub MCP: standardowy dostęp

---

*[Supervisor 02 | sonic-void 21.06.2026 17:44]*