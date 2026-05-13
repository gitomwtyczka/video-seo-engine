"""Match Prawy TV WordPress posts to available VTT subtitle files."""
import requests, os, re, json
from requests.auth import HTTPBasicAuth

WP_URL = "https://prawy.pl"
auth = HTTPBasicAuth("prawy_admin", "GbXNhj7xMRUxO1nsxDguioUG")
SUBS_DIR = r"D:\Biblioteki\prawy.pl\subs"
DONE = {"fukGxq5aGOo", "YJWuZs8zpzA", "8G1-naCE7Mo", "01vhWvog9gQ", "FqinFJiFZeg", "bK2bEhoKu-o"}

# Get VTT IDs
vtt_ids = set()
for f in os.listdir(SUBS_DIR):
    if f.endswith('.pl.vtt'):
        vtt_ids.add(f.replace('.pl.vtt', ''))

print(f"VTT files: {len(vtt_ids)}, done: {len(DONE)}, available: {len(vtt_ids - DONE)}")

# Fetch Prawy TV posts (category 2472)
matches = []
page = 1
while True:
    url = f"{WP_URL}/wp-json/wp/v2/posts?categories=2472&per_page=50&page={page}&_fields=id,title,slug,content"
    resp = requests.get(url, auth=auth, timeout=30)
    if resp.status_code != 200:
        break
    posts = resp.json()
    if not posts:
        break
    
    for p in posts:
        content = p.get("content", {}).get("rendered", "")
        # Extract YouTube IDs from content
        yt_matches = re.findall(r'youtube\.com/(?:watch\?v=|embed/)([a-zA-Z0-9_-]{11})', content)
        for yt_id in yt_matches:
            if yt_id in vtt_ids and yt_id not in DONE:
                title = p["title"]["rendered"]
                matches.append({
                    "wp_id": p["id"],
                    "youtube_id": yt_id,
                    "post_title": title,
                    "slug": p["slug"]
                })
                DONE.add(yt_id)  # prevent duplicates
    
    page += 1
    if page > 20:
        break

print(f"\nFound {len(matches)} Prawy TV posts with VTT subtitles:")
for i, m in enumerate(matches):
    vtt_size = os.path.getsize(os.path.join(SUBS_DIR, f"{m['youtube_id']}.pl.vtt"))
    duration_est = vtt_size // 130  # rough estimate: ~130 bytes per second of VTT
    print(f"  {i+1}. WP#{m['wp_id']} | {m['youtube_id']} | ~{duration_est//60}min | {m['post_title'][:70]}")

# Save for use
with open(r"D:\Biblioteki\prawy.pl\prawy_tv_matches.json", 'w', encoding='utf-8') as f:
    json.dump(matches, f, ensure_ascii=False, indent=2)
print(f"\nSaved to prawy_tv_matches.json")
