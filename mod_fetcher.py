import urllib.request
import json
import base64

url = 'https://api.github.com/repos/gitomwtyczka/video-seo-engine/contents/core/fetcher.py?ref=main'
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read())
    content = base64.b64decode(data['content']).decode('utf-8')
    sha = data['sha']

# modify fetcher.py
content = content.replace(
    'def fetch_metadata_api_v3(video_id: str, api_key: str) -> dict:',
    'def fetch_metadata_api_v3(video_id: str, api_key: str, access_token: str | None = None) -> dict:'
)

old_url_code = """    url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?id={video_id}&key={api_key}"
        f"&part=snippet,contentDetails,statistics"
    )
    try:
        req = urllib.request.Request(url)  # noqa: S310"""

new_url_code = """    url = f"https://www.googleapis.com/youtube/v3/videos"
    import urllib.parse
    params = {"id": video_id, "part": "snippet,contentDetails,statistics"}
    headers = {}
    
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    else:
        params["key"] = api_key
        
    query_string = urllib.parse.urlencode(params)
    url = f"{url}?{query_string}"
    
    try:
        req = urllib.request.Request(url, headers=headers)  # noqa: S310"""

content = content.replace(old_url_code, new_url_code)

content = content.replace(
    'def process_video(video_id: str, output_dir: str, lang: str = "pl") -> dict:',
    'def process_video(video_id: str, output_dir: str, lang: str = "pl", access_token: str | None = None) -> dict:'
)

content = content.replace(
    '        meta = fetch_metadata_api_v3(video_id, api_key)',
    '        meta = fetch_metadata_api_v3(video_id, api_key, access_token)'
)

with open('fetcher_new.py', 'w', encoding='utf-8') as f:
    f.write(content)
with open('fetcher_sha.txt', 'w', encoding='utf-8') as f:
    f.write(sha)
print('Fetcher modified')
