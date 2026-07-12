# Raport: vse-diag2 — diagnoza legacy YT
**Model:** Gemini Pro | **Typ:** DIAGNOSTYKA
**Data:** 2026-07-12
**Commit testowany:** d6735e0

## Odpowiedzi na pytania diagnostyczne

### 1. Czy commit d6735e0 jest na VPS?
**TAK.** Log git log --oneline -5 z VPS:
\\\
d6735e0 fix: disable legacy YT update when yt_channel_ids present (Scenario A) [vse-fix]
0c9c0ce heartbeat: [vse-research] status=done
8b79336 report: [vse-research] przepływ schema_data
\\\
Wdrożenie było poprawne.

### 2. Co pokazują logi?
Z logów docker logs vse-api wynika kluczowa kwestia: **/v1/inject NIE JEST w ogóle wywoływany, gdy użytkownik klika "Wyślij na YouTube".**
\\\
2026-07-12 18:22:04,168 [INFO] api.services.pipeline: [pipeline] PressAI YT description received for dZL_p2VrPa0
INFO:     172.27.0.1:42088 - "POST /v1/youtube/publish-description HTTP/1.0" 200 OK
\\\
Zamiast pełnego wstrzykiwania do WP (które idzie przez 
un_inject i ma nasz guard), "Wyślij na YouTube" z UI (modala YouTubePublishModal) uderza prosto na /v1/youtube/publish-description. Endpoint ten nie używa starego inject_video ani nowego 
un_inject. Działa w izolacji i wrzuca dokładnie ten string, który poda mu frontend.

### 3. Jak wygląda guard na VPS w pipeline.py?
Guard dodany w d6735e0 został sprawdzony w kodzie (i działa dla opcji "Opublikuj i Wstrzyknij" / POST /v1/inject):
\\\python
    # FIX: Scenariusz A obsługuje YT — wyłącz legacy
    if yt_channel_ids and profile_config:
        if profile_config.get("yt_update_enabled"):
            logger.info("[inject] yt_channel_ids present -> disabling legacy yt_update_enabled")
            profile_config["yt_update_enabled"] = False
\\\

### 4. Czy dashboard wysyła payload z poprawnym opisem?
Znalazłem **przyczynę źródłową błędu** (tzw. root cause). Bug leży w komponencie UI dashboard-inner.tsx (okolice linii 3657), który składa opis dla POST /v1/youtube/publish-description:

\\\	ypescript
const hook = result.raw?.youtube_description_hook || result.raw?.youtube_description || "";
// ... pomija result.raw?.seo?.youtube_description_body całkowicie!
const ytDescription = [
    hook,
    wpUrl ? \\n\n🚀 Pełny artykuł: \\ : "",
    chaptersStr ? \\n\n⏱️ Rozdziały:\n\\ : "",
    hashtags ? \\n\n---\n\\ : "",
].join("");
\\\
Frontend kompletnie ignoruje nowe pole youtube_description_body generowane przez PressAI w seo obiekcie, budując zamiast tego kadłubowy opis na bazie starych, prawdopodobnie pustych pól (jak youtube_description_hook).
