"""
Users router: current user profile, usage stats, and VSE Desktop Runner package generator.
"""
import hashlib
import io
import secrets
import zipfile
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from api.db import get_db
from api.auth import get_current_user
from api.models.user import User, UsageLog, ApiKey
from api.quota import check_multilang_access

router = APIRouter(prefix="/v1/users", tags=["users"])


class PlanInfo(BaseModel):
    id: str
    display_name: str
    monthly_quota: int
    wp_sites_limit: int
    api_access: bool


class UsageInfo(BaseModel):
    used_this_month: int
    quota: int  # -1 = unlimited
    percent: float


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_verified: bool
    is_admin: bool
    has_multilang_addon: bool = False
    multilang: dict = {}
    plan_badge: str = "Free"
    desktop_runner_active: bool = False
    plan: PlanInfo
    usage: UsageInfo
    created_at: str


@router.get("/me", response_model=UserProfile)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return current user profile with plan, multilang entitlements, and monthly usage."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(func.count(UsageLog.id))
        .where(UsageLog.user_id == current_user.id)
        .where(UsageLog.success == True)  # noqa: E712
        .where(UsageLog.endpoint != "adapt_material")
        .where(UsageLog.created_at >= month_start)
    )
    used = result.scalar_one()
    quota = current_user.plan.monthly_quota if current_user.plan else 5
    percent = 0.0 if quota == -1 else round(used / quota * 100, 1) if quota > 0 else 0.0

    multilang = await check_multilang_access(current_user.id, db, user=current_user)
    has_addon = bool(multilang.get("has_multilang_addon", False))

    plan = current_user.plan
    plan_id = plan.id if plan else (current_user.plan_id or "free")

    if plan_id == "starter" and has_addon:
        plan_badge = "Starter + 🌐 8 Jęz."
    elif plan_id == "starter":
        plan_badge = "Starter"
    elif plan_id == "pro":
        plan_badge = "Pro (🌐 8 Jęz.)"
    elif plan_id == "agency":
        plan_badge = "Agency (🌐 8 Jęz.)"
    elif plan_id == "free" and has_addon:
        plan_badge = "Starter + 🌐 8 Jęz."
    else:
        plan_badge = "Free"

    runner_cutoff = now - timedelta(minutes=3)
    runner_res = await db.execute(
        select(func.count(ApiKey.id))
        .where(ApiKey.user_id == current_user.id)
        .where(ApiKey.is_active == True)  # noqa: E712
        .where(ApiKey.last_used_at >= runner_cutoff)
    )
    desktop_runner_active = (runner_res.scalar_one() or 0) > 0

    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_verified=current_user.is_verified,
        is_admin=current_user.is_admin,
        has_multilang_addon=has_addon,
        multilang=multilang,
        plan_badge=plan_badge,
        desktop_runner_active=desktop_runner_active,
        plan=PlanInfo(
            id=plan.id,
            display_name=plan.display_name,
            monthly_quota=plan.monthly_quota,
            wp_sites_limit=plan.wp_sites_limit,
            api_access=plan.api_access
        ) if plan else PlanInfo(id="free", display_name="Free", monthly_quota=5, wp_sites_limit=0, api_access=False),
        usage=UsageInfo(
            used_this_month=used,
            quota=quota,
            percent=percent
        ),
        created_at=current_user.created_at.isoformat() if current_user.created_at else ""
    )


@router.get("/desktop-runner-package")
async def get_desktop_runner_package(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Generuje gotową paczkę .zip z VSE Desktop Runnerem oraz indywidualnym kluczem API dla użytkownika."""
    user_plan = (current_user.plan_id or "free").lower()
    if user_plan == "free" and not getattr(current_user, "has_multilang_addon", False) and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Pakiet VSE Desktop Runner jest dostępny od planu Starter.",
        )

    # Dezaktywuj poprzednie klucze Desktop Runner dla tego użytkownika
    await db.execute(
        update(ApiKey)
        .where(ApiKey.user_id == current_user.id, ApiKey.name == "VSE Desktop Runner")
        .values(is_active=False)
    )

    raw_key = f"vse_live_{secrets.token_urlsafe(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    new_key = ApiKey(
        user_id=current_user.id,
        key_hash=key_hash,
        key_prefix=raw_key[:14] + "...",
        name="VSE Desktop Runner",
        is_active=True,
    )
    db.add(new_key)
    await db.commit()

    runner_py = f'''#!/usr/bin/env python3
"""
PressAI VSE Desktop Runner — Lokalny Akcelerator YouTube & ShortMachine
Skonfigurowany automatycznie dla konta: {current_user.email}
"""
import re
import time
import requests

API_BASE = "https://vse.impresjapr.pl"
RUNNER_TOKEN = "{raw_key}"
POLL_INTERVAL = 3

HEADERS = {{
    "Authorization": f"Bearer {{RUNNER_TOKEN}}",
    "Content-Type": "application/json",
}}


def extract_video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\\.be/|shorts/|embed/)([a-zA-Z0-9_-]{{11}})", url)
    return m.group(1) if m else url.strip()


def fetch_transcript(video_url: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi
    vid = extract_video_id(video_url)
    ytt = YouTubeTranscriptApi()
    t_list = list(ytt.list(vid))
    if not t_list:
        raise RuntimeError("No transcript available")
    chosen = t_list[0]
    for t in t_list:
        code = getattr(t, "language_code", "")
        if code.startswith("pl") or code.startswith("en"):
            chosen = t
            break
    entries = chosen.fetch()
    lines = ["__VTT__"]
    for item in entries:
        start = int(getattr(item, "start", 0) if not isinstance(item, dict) else item.get("start", 0))
        text = (getattr(item, "text", "") if not isinstance(item, dict) else item.get("text", "")).replace("\\n", " ").strip()
        if text:
            mm, ss = divmod(start, 60)
            lines.append(f"[{{mm:02d}}:{{ss:02d}}] {{text}}")
    return "\\n".join(lines)


def main():
    print("============================================================")
    print(" PressAI VSE Desktop Runner — Aktywny")
    print(" Konto: {current_user.email}")
    print("============================================================")
    while True:
        try:
            resp = requests.get(f"{{API_BASE}}/v1/jobs/pending", headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                jobs = resp.json()
                for job in jobs:
                    job_id = job["id"]
                    v_url = job["video_url"]
                    print(f"[VSE Runner] Pobieranie napisów dla: {{v_url}} ...")
                    try:
                        vtt = fetch_transcript(v_url)
                        requests.post(
                            f"{{API_BASE}}/v1/jobs/{{job_id}}/result",
                            headers=HEADERS,
                            json={{"status": "fetched", "transcript": vtt}},
                            timeout=20,
                        )
                        print(f"[VSE Runner] Sukces ({{len(vtt)}} znaków) -> wysłano do chmury VSE!")
                    except Exception as e:
                        requests.post(
                            f"{{API_BASE}}/v1/jobs/{{job_id}}/result",
                            headers=HEADERS,
                            json={{"status": "failed", "error": str(e)}},
                            timeout=20,
                        )
                        print(f"[VSE Runner] Błąd dla {{v_url}}: {{e}}")
        except Exception as exc:
            print(f"[VSE Runner] Połączenie: {{exc}}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
'''

    runner_bat = """@echo off
title PressAI VSE Desktop Runner
echo ============================================================
echo  Inicjalizacja PressAI VSE Desktop Runner...
echo ============================================================
pip install -q requests youtube-transcript-api yt-dlp
python vse_runner.py
pause
"""

    instrukcja_txt = f"""============================================================
PressAI VSE Desktop Runner — Instrukcja uruchomienia
Konto: {current_user.email}
============================================================

PL:
1. Wypakuj wszystkie pliki z archiwum vse-desktop-runner.zip do dowolnego folderu.
2. Kliknij dwukrotnie plik "Uruchom_VSE_Runner.bat" (na Windows) lub uruchom "python3 vse_runner.py" (na macOS/Linux).
3. Twój pakiet jest już automatycznie skonfigurowany z Twoim indywidualnym kluczem API ({raw_key[:14]}...).
4. Gdy okno VSE Desktop Runnera jest otwarte, wszystkie generowania w panelu https://vse.impresjapr.pl korzystają z Twojego domowego łączą w ułamku sekundy!

EN:
1. Extract all files from vse-desktop-runner.zip into any folder.
2. Double-click "Uruchom_VSE_Runner.bat" (Windows) or run "python3 vse_runner.py" (macOS/Linux).
3. Your package is pre-configured for account {current_user.email}.
"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("vse_runner.py", runner_py)
        zf.writestr("Uruchom_VSE_Runner.bat", runner_bat)
        zf.writestr("INSTRUKCJA.txt", instrukcja_txt)

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="vse-desktop-runner.zip"'},
    )


