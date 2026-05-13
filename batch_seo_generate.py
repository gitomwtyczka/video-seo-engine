"""
Batch SEO v5.3 Generator — processes ALL matched Prawy TV posts.
Reads from prawy_tv_matches.json, skips already-done, calls Gemini for each.
"""
import re
import json
import sys
import os
import time
import traceback
from datetime import datetime

# Import core functions from test_full_seo_v4.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_full_seo_v4 import (
    parse_vtt_full,
    find_anchor_in_vtt,
    generate_seo_v4,
    format_duration_iso
)

SUBS_DIR = r"D:\Biblioteki\prawy.pl\subs"
OUT_DIR = r"D:\Biblioteki\prawy.pl\seo_results_v5"
MATCHES_FILE = r"D:\Biblioteki\prawy.pl\prawy_tv_matches.json"
ERRORS_LOG = r"D:\Biblioteki\prawy.pl\seo_results_v5\errors.log"
BATCH_REPORT = r"D:\Biblioteki\prawy.pl\seo_results_v5\batch_report.json"

# Already processed YouTube IDs (Batch 1 + 2)
ALREADY_DONE = {
    "fukGxq5aGOo",  # Przewrót Majowy
    "YJWuZs8zpzA",  # Jedwabne
    "8G1-naCE7Mo",  # Loranty
    "01vhWvog9gQ",  # Macierewicz
    "FqinFJiFZeg",  # Czarnek
    "bK2bEhoKu-o",  # Jakubiak
}

# Rate limiting
GEMINI_DELAY = 3  # seconds between Gemini calls
BATCH_SIZE = 25   # posts per batch
BATCH_PAUSE = 10  # seconds pause between batches


def process_single_video(video, api_key, idx, total):
    """Process one video: parse VTT, call Gemini, match anchors, save JSON."""
    vid = video["youtube_id"]
    wp_id = video["wp_id"]
    title = video["post_title"]
    slug = video["slug"]
    
    vtt_path = os.path.join(SUBS_DIR, f"{vid}.pl.vtt")
    out_path = os.path.join(OUT_DIR, f"{vid}.json")
    
    # Skip if already generated
    if os.path.exists(out_path):
        print(f"  [{idx}/{total}] SKIP (already exists): WP#{wp_id} {vid}")
        return "skipped_exists", 0
    
    # Check VTT exists
    if not os.path.exists(vtt_path):
        msg = f"VTT missing: {vid} for WP#{wp_id}"
        print(f"  [{idx}/{total}] ERROR: {msg}")
        return "error_vtt", 0
    
    start_time = time.time()
    print(f"\n  [{idx}/{total}] Processing: WP#{wp_id} | {vid} | {title[:60]}...")
    
    # Parse VTT
    timestamped, segments, duration = parse_vtt_full(vtt_path)
    dur_min = int(duration // 60)
    dur_sec = int(duration % 60)
    print(f"    VTT: {len(segments)} segments | {dur_min}:{dur_sec:02d}")
    
    # Skip very short videos (< 60 seconds of VTT data)
    if duration < 60:
        msg = f"Too short ({dur_min}:{dur_sec:02d}): {vid} WP#{wp_id}"
        print(f"    SKIP: {msg}")
        return "skipped_short", 0
    
    # Generate with Gemini (with retry)
    yt_url = f"https://www.youtube.com/watch?v={vid}"
    result = None
    for attempt in range(2):
        try:
            print(f"    Gemini (attempt {attempt+1})...")
            result = generate_seo_v4(title, timestamped, duration, yt_url, api_key)
            break
        except Exception as e:
            if attempt == 0:
                print(f"    Gemini error: {e} — retrying in 10s...")
                time.sleep(10)
            else:
                msg = f"Gemini failed after 2 attempts: {vid} WP#{wp_id} — {e}"
                print(f"    ERROR: {msg}")
                return "error_gemini", 0
    
    if not result:
        return "error_gemini", 0
    
    # ANCHOR MATCHING — resolve chapters
    resolved_chapters = []
    for ch in result.get("chapters", []):
        anchor = ch.get("anchor_text", "")
        ts = find_anchor_in_vtt(anchor, segments)
        resolved_chapters.append({
            "time": max(0, ts),
            "label": ch["label"],
            "anchor_text": anchor,
            "matched": ts >= 0
        })
    
    resolved_chapters.sort(key=lambda x: x["time"])
    if resolved_chapters and resolved_chapters[0]["time"] != 0:
        resolved_chapters[0]["time"] = 0
    
    result["chapters"] = resolved_chapters
    
    # ANCHOR MATCHING — resolve quotes
    for q in result.get("quotes", []):
        anchor = q.get("anchor_text", q.get("text", "")[:40])
        ts = find_anchor_in_vtt(anchor, segments)
        q["time"] = max(0, ts)
    
    # Add metadata
    result["wp_id"] = wp_id
    result["youtube_id"] = vid
    result["original_title"] = title
    result["slug"] = slug
    result["yt_url"] = yt_url
    result["total_duration"] = int(duration)
    result["duration_seconds"] = int(duration)
    result["duration_iso"] = format_duration_iso(duration)
    
    # Save
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    elapsed = time.time() - start_time
    matched = sum(1 for c in resolved_chapters if c.get("matched"))
    print(f"    OK: {len(resolved_chapters)} chapters ({matched} matched) | {elapsed:.1f}s | {result.get('focus_keyphrase', '?')}")
    
    return "success", elapsed


def main():
    api_key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("Usage: python batch_seo_generate.py YOUR_GEMINI_API_KEY")
        sys.exit(1)
    
    # Optional: start from specific index
    start_from = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    
    os.makedirs(OUT_DIR, exist_ok=True)
    
    # Load matches
    with open(MATCHES_FILE, 'r', encoding='utf-8') as f:
        all_matches = json.load(f)
    
    # Filter out already done
    to_process = [m for m in all_matches if m["youtube_id"] not in ALREADY_DONE]
    total = len(to_process)
    
    print("=" * 70)
    print(f"BATCH SEO v5.3 Generator")
    print(f"Total matches: {len(all_matches)} | Already done: {len(ALREADY_DONE)} | To process: {total}")
    print(f"Starting from index: {start_from}")
    print(f"Gemini delay: {GEMINI_DELAY}s | Batch size: {BATCH_SIZE}")
    print("=" * 70)
    
    # Stats
    stats = {
        "start_time": datetime.now().isoformat(),
        "total_available": total,
        "start_index": start_from,
        "success": 0,
        "skipped_exists": 0,
        "skipped_short": 0,
        "error_vtt": 0,
        "error_gemini": 0,
        "errors": [],
        "times": []
    }
    
    errors_file = open(ERRORS_LOG, 'a', encoding='utf-8')
    
    for i, video in enumerate(to_process[start_from:], start=start_from + 1):
        try:
            status, elapsed = process_single_video(video, api_key, i, total)
            stats[status] = stats.get(status, 0) + 1
            
            if elapsed > 0:
                stats["times"].append(elapsed)
            
            if "error" in status:
                error_msg = f"[{datetime.now().isoformat()}] {status}: WP#{video['wp_id']} {video['youtube_id']} {video['post_title'][:60]}\n"
                errors_file.write(error_msg)
                stats["errors"].append({
                    "wp_id": video["wp_id"],
                    "youtube_id": video["youtube_id"],
                    "status": status
                })
            
            # Rate limiting
            if status == "success":
                time.sleep(GEMINI_DELAY)
            
            # Batch pause
            if i > 0 and i % BATCH_SIZE == 0:
                print(f"\n  --- Batch pause ({BATCH_PAUSE}s) after {i} posts ---\n")
                time.sleep(BATCH_PAUSE)
                
                # Intermediate report
                processed = stats["success"] + stats["skipped_exists"] + stats["skipped_short"]
                failed = stats["error_vtt"] + stats["error_gemini"]
                print(f"  Progress: {processed} ok / {failed} fail / {total} total")
        
        except KeyboardInterrupt:
            print(f"\n\nInterrupted at index {i}. Resume with: python batch_seo_generate.py API_KEY {i}")
            break
        except Exception as e:
            error_msg = f"[{datetime.now().isoformat()}] CRASH: WP#{video['wp_id']} {video['youtube_id']} — {traceback.format_exc()}\n"
            errors_file.write(error_msg)
            stats["errors"].append({
                "wp_id": video["wp_id"],
                "youtube_id": video["youtube_id"],
                "status": "crash",
                "error": str(e)
            })
            print(f"  [{i}/{total}] CRASH: {e}")
            time.sleep(5)
    
    errors_file.close()
    
    # Final stats
    stats["end_time"] = datetime.now().isoformat()
    if stats["times"]:
        stats["time_min"] = round(min(stats["times"]), 1)
        stats["time_avg"] = round(sum(stats["times"]) / len(stats["times"]), 1)
        stats["time_max"] = round(max(stats["times"]), 1)
    
    with open(BATCH_REPORT, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'=' * 70}")
    print(f"BATCH COMPLETE")
    print(f"  Success:  {stats['success']}")
    print(f"  Skipped (exists): {stats['skipped_exists']}")
    print(f"  Skipped (short):  {stats['skipped_short']}")
    print(f"  Errors (VTT):     {stats['error_vtt']}")
    print(f"  Errors (Gemini):  {stats['error_gemini']}")
    if stats["times"]:
        print(f"  Time: min={stats['time_min']}s avg={stats['time_avg']}s max={stats['time_max']}s")
    print(f"  Report: {BATCH_REPORT}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
