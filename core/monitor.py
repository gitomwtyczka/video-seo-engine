"""YouTube Channel Monitor — detect new videos and trigger pipeline (Phase 2).

NEW module — not yet implemented. Planned for Phase 2.

Responsibilities:
  - Poll YouTube channel for new videos (via yt-dlp, no API key)
  - Compare against last-seen video ID registry
  - On new video detected: trigger fetcher → generator → injector pipeline
  - Create WordPress draft post automatically
  - Send notification (Discord webhook / email)

Design decisions:
  - Polling interval: configurable (default 15 min)
  - State persistence: JSON file (last_seen_video_id.json)
  - No YouTube API key required (yt-dlp channel scraping)
  - Optional: YouTube Data API v3 for richer metadata

Dependencies:
  pip install yt-dlp schedule python-dotenv
"""

# TODO: implement in Phase 2
raise NotImplementedError("monitor.py — Phase 2 feature, not yet implemented.")
