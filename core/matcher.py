"""Match WordPress posts to available YouTube video IDs.

Migrated from: shadow-perihelion/scripts/video-seo/match_prawy_tv.py
Migration date: 2026-05-13
Migrated by: vse-architect-01

Refactored for multi-portal support:
- WP_URL, WP_USER, WP_APP_PASS loaded from environment
- Category ID configurable via WP_CATEGORY_ID env var
- Removed hardcoded Windows paths
"""
import json
import logging
import os
import re

import requests
from requests.auth import HTTPBasicAuth

log = logging.getLogger(__name__)

WP_URL = os.environ.get("WP_BASE_URL", "https://prawy.pl")
WP_USER = os.environ.get("WP_USER", "")
WP_APP_PASS = os.environ.get("WP_APP_PASSWORD", "")
WP_CATEGORY_ID = int(os.environ.get("WP_CATEGORY_ID", "2472"))  # Prawy TV default

auth = HTTPBasicAuth(WP_USER, WP_APP_PASS)


def get_youtube_ids_from_dir(vtt_dir: str) -> set:
    """Extract YouTube video IDs from .vtt files in a directory."""
    vtt_ids = set()
    if not os.path.isdir(vtt_dir):
        log.warning("VTT directory not found: %s", vtt_dir)
        return vtt_ids
    for f in os.listdir(vtt_dir):
        if f.endswith('.pl.vtt') or f.endswith('.vtt'):
            vid = f.replace('.pl.vtt', '').replace('.vtt', '')
            vtt_ids.add(vid)
    return vtt_ids


def fetch_posts_by_category(category_id: int, max_pages: int = 20) -> list:
    """Fetch WordPress posts from a given category via REST API.

    Returns list of post dicts with id, title, slug, content.
    """
    posts = []
    for page in range(1, max_pages + 1):
        url = (
            f"{WP_URL}/wp-json/wp/v2/posts"
            f"?categories={category_id}&per_page=50&page={page}"
            f"&_fields=id,title,slug,content,date"
        )
        try:
            resp = requests.get(url, auth=auth, timeout=30)
            if resp.status_code == 400:
                break  # beyond last page
            if resp.status_code != 200:
                log.warning("WP API returned %d on page %d", resp.status_code, page)
                break
            batch = resp.json()
            if not batch:
                break
            posts.extend(batch)
            log.info("Fetched page %d — %d posts total", page, len(posts))
        except Exception as e:
            log.error("Error fetching posts page %d: %s", page, e)
            break
    return posts


def extract_youtube_ids_from_content(content_html: str) -> list:
    """Extract all YouTube video IDs embedded in post HTML content."""
    return re.findall(r'youtube\.com/(?:watch\?v=|embed/)([a-zA-Z0-9_-]{11})', content_html)


def match_posts_to_videos(
    category_id: int = WP_CATEGORY_ID,
    vtt_dir: str = "",
    done: set = None,
) -> list:
    """Match WordPress posts to YouTube video IDs.

    Args:
        category_id: WordPress category ID to scan.
        vtt_dir: Optional directory with .vtt files — filters only posts with available VTT.
        done: Set of already-processed YouTube IDs to skip.

    Returns:
        List of match dicts: {wp_id, youtube_id, post_title, slug, post_date}
    """
    if done is None:
        done = set()

    vtt_ids = get_youtube_ids_from_dir(vtt_dir) if vtt_dir else None
    posts = fetch_posts_by_category(category_id)
    log.info("Total posts fetched: %d", len(posts))

    matches = []
    seen = set(done)

    for p in posts:
        content = p.get("content", {}).get("rendered", "")
        yt_ids = extract_youtube_ids_from_content(content)
        for yt_id in yt_ids:
            if yt_id in seen:
                continue
            if vtt_ids is not None and yt_id not in vtt_ids:
                continue
            matches.append({
                "wp_id": p["id"],
                "youtube_id": yt_id,
                "post_title": p["title"]["rendered"],
                "slug": p.get("slug", ""),
                "post_date": p.get("date", ""),
            })
            seen.add(yt_id)

    log.info("Matched %d posts with YouTube videos", len(matches))
    return matches


def save_matches(matches: list, output_path: str) -> None:
    """Save match results to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    log.info("Saved %d matches to %s", len(matches), output_path)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="[matcher] %(message)s")

    vtt_dir = os.environ.get("SUBS_DIR", "")
    output = os.environ.get("MATCHES_OUTPUT", "prawy_tv_matches.json")

    matches = match_posts_to_videos(vtt_dir=vtt_dir)
    save_matches(matches, output)

    for i, m in enumerate(matches, 1):
        print(f"  {i}. WP#{m['wp_id']} | {m['youtube_id']} | {m['post_title'][:70]}")
