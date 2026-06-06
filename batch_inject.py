"""
Batch SEO Injector v1.0 — injects generated SEO JSON into WordPress.
Emulates natural editorial cadence: 15-22 posts/day with random pauses.

Usage:
  python batch_inject.py                     # natural cadence (15-22/day)
  python batch_inject.py --limit 3 --no-delay  # test mode: 3 posts, no pause
  python batch_inject.py --dry-run             # validate only
"""
import json
import os
import sys
import time
import random
import argparse
from datetime import datetime

# Import core functions from existing pipeline
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject_rest_v5 import update_post, set_youtube_thumbnail, auth, WP_URL
import requests

SEO_DIR = r"D:\Biblioteki\prawy.pl\seo_results_v5"
PROGRESS_FILE = os.path.join(SEO_DIR, "inject_progress.json")

# Natural cadence settings
DAILY_LIMIT = 18
MIN_DELAY_MIN = 3
MAX_DELAY_MIN = 15
WORK_START = 8
WORK_END = 17


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"injected": {}, "skipped": {}, "failed": {}}


def save_progress(progress):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def is_already_injected(wp_id):
    """Check if post already has SEO content injected."""
    try:
        url = f"{WP_URL}/wp-json/wp/v2/posts/{wp_id}"
        resp = requests.get(url, auth=auth, timeout=15)
        if resp.status_code == 200:
            content = resp.json().get("content", {}).get("rendered", "")
            return "prawy-chapter" in content or "VideoObject" in content
    except Exception:
        pass
    return False


def get_seo_files():
    """Get all SEO JSON files sorted by name."""
    files = []
    for f in os.listdir(SEO_DIR):
        if f.endswith('.json') and f not in ('batch_report.json', 'inject_progress.json', 'inject_report.json'):
            files.append(os.path.join(SEO_DIR, f))
    files.sort()
    return files


def inject_single(seo_path, progress, dry_run=False, no_thumb=False):
    """Inject one SEO JSON into WordPress."""
    with open(seo_path, 'r', encoding='utf-8') as f:
        seo = json.load(f)
    
    wp_id = seo.get("wp_id")
    yt_id = seo.get("youtube_id")
    title = seo.get("original_title", "?")
    
    if not wp_id or not yt_id:
        return "error", f"Missing wp_id or youtube_id in {seo_path}"
    
    wp_id_str = str(wp_id)
    
    # Skip if already in progress
    if wp_id_str in progress["injected"]:
        return "skip_progress", None
    if wp_id_str in progress["skipped"]:
        return "skip_progress", None
    
    # Check if already injected in WP
    if is_already_injected(wp_id):
        progress["skipped"][wp_id_str] = {
            "date": datetime.now().isoformat(),
            "reason": "already_injected",
            "youtube_id": yt_id
        }
        save_progress(progress)
        return "skip_wp", None
    
    if dry_run:
        print(f"  [DRY-RUN] Would inject WP#{wp_id} | {yt_id} | {title[:50]}")
        return "dry_run", None
    
    # Inject content
    try:
        status_code, link = update_post(wp_id, seo, yt_id)
        
        if status_code == 200:
            # Set thumbnail
            if not no_thumb:
                set_youtube_thumbnail(wp_id, yt_id, title)
            
            progress["injected"][wp_id_str] = {
                "date": datetime.now().isoformat(),
                "youtube_id": yt_id,
                "link": link,
                "title": title[:80]
            }
            save_progress(progress)
            return "ok", link
        else:
            progress["failed"][wp_id_str] = {
                "date": datetime.now().isoformat(),
                "youtube_id": yt_id,
                "error": f"HTTP {status_code}"
            }
            save_progress(progress)
            return "fail", f"HTTP {status_code}"
    except Exception as e:
        progress["failed"][wp_id_str] = {
            "date": datetime.now().isoformat(),
            "youtube_id": yt_id,
            "error": str(e)
        }
        save_progress(progress)
        return "error", str(e)


def main():
    parser = argparse.ArgumentParser(description="Batch SEO Injector v1.0")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, don't inject")
    parser.add_argument("--limit", type=int, default=None, help="Override daily limit")
    parser.add_argument("--no-thumb", action="store_true", help="Skip thumbnail upload")
    parser.add_argument("--no-delay", action="store_true", help="No pauses between posts (test mode)")
    parser.add_argument("--start", type=int, default=0, help="Start from N-th file")
    args = parser.parse_args()
    
    # Calculate today's limit
    if args.limit:
        today_limit = args.limit
    else:
        today_limit = DAILY_LIMIT + random.randint(-3, 3)
    
    print("=" * 60)
    print(f"SEO INJECTOR v1.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Limit: {today_limit} | Dry-run: {args.dry_run} | Delay: {not args.no_delay}")
    print("=" * 60)
    
    # Load progress and files
    progress = load_progress()
    seo_files = get_seo_files()
    
    print(f"Available JSON files: {len(seo_files)}")
    print(f"Already injected: {len(progress['injected'])}")
    print(f"Already skipped: {len(progress['skipped'])}")
    print(f"Failed: {len(progress['failed'])}")
    
    # Process
    injected_count = 0
    skipped_count = 0
    
    for i, seo_path in enumerate(seo_files[args.start:], start=args.start):
        if injected_count >= today_limit:
            print(f"\n--- Daily limit reached ({today_limit}) ---")
            break
        
        # Check work hours (skip in no-delay mode)
        if not args.no_delay:
            now = datetime.now()
            if now.hour < WORK_START or now.hour >= WORK_END:
                print(f"\n--- Outside work hours ({WORK_START}:00-{WORK_END}:00) ---")
                break
        
        fname = os.path.basename(seo_path)
        result, detail = inject_single(seo_path, progress, args.dry_run, args.no_thumb)
        
        if result == "ok":
            injected_count += 1
            print(f"  [{injected_count}/{today_limit}] OK: {fname} -> {detail}")
        elif result == "skip_wp":
            skipped_count += 1
            print(f"  [SKIP] Already injected: {fname}")
        elif result == "skip_progress":
            continue  # silent skip
        elif result == "dry_run":
            injected_count += 1
        elif result == "fail" or result == "error":
            print(f"  [FAIL] {fname}: {detail}")
        
        # Natural delay
        if not args.no_delay and not args.dry_run and result == "ok":
            delay = random.uniform(MIN_DELAY_MIN * 60, MAX_DELAY_MIN * 60)
            delay_min = delay / 60
            print(f"    Pauza: {delay_min:.1f} min...")
            time.sleep(delay)
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"PODSUMOWANIE:")
    print(f"  Wstrzyknięte:  {injected_count}")
    print(f"  Pominięte:     {skipped_count}")
    print(f"  Total w bazie: {len(progress['injected'])} injected, {len(progress['skipped'])} skipped")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
