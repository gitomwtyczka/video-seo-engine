#!/usr/bin/env python3
"""PressAI Video SEO Engine -- Unified CLI entry point.

Usage:
  vse generate --video <YT_ID>                        # Single video -> SEO JSON
  vse generate --batch prawy_tv_matches.json          # Batch generate from matches file
  vse inject --video <YT_ID> --wp-id <WP_ID>         # Inject single video to WP
  vse inject --batch seo_results/                     # Batch inject from SEO dir
  vse fetch --video <URL>                             # Fetch YouTube data + VTT
  vse fetch --channel <CHANNEL_ID>                    # List channel videos
  vse match                                           # Match WP posts to YouTube IDs
  vse sitemap                                         # Generate video sitemap XML
  vse watch --channel <CHANNEL_ID>                    # Monitor YT channel for new videos
  vse watch --channel <CHANNEL_ID> --dry-run          # Dry-run: show what would be processed
  vse update-yt --all-registry                        # Update YT descriptions for all registry videos
  vse update-yt --video <YT_ID> --wp-url <URL>        # Update single video description on YouTube

For full options on any subcommand:
  vse <command> --help

Environment variables (or .env file):
  GEMINI_API_KEY    -- required for generate / watch
  WP_USER           -- required for inject / watch
  WP_APP_PASSWORD   -- required for inject / watch
  WP_BASE_URL       -- required for inject / match / sitemap / watch (default: https://prawy.pl)
  YT_API_KEY        -- required for watch (YouTube Data API v3)
  YT_CLIENT_ID      -- required for update-yt (OAuth 2.0)
  YT_CLIENT_SECRET  -- required for update-yt (OAuth 2.0)
  YT_REFRESH_TOKEN  -- required for update-yt (OAuth 2.0)
  CHANNEL_ID        -- YouTube channel ID (for watch)
  MONITOR_INTERVAL  -- polling interval in seconds (default: 3600)
  PORTAL            -- prawy | kurier365 | biznesciti (default: prawy)
  SUBS_DIR          -- path to .vtt files directory
  SEO_DIR           -- path to seo_results directory
"""
import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv  # type: ignore

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================
# HELPERS -- env resolution
# ============================================================

def _require_env(name: str) -> str:
    """Return env var value or exit with helpful error."""
    val = os.environ.get(name, "")
    if not val:
        logger.error("Missing required env var: %s (set in .env or environment)", name)
        sys.exit(1)
    return val


# ============================================================
# SUBCOMMAND: fetch
# ============================================================

def cmd_fetch(args: argparse.Namespace) -> None:
    """Fetch YouTube transcript + metadata for a video or channel."""
    from core.fetcher import main as fetcher_main  # type: ignore
    sys.argv = [sys.argv[0]] + args.rest
    fetcher_main()


# ============================================================
# SUBCOMMAND: match
# ============================================================

def cmd_match(args: argparse.Namespace) -> None:
    """Match WordPress posts to YouTube IDs (MODE B -- portal scanner)."""
    from core.matcher import main as matcher_main  # type: ignore
    matcher_main()


# ============================================================
# SUBCOMMAND: sitemap
# ============================================================

def cmd_sitemap(args: argparse.Namespace) -> None:
    """Generate video sitemap XML."""
    from core.sitemap import main as sitemap_main  # type: ignore
    sys.argv = [sys.argv[0]] + args.rest
    sitemap_main()


# ============================================================
# SUBCOMMAND: generate
# ============================================================

def cmd_generate(args: argparse.Namespace) -> None:
    """Generate SEO schema JSON via Gemini for one video or a batch."""
    import json
    from core.generator import process_video  # type: ignore

    api_key = _require_env("GEMINI_API_KEY")
    subs_dir = os.environ.get("SUBS_DIR", "subs")
    seo_dir = os.environ.get("SEO_DIR", "seo_results")

    if args.video:
        # Single video mode -- requires --wp-id and --title
        if not args.wp_id or not args.title:
            logger.error("Single mode requires --wp-id and --title")
            sys.exit(1)
        yt_id = args.video
        vtt_path = os.path.join(subs_dir, f"{yt_id}.pl.vtt")
        if not os.path.exists(vtt_path):
            logger.error("VTT not found: %s", vtt_path)
            sys.exit(1)
        yt_url = f"https://www.youtube.com/watch?v={yt_id}"
        result = process_video(
            youtube_id=yt_id,
            wp_id=int(args.wp_id),
            post_title=args.title,
            yt_url=yt_url,
            vtt_path=vtt_path,
            api_key=api_key,
            out_dir=seo_dir,
        )
        print(f"OK: {yt_id} -> {seo_dir}/{yt_id}.json")
        print(f"  focus_keyphrase: {result.get('focus_keyphrase')}")
        print(f"  chapters: {len(result.get('chapters', []))}")

    elif args.batch:
        # Batch mode -- load matches JSON
        if not os.path.exists(args.batch):
            logger.error("Batch file not found: %s", args.batch)
            sys.exit(1)
        with open(args.batch, "r", encoding="utf-8") as f:
            matches = json.load(f)

        logger.info("Batch generate: %d videos from %s", len(matches), args.batch)
        ok_count = 0
        fail_count = 0
        for i, m in enumerate(matches):
            yt_id = m.get("youtube_id", "")
            wp_id = m.get("wp_id", 0)
            title = m.get("post_title", m.get("title", ""))
            yt_url = m.get("yt_url", f"https://www.youtube.com/watch?v={yt_id}")
            vtt_path = os.path.join(subs_dir, f"{yt_id}.pl.vtt")

            logger.info("[%d/%d] %s | WP#%s", i + 1, len(matches), yt_id, wp_id)

            if not os.path.exists(vtt_path):
                logger.warning("  SKIP -- VTT not found: %s", vtt_path)
                fail_count += 1
                continue

            out_path = os.path.join(seo_dir, f"{yt_id}.json")
            if os.path.exists(out_path) and not args.force:
                logger.info("  SKIP -- already exists (use --force to overwrite)")
                ok_count += 1
                continue

            try:
                process_video(
                    youtube_id=yt_id,
                    wp_id=int(wp_id),
                    post_title=title,
                    yt_url=yt_url,
                    vtt_path=vtt_path,
                    api_key=api_key,
                    out_dir=seo_dir,
                    sleep_between=args.sleep,
                )
                ok_count += 1
            except Exception as exc:
                logger.error("  FAIL: %s", exc)
                fail_count += 1

        logger.info("Batch done: %d OK / %d FAIL", ok_count, fail_count)

    else:
        logger.error("Provide --video <YT_ID> or --batch <matches.json>")
        sys.exit(1)


# ============================================================
# SUBCOMMAND: inject
# ============================================================

def cmd_inject(args: argparse.Namespace) -> None:
    """Inject SEO content to WordPress post(s) via REST API."""
    import json
    from core.injector import inject_video  # type: ignore
    from core.profile import resolve_profile  # type: ignore

    # Load profile (YAML or env fallback)
    profile = resolve_profile(getattr(args, "profile", None))
    paths = profile.get("paths", {})

    wp_base_url = profile.get("wp_base_url") or os.environ.get("WP_BASE_URL", "https://prawy.pl")
    wp_user = profile.get("wp_user") or _require_env("WP_USER")
    wp_app_pass = profile.get("wp_app_password") or _require_env("WP_APP_PASSWORD")
    yt_api_key = profile.get("yt_api_key") or os.environ.get("YT_API_KEY", "") or None
    dry_run = args.dry_run

    if dry_run:
        logger.info("DRY RUN mode -- no actual changes to WordPress")

    if args.video:
        # Single inject mode -- requires --wp-id and seo JSON
        if not args.wp_id:
            logger.error("Single inject requires --wp-id")
            sys.exit(1)
        yt_id = args.video
        seo_dir = paths.get("seo_dir") or os.environ.get("SEO_DIR", "seo_results")
        seo_path = os.path.join(seo_dir, f"{yt_id}.json")
        if not os.path.exists(seo_path):
            logger.error("SEO JSON not found: %s (run 'vse generate' first)", seo_path)
            sys.exit(1)
        with open(seo_path, "r", encoding="utf-8") as f:
            seo = json.load(f)
        result = inject_video(
            wp_id=int(args.wp_id),
            yt_id=yt_id,
            seo=seo,
            wp_base_url=wp_base_url,
            wp_user=wp_user,
            wp_app_pass=wp_app_pass,
            yt_api_key=yt_api_key,
            dry_run=dry_run,
            skip_thumbnail=args.skip_thumbnail,
            profile=profile,
        )
        status_str = "OK" if result["ok"] else "FAIL"
        print(f"[{status_str}] WP#{args.wp_id} | {result['link']}")

    elif args.batch:
        # Batch inject -- iterate all JSONs in a directory
        seo_dir = args.batch.rstrip("/\\")
        if not os.path.isdir(seo_dir):
            logger.error("Batch dir not found: %s", seo_dir)
            sys.exit(1)
        json_files = sorted(f for f in os.listdir(seo_dir) if f.endswith(".json"))
        logger.info("Batch inject: %d files from %s", len(json_files), seo_dir)
        ok_count = 0
        fail_count = 0
        for i, fname in enumerate(json_files):
            seo_path = os.path.join(seo_dir, fname)
            with open(seo_path, "r", encoding="utf-8") as f:
                seo = json.load(f)
            yt_id = seo.get("youtube_id", fname.replace(".json", ""))
            wp_id = seo.get("wp_id", 0)
            if not wp_id:
                logger.warning("[%d/%d] SKIP -- no wp_id in %s", i + 1, len(json_files), fname)
                fail_count += 1
                continue
            logger.info("[%d/%d] WP#%s | YT:%s", i + 1, len(json_files), wp_id, yt_id)
            try:
                result = inject_video(
                    wp_id=int(wp_id),
                    yt_id=yt_id,
                    seo=seo,
                    wp_base_url=wp_base_url,
                    wp_user=wp_user,
                    wp_app_pass=wp_app_pass,
                    yt_api_key=yt_api_key,
                    dry_run=dry_run,
                    skip_thumbnail=args.skip_thumbnail,
                    profile=profile,
                )
                if result["ok"]:
                    ok_count += 1
                else:
                    fail_count += 1
            except Exception as exc:
                logger.error("  FAIL: %s", exc)
                fail_count += 1

        logger.info("Batch inject done: %d OK / %d FAIL", ok_count, fail_count)

    else:
        logger.error("Provide --video <YT_ID> --wp-id <ID> or --batch <seo_dir/>")
        sys.exit(1)


# ============================================================
# SUBCOMMAND: update-yt (Faza 2B — YouTube Description Writer)
# ============================================================

def cmd_update_yt(args: argparse.Namespace) -> None:
    """Write enriched descriptions + chapters + footer back to YouTube (OAuth).

    Faza 2B: retroactive batch update for 213+ Prawy TV videos.
    Uses YouTube Data API v3 videos.update (50 quota units each).
    Daily limit: ~200 updates/day at default delay.

    Requires OAuth credentials in .env:
        YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
    """
    import json
    from core.yt_admin import update_video_description, batch_update_from_registry  # type: ignore

    wp_base_url = os.environ.get("WP_BASE_URL", "https://prawy.pl")
    seo_dir = Path(os.environ.get("SEO_DIR", "seo_results"))
    registry_dir = Path(args.registry_dir)
    dry_run = args.dry_run
    delay = args.delay

    # Verify OAuth credentials are present
    for cred in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        if not os.environ.get(cred):
            logger.error("Missing OAuth credential: %s (set in .env)", cred)
            sys.exit(1)

    if dry_run:
        logger.info("DRY RUN -- no changes will be made to YouTube")

    if args.all_registry:
        # Batch mode: update all videos with SEO JSON in the registry
        logger.info(
            "Batch update-yt: registry=%s seo=%s delay=%.1fs",
            registry_dir, seo_dir, delay,
        )
        stats = batch_update_from_registry(
            registry_dir=registry_dir,
            seo_dir=seo_dir,
            wp_base_url=wp_base_url,
            dry_run=dry_run,
            delay_between=delay,
        )
        print(
            f"\nBatch complete: {stats['success']} updated | "
            f"{stats['failed']} failed | {stats['skipped']} skipped | "
            f"{stats['total']} total"
        )

    elif args.video:
        # Single video mode
        yt_id = args.video
        wp_url = args.wp_url or wp_base_url

        seo_file = seo_dir / f"{yt_id}.json"
        if not seo_file.exists():
            logger.error("SEO JSON not found: %s (run 'vse generate' first)", seo_file)
            sys.exit(1)

        with open(seo_file, "r", encoding="utf-8") as f:
            seo = json.load(f)

        logger.info("update-yt: %s | wp_url=%s", yt_id, wp_url)
        ok = update_video_description(yt_id, seo, wp_url, dry_run=dry_run)
        if ok:
            print(f"[OK] YouTube description updated: {yt_id}")
        else:
            print(f"[FAIL] Could not update: {yt_id}")
            sys.exit(1)

    else:
        logger.error("Provide --video <YT_ID> --wp-url <URL> or --all-registry")
        sys.exit(1)


# ============================================================
# SUBCOMMAND: watch (MODE A -- YouTube Channel Monitor)
# ============================================================

def cmd_watch(args: argparse.Namespace) -> None:
    """Watch a YouTube channel for new videos and create WP drafts (MODE A)."""
    from core.monitor import watch  # type: ignore
    from core.profile import resolve_profile  # type: ignore

    # Load profile (YAML or env fallback)
    profile = resolve_profile(getattr(args, "profile", None))
    paths = profile.get("paths", {})
    mon_cfg = profile.get("monitor", {})
    delay_cfg = profile.get("publish_delay", {})

    channel_id = args.channel or (profile.get("channel_ids") or [None])[0] or os.environ.get("CHANNEL_ID", "")
    if not channel_id:
        logger.error("Provide --channel <CHANNEL_ID>, set in profile, or CHANNEL_ID in .env")
        sys.exit(1)

    yt_api_key = profile.get("yt_api_key") or _require_env("YT_API_KEY")
    wp_base_url = profile.get("wp_base_url") or os.environ.get("WP_BASE_URL", "https://prawy.pl")
    wp_user = profile.get("wp_user") or _require_env("WP_USER")
    wp_app_pass = profile.get("wp_app_password") or _require_env("WP_APP_PASSWORD")
    gemini_api_key = profile.get("gemini_api_key") or _require_env("GEMINI_API_KEY")
    subs_dir = paths.get("subs_dir") or os.environ.get("SUBS_DIR", "subs")
    seo_dir = paths.get("seo_dir") or os.environ.get("SEO_DIR", "seo_results")
    interval = args.interval or mon_cfg.get("interval_seconds") or int(os.environ.get("MONITOR_INTERVAL", "3600"))
    registry_dir = Path(paths.get("registry_dir") or args.registry_dir)

    publish_delay_min = args.publish_delay_min or delay_cfg.get("min") or int(
        os.environ.get("PUBLISH_DELAY_MIN", "5")
    )
    publish_delay_max = args.publish_delay_max or delay_cfg.get("max") or int(
        os.environ.get("PUBLISH_DELAY_MAX", "37")
    )

    if args.dry_run:
        logger.info("DRY RUN -- no WordPress or Gemini calls will be made")

    watch(
        channel_id=channel_id,
        yt_api_key=yt_api_key,
        wp_base_url=wp_base_url,
        wp_user=wp_user,
        wp_app_pass=wp_app_pass,
        gemini_api_key=gemini_api_key,
        subs_dir=subs_dir,
        seo_dir=seo_dir,
        interval=interval,
        registry_dir=registry_dir,
        dry_run=args.dry_run,
        run_once=args.once,
        publish_delay_min=publish_delay_min,
        publish_delay_max=publish_delay_max,
    )


# ============================================================
# MAIN PARSER
# ============================================================

def main() -> None:
    """Main CLI dispatcher for PressAI Video SEO Engine."""
    parser = argparse.ArgumentParser(
        prog="vse",
        description="PressAI Video SEO Engine -- automated video content optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- fetch ---
    fetch_p = subparsers.add_parser("fetch", help="Fetch YouTube data + VTT transcript")
    fetch_p.add_argument("rest", nargs=argparse.REMAINDER)
    fetch_p.set_defaults(func=cmd_fetch)

    # --- match ---
    match_p = subparsers.add_parser("match", help="Match WP posts to YouTube IDs")
    match_p.add_argument("--portal", default=os.environ.get("PORTAL", "prawy"),
                          help="Portal ID (default: prawy)")
    match_p.set_defaults(func=cmd_match)

    # --- sitemap ---
    sitemap_p = subparsers.add_parser("sitemap", help="Generate video sitemap XML")
    sitemap_p.add_argument("rest", nargs=argparse.REMAINDER)
    sitemap_p.set_defaults(func=cmd_sitemap)

    # --- generate ---
    gen_p = subparsers.add_parser("generate", help="Generate SEO schema JSON via Gemini")
    gen_p.add_argument("--video", metavar="YT_ID", help="Single YouTube video ID")
    gen_p.add_argument("--wp-id", metavar="WP_ID", help="WordPress post ID (single mode)")
    gen_p.add_argument("--title", metavar="TITLE", help="Post title (single mode)")
    gen_p.add_argument("--batch", metavar="MATCHES_JSON",
                        help="Path to matches JSON file (batch mode)")
    gen_p.add_argument("--force", action="store_true",
                        help="Overwrite existing SEO JSON files")
    gen_p.add_argument("--sleep", type=int, default=5,
                        help="Seconds between Gemini calls in batch mode (default: 5)")
    gen_p.add_argument("--profile", metavar="PROFILE",
                        default=os.environ.get("PORTAL", "prawy"),
                        help="Portal profile name (default: prawy)")
    gen_p.set_defaults(func=cmd_generate)

    # --- inject ---
    inj_p = subparsers.add_parser("inject", help="Inject SEO schema to WordPress post")
    inj_p.add_argument("--video", metavar="YT_ID", help="Single YouTube video ID")
    inj_p.add_argument("--wp-id", metavar="WP_ID", help="WordPress post ID (single mode)")
    inj_p.add_argument("--batch", metavar="SEO_DIR",
                        help="Path to seo_results directory (batch mode)")
    inj_p.add_argument("--dry-run", action="store_true",
                        help="Print what would be done without changing WordPress")
    inj_p.add_argument("--skip-thumbnail", action="store_true",
                        help="Skip YouTube thumbnail upload/set")
    inj_p.add_argument("--profile", metavar="PROFILE",
                        default=os.environ.get("PORTAL", "prawy"),
                        help="Portal profile name (default: prawy)")
    inj_p.set_defaults(func=cmd_inject)

    # --- update-yt ---
    uyt_p = subparsers.add_parser(
        "update-yt",
        help="Write enriched descriptions + chapters + footer to YouTube (OAuth 2.0)",
    )
    uyt_p.add_argument(
        "--video", metavar="YT_ID",
        help="Single YouTube video ID to update",
    )
    uyt_p.add_argument(
        "--wp-url", metavar="URL",
        help="WordPress article URL to include in description (single mode)",
    )
    uyt_p.add_argument(
        "--all-registry", action="store_true",
        help="Update all videos in registry/ that have a matching SEO JSON",
    )
    uyt_p.add_argument(
        "--registry-dir", metavar="DIR", default="registry",
        help="Path to registry directory (default: registry/)",
    )
    uyt_p.add_argument(
        "--dry-run", action="store_true",
        help="Build descriptions and log without pushing to YouTube",
    )
    uyt_p.add_argument(
        "--delay", metavar="SECONDS", type=float, default=2.0,
        help="Delay between API calls in batch mode (default: 2.0s)",
    )
    uyt_p.set_defaults(func=cmd_update_yt)

    # --- watch ---
    watch_p = subparsers.add_parser(
        "watch",
        help="Monitor YouTube channel for new videos (MODE A -- push)",
    )
    watch_p.add_argument(
        "--channel", metavar="CHANNEL_ID",
        help="YouTube channel ID (or set CHANNEL_ID in .env)",
    )
    watch_p.add_argument(
        "--interval", metavar="SECONDS", type=int,
        help="Polling interval in seconds (default: MONITOR_INTERVAL env or 3600)",
    )
    watch_p.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be processed without making any API calls",
    )
    watch_p.add_argument(
        "--once", action="store_true",
        help="Poll once and exit (useful for cron / CI)",
    )
    watch_p.add_argument(
        "--registry-dir", metavar="DIR", default="registry",
        help="Path to the registry directory (default: registry/)",
    )
    watch_p.add_argument(
        "--publish-delay-min", metavar="MINUTES", type=int, default=None,
        help="Min WP publish delay after YT premiere (default: 5)",
    )
    watch_p.add_argument(
        "--publish-delay-max", metavar="MINUTES", type=int, default=None,
        help="Max WP publish delay after YT premiere (default: 37)",
    )
    watch_p.add_argument(
        "--profile", metavar="PROFILE",
        default=os.environ.get("PORTAL", "prawy"),
        help="Portal profile name (default: prawy)",
    )
    watch_p.set_defaults(func=cmd_watch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
