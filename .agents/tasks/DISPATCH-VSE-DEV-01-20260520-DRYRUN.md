# DISPATCH: Title Sync — Dry Run + linki do weryfikacji
**Od:** Supervisor 01 (sonic-void)
**Do:** vse-dev-01 (video-seo-engine)
**Data:** 2026-05-20
**Priorytet:** 🟡 Medium — weryfikacja przed prod

---

## ⚡ KROK 0 — przedstawienie na starcie

```
[vse-dev-01 | video-seo-engine 2026-05-20 HH:MM] 📊 V1:0/40 🟢 V2:1str 🟢 V3:1pl 🟢 V4:stabilny V5:ok — online
```

Kontekst: Implementowałeś Title Sync w poprzedniej sesji (commit `16f9639`, 31/31 testów ✅).

---

## Cel

Uruchom dry run na 5 filmach z `next_batch_matches.json` i dostarcz Supervisorowi:
1. Tabelę: obecny tytuł YT → proponowany `yt_title`
2. Tabelę: obecny WP post title → proponowany `post_title`  
3. Bezpośrednie linki do weryfikacji (YouTube + prawy.pl)

---

## Kontekst techniczny

### Stan danych:
- `seo_results/` — **41 JSONów**, wszystkie w STARYM formacie (brak `post_title`, `yt_title`)
- `next_batch_matches.json` — **5 filmów** w strukturze: `{youtube_id, wp_id, post_title}`
- `registry/` — 5 starszych wpisów (status: injected), bez nowych pól tytułów

### Problem:
Żaden istniejący SEO JSON nie ma `post_title` / `yt_title` — były generowane przed Title Sync.
Dry run musi **re-generować** SEO dla 5 filmów z nowym promptem (lub zbudować mock).

---

## Zadania

### TASK-1: Re-generowanie SEO dla 5 filmów (nowy prompt)

Filmy z `next_batch_matches.json`:
```json
[
  {"youtube_id": "fukGxq5aGOo", "wp_id": 119062},
  {"youtube_id": "...", "wp_id": 119067},
  {"youtube_id": "...", "wp_id": 118966},
  {"youtube_id": "...", "wp_id": 118994},
  {"youtube_id": "...", "wp_id": 118818}
]
```

Dla każdego z 5 filmów — sprawdź czy mamy VTT/subs:
```bash
ls ~/projects/video-seo-engine/subs/ | head -20
```

Jeśli VTT istnieje → `vse generate --video <YT_ID>` (nowy prompt z post_title+yt_title).
Jeśli brak VTT → sprawdź `seo_results/` pod danym `youtube_id`.

### TASK-2: Dry Run inject

Dla każdego z 5 wygenerowanych SEO JSONów uruchom dry run:
```bash
cd ~/projects/video-seo-engine
source .env  # lub załaduj env

# Sprawdź czy jest komenda dry-run w CLI:
python -m cli.main inject --video <YT_ID> --wp-id <WP_ID> --dry-run

# Lub bezpośrednio przez Python:
python3 -c "
from core.injector import inject_video
result = inject_video('<YT_ID>', <WP_ID>, dry_run=True)
print(result)
"
```

Jeśli `inject` nie obsługuje `--dry-run` w CLI → dodaj obsługę lub użyj Python direct call.

### TASK-3: Zebranie linków

Dla każdego z 5 filmów pobierz:
```python
from core.yt_admin import get_video_data
data = get_video_data('<YT_ID>')
current_yt_title = data['snippet']['title']
```

Obecne URL WP: `https://prawy.pl/?p=<WP_ID>`

### TASK-4: Tabela wynikowa

Przygotuj tabelę dla Supervisora:

```markdown
| YT_ID | Obecny tytuł YT | Proponowany yt_title | Obecny WP title | Proponowany post_title | Link YT | Link WP |
|-------|----------------|---------------------|-----------------|----------------------|---------|---------|
| fukGxq5aGOo | ... | ... | ... | ... | https://youtu.be/fukGxq5aGOo | https://prawy.pl/?p=119062 |
...
```

---

## Raport

```
Lokalnie:
~/projects/video-seo-engine/.agents/reports/2026-05-20_vse-dev-01_dryrun-title-sync.md

GitHub MCP (sonic-void):
  owner: gitomwtyczka / repo: sonic-void / branch: master
  path: .agents/reports/inbox/2026-05-20_vse-dev-01_dryrun-title-sync.md
```

**Raport zawiera tylko dry run — NIE injektuj bez zatwierdzenia Supervisora.**

---

> Zamknij raport linią callsign:
> `[vse-dev-01 | video-seo-engine YYYY-MM-DD HH:MM] V1:N/40 V2:Nstr V3:Npl V4:stabilny V5:ok — dry run wysłany`

---

*[Supervisor 01 | sonic-void | 2026-05-20]*
