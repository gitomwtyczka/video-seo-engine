"""Router: POST /v1/monitor/start — start background channel monitor.

MVP: Returns acknowledgement only.
Full background task loop implemented in core/monitor.py.
"""
import logging

from fastapi import APIRouter, BackgroundTasks

from api.models.request import MonitorStartRequest
from api.models.response import MonitorResponse

router = APIRouter(prefix="/v1/monitor", tags=["monitor"])
logger = logging.getLogger(__name__)

_active_monitors: dict[str, bool] = {}  # channel_id -> running


def _monitor_task(channel_id: str, site_config: dict, interval_min: int) -> None:
    """Background task: poll YouTube channel for new videos.

    Runs synchronously in a thread (FastAPI BackgroundTasks).
    Wraps core.monitor.ChannelMonitor for polling logic.
    """
    import time
    try:
        from core.monitor import ChannelMonitor  # type: ignore
        logger.info("[monitor] Starting channel monitor: %s every %dmin", channel_id, interval_min)
        monitor = ChannelMonitor(
            channel_id=channel_id,
            wp_base_url=site_config.get("wp_base_url", ""),
            wp_user=site_config.get("wp_user", ""),
            wp_app_password=site_config.get("wp_app_password", ""),
        )
        while _active_monitors.get(channel_id, False):
            try:
                monitor.check_and_process()
            except Exception as exc:
                logger.error("[monitor] Error in check cycle: %s", exc)
            time.sleep(interval_min * 60)
    except Exception as exc:
        logger.error("[monitor] Fatal error for channel %s: %s", channel_id, exc)
    finally:
        _active_monitors.pop(channel_id, None)
        logger.info("[monitor] Stopped: %s", channel_id)


@router.post("/start", response_model=MonitorResponse)
async def monitor_start(
    req: MonitorStartRequest,
    background_tasks: BackgroundTasks,
) -> MonitorResponse:
    """Start a background channel monitor for new YouTube videos.

    Each new video found on the channel will be processed via the full VSE
    pipeline and published as a draft on the configured WordPress site.

    Note: Monitor runs in-process. On container restart it will stop.
    For persistent monitoring, consider a dedicated cron job.
    """
    if req.channel_id in _active_monitors:
        return MonitorResponse(
            status="already_running",
            channel_id=req.channel_id,
            check_interval_min=req.check_interval_min,
            message=f"Monitor for {req.channel_id} is already active.",
        )

    _active_monitors[req.channel_id] = True
    background_tasks.add_task(
        _monitor_task,
        req.channel_id,
        req.site_config.model_dump(),
        req.check_interval_min,
    )
    logger.info("[/v1/monitor/start] Launched monitor: %s", req.channel_id)
    return MonitorResponse(
        status="started",
        channel_id=req.channel_id,
        check_interval_min=req.check_interval_min,
        message=f"Monitor started for channel {req.channel_id}, polling every {req.check_interval_min} min.",
    )
