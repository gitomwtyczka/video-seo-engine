# PROMPT STARTOWY — VSE Następna Sesja
## Plik: `.agents/reports/BOOTSTRAP-NEXT-SESSION.md`

---

## COPY-PASTE PROMPT (wklej na starcie nowej sesji)

```
# [vse-dev-01 | video-seo-engine | HANDOFF 2026-05-20] ONLINE

Działam jako **vse-dev-01** — Worker implementacyjny dla projektu **PressAI Video SEO Engine**.

## Kontekst z poprzedniej sesji (2026-05-20)

### Co zostało zrobione:
- Przetworzono 39 filmów (Batch 1-3 + hotfix), pełny pipeline VTT→Gemini→WP→RankMath→YT
- Zrefaktorowano architekturę na **multi-tenant**:
  - `core/profile.py` — YAML portal profiles (backward compat env fallback)
  - `profiles/prawy.yaml` — profil Prawy.pl w użyciu
  - `core/injector.py` — odcięto hardcoded `prawySeek`/`prawy-chapter` → `_build_player_js()`
  - `cli/main.py` — `--profile <name>` we wszystkich komendach
  - `Dockerfile` + `docker-compose.vse.yml` — VPS deployment ready
- Commit: `6e793c4` (HEAD, main)
- **Niepushowane**: 3 commity lokalne vs `origin/main`

### Co do zrobienia (priorytet malejący):

1. **git push origin main** — najpierw!

2. **VPS Deploy (oracle-crimson 147.224.162.100)**:
   ```bash
   # Na WSL2 Jagodziak4:
   git push origin main
   
   # Eksport cookies Firefox:
   cd /home/tobroz/projects/video-seo-engine
   python3 -m yt_dlp --cookies-from-browser firefox --cookies cookies/prawy_cookies.txt "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --skip-download 2>&1 | head -5
   
   # Na oracle-crimson (SSH):
   ssh oracle-crimson
   cd /opt/vse && git pull origin main
   cp ~/.impresja/secrets/vse.env .env.production
   # (+ skopiuj cookies/prawy_cookies.txt)
   docker compose -f docker-compose.vse.yml up -d --build
   docker logs -f vse-watch
   ```

3. **Backlog ~144 filmów** — wygeneruj nowy batch z matches JSON:
   ```bash
   python3 -m cli.main generate --batch <nowe_matches.json> --profile prawy
   python3 -m cli.main inject --batch data/prawy/seo_results/ --profile prawy
   ```

4. **Nowy portal** (gdy gotowy):
   ```bash
   cp profiles/template.yaml profiles/<nowy_portal_id>.yaml
   # Uzupełnij pola, dodaj .env z kredencjalami
   python3 -m cli.main watch --profile <nowy_portal_id>
   ```

### Ścieżki kluczowe:
- Workspace: `/home/tobroz/projects/video-seo-engine`
- Sekrety: `~/.impresja/secrets/vse.env` (WSL2 Jagodziak4)
- Raport poprzednika: `.agents/reports/2026-05-20_vse-dev-01_handoff-vps-multitenant.md`
- Profil prawy: `profiles/prawy.yaml`
- Docker: `docker-compose.vse.yml`

### Architektura komend:
```bash
vse generate --batch batch.json --profile prawy   # generuj schema JSON
vse inject --batch data/prawy/seo_results/ --profile prawy  # wstrzyknij do WP
vse watch --profile prawy --interval 1800          # daemon VPS
vse update-yt --all-registry --registry-dir data/prawy/registry/  # YT opisy
```

### Znane problemy:
- cookies.txt wygasają ~30 dni — monitoruj logi yt-dlp
- Backup: `youtube-transcript-api` jako fallback (filmy publiczne)

## Zaczynamy od:
Potwierdź stan git + zrób `git push`. Następnie wykonaj VPS deploy zgodnie z checklistą.
```

---

## KRÓTKI KONTEKST TECHNICZNY (dla przypomnienia)

### Stos:
- **Python 3.11** + pyyaml + requests + google-generativeai
- **youtube-transcript-api 1.2.4+** — VTT bez klucza API
- **yt-dlp** — fallback + cookies
- **Gemini 2.5 Flash** — AI generation chapters/FAQ/schema
- **WordPress REST API v2** + RankMath `rankmath/v1/updateMeta`
- **YouTube OAuth 2.0** — opis + rozdziały na kanale
- **Docker** — deployment oracle-crimson

### Schema SEO (v5.3):
- `VideoObject` (OBOWIĄZKOWO: duration ISO 8601, uploadDate+TZ, thumbnailUrl maxresdefault)
- `Clip` z `startOffset/endOffset` + `SeekToAction`
- `FAQPage` z transkryptu
- NIE: Quotation (bez wpływu), BroadcastEvent (inny pipeline)

### Prawy.pl specyfika:
- CSS class: `prawy-chapter` → `data-time` → `prawySeek(t)`
- WP REST: Application Password, status: `publish`
- RankMath: POST `rankmath/v1/updateMeta` (nie `meta` field w PATCH)
- Thumbnail: `maxresdefault.jpg` z i.ytimg.com

---

*Wygenerowano: 2026-05-20 | vse-dev-01 | sesja 32dc395c*
