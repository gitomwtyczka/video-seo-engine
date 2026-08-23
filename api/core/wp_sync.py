"""WP Sync — tworzy/aktualizuje CPT szort w WordPress po VSE inject."""
import os
import requests
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

WP_URL = os.getenv('WP_URL', '')
WP_USER = os.getenv('WP_USER', '')
WP_APP_PASSWORD = os.getenv('WP_APP_PASSWORD', '')


def create_szort(
    youtube_id: str,
    title: str,
    publish_at: str | None,
    thumbnail_url: str = '',
    hook_text: str = '',
    suggested_title: str = '',
    tags: str = '',
    channel_id: str = '',
    duration_sec: int = 0,
) -> dict:
    """Tworzy post CPT szort w WordPress przez REST API."""
    if not WP_URL or not WP_USER or not WP_APP_PASSWORD:
        logger.warning('WP Sync: brak credentials (WP_URL/WP_USER/WP_APP_PASSWORD)')
        return {'error': 'No WP credentials configured'}

    if publish_at:
        status = 'future'
        post_date_local = _utc_to_wp_local(publish_at)
    else:
        status = 'publish'
        post_date_local = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    payload = {
        'title': title,
        'status': status,
        'date': post_date_local,
        'meta': {
            'youtube_id': youtube_id,
            'youtube_url': f'https://www.youtube.com/shorts/{youtube_id}',
            'view_count': 0,
            'publish_at': publish_at or '',
            'thumbnail_url': thumbnail_url,
            'duration_sec': duration_sec,
            'hook_text': hook_text,
            'suggested_title': suggested_title,
            'tags': tags,
            'channel_id': channel_id,
            'vse_synced_at': datetime.now(timezone.utc).isoformat(),
        },
    }

    resp = requests.post(
        f'{WP_URL.rstrip("/")}/wp-json/wp/v2/szorty',
        json=payload,
        auth=(WP_USER, WP_APP_PASSWORD),
        timeout=15,
    )

    if resp.status_code in (200, 201):
        data = resp.json()
        logger.info('WP Sync: created szort ID=%s for youtube_id=%s', data.get('id'), youtube_id)
        return {'wp_post_id': data.get('id'), 'wp_post_url': data.get('link')}
    else:
        logger.error('WP Sync error: %s %s', resp.status_code, resp.text[:200])
        return {'error': f'WP API error {resp.status_code}: {resp.text[:100]}'}


def _utc_to_wp_local(utc_iso: str) -> str:
    """Konwertuje UTC ISO string na format lokalny WP (Europe/Warsaw)."""
    try:
        from zoneinfo import ZoneInfo
        dt_utc = datetime.fromisoformat(utc_iso.replace('Z', '+00:00'))
        dt_local = dt_utc.astimezone(ZoneInfo('Europe/Warsaw'))
        return dt_local.strftime('%Y-%m-%dT%H:%M:%S')
    except Exception:
        return utc_iso[:19]
