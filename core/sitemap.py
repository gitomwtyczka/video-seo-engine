"""Generate supplementary video sitemap for WordPress portals.

Migrated from: shadow-perihelion/scripts/video-seo/generate_video_sitemap.py
Migration date: 2026-05-13
Migrated by: vse-architect-01

Refactored for multi-portal support:
- All paths loaded from environment / CLI args
- Removed hardcoded Windows paths
- Logging instead of print for non-output messages

Usage:
    python -m core.sitemap --matches prawy_tv_matches.json --output video-sitemap.xml
    python -m core.sitemap --matches matches.json --seo-dir seo_results/ --wp-url https://prawy.pl
"""
import argparse
import json
import logging
import os
import re
from datetime import datetime
from xml.sax.saxutils import escape

log = logging.getLogger(__name__)


def load_matches(path: str) -> list:
    """Load prawy_tv_matches.json or any matches file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_duration_from_seo(seo_dir: str) -> dict:
    """Load duration data from seo_results/*.json files.

    Returns dict: {youtube_id: duration_seconds}
    """
    durations = {}
    if not os.path.isdir(seo_dir):
        log.warning("SEO dir not found: %s", seo_dir)
        return durations
    for fname in os.listdir(seo_dir):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(seo_dir, fname), 'r', encoding='utf-8') as f:
                data = json.load(f)
            yt_id = data.get("youtube_id", "")
            dur = data.get("duration_seconds") or data.get("duration", 0)
            if yt_id and dur:
                durations[yt_id] = int(dur)
        except (json.JSONDecodeError, KeyError):
            continue
    log.info("Loaded %d duration values from SEO results", len(durations))
    return durations


def estimate_duration_from_vtt(vtt_dir: str, youtube_id: str) -> int:
    """Estimate duration from VTT file size (~130 bytes per second)."""
    vtt_path = os.path.join(vtt_dir, f"{youtube_id}.pl.vtt")
    if os.path.exists(vtt_path):
        size = os.path.getsize(vtt_path)
        return max(60, size // 130)
    return 0


def generate_xml(
    matches: list,
    durations: dict,
    wp_url: str,
    vtt_dir: str = "",
) -> str:
    """Generate video sitemap XML string.

    Args:
        matches: List of match dicts (wp_id, youtube_id, post_title, slug, post_date).
        durations: Dict {youtube_id: duration_seconds}.
        wp_url: Base WordPress URL.
        vtt_dir: Optional directory with .vtt files for duration estimation.

    Returns:
        XML string conforming to Google Video Sitemap 1.1 spec.
    """
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">',
    ]

    stats = {"total": 0, "with_duration": 0, "estimated_duration": 0, "no_duration": 0}

    for m in matches:
        wp_id = m["wp_id"]
        yt_id = m["youtube_id"]
        title = m.get("post_title", f"Video #{wp_id}")
        slug = m.get("slug", "")

        # Clean HTML entities from title
        title = title.replace("&#8211;", "–").replace("&#8212;", "—")
        title = title.replace("&amp;", "&").replace("&#038;", "&")
        title = re.sub(r'&#\d+;', '', title)

        # Get duration
        duration = durations.get(yt_id, 0)
        duration_source = "seo"
        if not duration and vtt_dir:
            duration = estimate_duration_from_vtt(vtt_dir, yt_id)
            duration_source = "vtt_estimate"

        if duration:
            if duration_source == "seo":
                stats["with_duration"] += 1
            else:
                stats["estimated_duration"] += 1
        else:
            stats["no_duration"] += 1

        loc = f"{wp_url}/{slug}/" if slug else f"{wp_url}/?p={wp_id}"
        pub_date = m.get("post_date", "") or datetime.now().strftime("%Y-%m-%dT%H:%M:%S+02:00")
        thumbnail = f"https://i.ytimg.com/vi/{yt_id}/maxresdefault.jpg"
        description = f"{escape(title)} — program wideo"

        xml_parts.append('  <url>')
        xml_parts.append(f'    <loc>{escape(loc)}</loc>')
        xml_parts.append(f'    <video:video>')
        xml_parts.append(f'      <video:thumbnail_loc>{thumbnail}</video:thumbnail_loc>')
        xml_parts.append(f'      <video:title><![CDATA[{title}]]></video:title>')
        xml_parts.append(f'      <video:description><![CDATA[{description}]]></video:description>')
        xml_parts.append(f'      <video:content_loc>https://www.youtube.com/watch?v={yt_id}</video:content_loc>')
        xml_parts.append(f'      <video:player_loc>https://www.youtube.com/embed/{yt_id}</video:player_loc>')
        if duration:
            xml_parts.append(f'      <video:duration>{duration}</video:duration>')
        xml_parts.append(f'      <video:publication_date>{pub_date}</video:publication_date>')
        xml_parts.append(f'      <video:family_friendly>yes</video:family_friendly>')
        xml_parts.append(f'      <video:live>no</video:live>')
        xml_parts.append(f'    </video:video>')
        xml_parts.append(f'  </url>')
        stats["total"] += 1

    xml_parts.append('</urlset>')
    xml_parts.append(f'<!-- Generated by core/sitemap.py | {datetime.now().isoformat()} -->')
    xml_parts.append(
        f'<!-- Stats: {stats["total"]} videos, {stats["with_duration"]} with duration, '
        f'{stats["estimated_duration"]} estimated, {stats["no_duration"]} without -->'
    )

    log.info(
        "Sitemap stats: total=%d with_duration=%d estimated=%d no_duration=%d",
        stats["total"], stats["with_duration"], stats["estimated_duration"], stats["no_duration"]
    )
    return '\n'.join(xml_parts)


def main():
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="[sitemap] %(message)s")
    parser = argparse.ArgumentParser(description="Generate video sitemap for WordPress portals")
    parser.add_argument("--matches", required=True, help="Path to matches JSON file")
    parser.add_argument("--seo-dir", default="", help="Path to seo_results/ directory with duration data")
    parser.add_argument("--vtt-dir", default="", help="Path to VTT subtitles directory")
    parser.add_argument("--output", required=True, help="Output XML path")
    parser.add_argument("--wp-url", default=os.environ.get("WP_BASE_URL", "https://prawy.pl"))
    args = parser.parse_args()

    log.info("Generating video sitemap: %s → %s", args.matches, args.output)

    matches = load_matches(args.matches)
    log.info("Loaded %d matches", len(matches))

    durations = load_duration_from_seo(args.seo_dir) if args.seo_dir else {}
    xml_content = generate_xml(matches, durations, args.wp_url, args.vtt_dir)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(xml_content)

    print(f"✅ Video sitemap saved: {args.output} ({len(xml_content):,} bytes)")
    print("📋 Next steps:")
    print("   1. Upload to portal root or serve via WordPress")
    print("   2. Submit in Google Search Console: Sitemaps → Add")


if __name__ == "__main__":
    main()
