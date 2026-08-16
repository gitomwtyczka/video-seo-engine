import urllib.request
import json
import base64

url = 'https://api.github.com/repos/gitomwtyczka/video-seo-engine/contents/api/services/pipeline.py?ref=main'
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read())
    content = base64.b64decode(data['content']).decode('utf-8')
    sha = data['sha']

# modify pipeline.py

# 1. signature
content = content.replace(
    'async def run_generate(\n    video_url: str,\n    llm_provider: str,\n    lang: str,\n    post_title_override: Optional[str] = None,\n    publication_type: str = "full_analysis",\n    portal_id: Optional[str] = None,\n) -> dict:',
    'async def run_generate(\n    video_url: str,\n    llm_provider: str,\n    lang: str,\n    post_title_override: Optional[str] = None,\n    publication_type: str = "full_analysis",\n    portal_id: Optional[str] = None,\n    user_id: Optional[str] = None,\n) -> dict:'
)

# 2. Add OAuth access_token retrieval logic
new_oauth_logic = """
    access_token = None
    if user_id:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from api.models.youtube_channel import YouTubeChannel
            try:
                uid = uuid.UUID(user_id)
                result = await db.execute(
                    select(YouTubeChannel)
                    .where(YouTubeChannel.user_id == uid)
                    .where(YouTubeChannel.is_active == True)
                    .limit(1)
                )
                channel = result.scalar_one_or_none()
                if channel:
                    if hasattr(channel, 'access_token') and getattr(channel, 'access_token'):
                        access_token = channel.access_token
                    elif channel.refresh_token:
                        import requests
                        client_id = os.environ.get("GOOGLE_CLIENT_ID", "") or os.environ.get("YT_CLIENT_ID", "")
                        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "") or os.environ.get("YT_CLIENT_SECRET", "")
                        if client_id and client_secret:
                            resp = requests.post(
                                "https://oauth2.googleapis.com/token",
                                data={
                                    "client_id": client_id,
                                    "client_secret": client_secret,
                                    "refresh_token": channel.refresh_token,
                                    "grant_type": "refresh_token",
                                },
                                timeout=15,
                            )
                            if resp.status_code == 200:
                                access_token = resp.json().get("access_token")
                                logger.info("[generate] Got access_token from refresh_token")
                            else:
                                logger.warning("[generate] Failed to get access_token: %s", resp.text)
                        else:
                            logger.warning("[generate] Missing OAuth client credentials")
            except Exception as exc:
                logger.warning("[generate] Error getting channel access_token: %s", exc)

    with tempfile.TemporaryDirectory() as tmp_dir:"""

content = content.replace('    with tempfile.TemporaryDirectory() as tmp_dir:', new_oauth_logic)

content = content.replace(
    '        meta = await asyncio.to_thread(fetch_video, video_id, tmp_dir, lang)',
    '        meta = await asyncio.to_thread(fetch_video, video_id, tmp_dir, lang, access_token)'
)

with open('pipeline_new.py', 'w', encoding='utf-8') as f:
    f.write(content)
with open('pipeline_sha.txt', 'w', encoding='utf-8') as f:
    f.write(sha)
print('Pipeline modified')
