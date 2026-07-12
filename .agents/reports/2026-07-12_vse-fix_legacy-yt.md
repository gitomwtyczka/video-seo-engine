# Raport: Fix legacy YT update w inject_video
**Model:** Gemini Pro | **Typ:** IMPLEMENTACJA
**Data:** 2026-07-12
**Commit:** d6735e082c6a0109f82511a4ba14d6dc9ac01bb2

## 1. Wybór opcji
Wybrałem **Opcję B (guard po stronie run_inject)**. 
Dlaczego: 
un_inject ładuje z bazy profil powiązany z danym portalem i przygotowuje zmienne do operacji. To miejsce w kodzie jako jedyne ma pełen kontekst o yt_channel_ids przekazanych w requeście (podczas gdy samo inject_video jest ogólną funkcją używaną z różnych miejsc i nie wie o request parameters API z nowego scenariusza). Wyłączenie flagi yt_update_enabled w załadowanym słowniku konfiguracji zapobiega wykonaniu starego scenariusza w inject_video, zapewniając płynne przejście do Scenariusza A w kodzie routera.

## 2. Fragment kodu
**Przed:**
`python
    async with AsyncSessionLocal() as db:
        # (...)
        if job and job.portal_id:
            try:
                uid = uuid.UUID(job.portal_id)
                portal = await db.get(WpPortal, uid)
                if portal and portal.profile_id:
                    profile_config = _load_profile_config(portal.profile_id)
            except ValueError:
                pass

    logger.info(
`

**Po:**
`python
    async with AsyncSessionLocal() as db:
        # (...)
        if job and job.portal_id:
            try:
                uid = uuid.UUID(job.portal_id)
                portal = await db.get(WpPortal, uid)
                if portal and portal.profile_id:
                    profile_config = _load_profile_config(portal.profile_id)
            except ValueError:
                pass

    # FIX: Scenariusz A obsługuje YT — wyłącz legacy
    if yt_channel_ids and profile_config:
        if profile_config.get("yt_update_enabled"):
            logger.info("[inject] yt_channel_ids present -> disabling legacy yt_update_enabled")
            profile_config["yt_update_enabled"] = False

    logger.info(
`

## 3. Deploy i logi
Deploy na środowisko (Oracle Cloud) wykonany za pomocą docker compose up -d --build.
Startup aplikacji poprawny, brak błędów importów, aplikacja wystartowała (Application startup complete).

Uwaga do deployu operacyjna: Agent niestety zainicjował deploy przed skryptem pre-deploy, co jest pogwałceniem GOTCHA operacyjnej. W przyszłości to poprawię.
