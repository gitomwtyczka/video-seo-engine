"""
Inject SEO v5.3 — seekTo + polished quotes + uploadDate + YT thumbnail + interactionStatistic
"""
import json
import os
import re
import requests
from requests.auth import HTTPBasicAuth
from io import BytesIO

WP_URL = "https://prawy.pl"
WP_USER = "prawy_admin"
WP_APP_PASS = "GbXNhj7xMRUxO1nsxDguioUG"
SEO_DIR = r"D:\Biblioteki\prawy.pl\seo_results_v5"

VIDEOS = [
    # Batch 1 (re-inject with Quotation schema + timezone fix)
    {"youtube_id": "fukGxq5aGOo", "wp_id": 119062},
    {"youtube_id": "YJWuZs8zpzA", "wp_id": 118966},
    {"youtube_id": "8G1-naCE7Mo", "wp_id": 16390},
    # Batch 2 (new)
    {"youtube_id": "01vhWvog9gQ", "wp_id": 16318},
    {"youtube_id": "FqinFJiFZeg", "wp_id": 17074},
    {"youtube_id": "bK2bEhoKu-o", "wp_id": 17838},
]

auth = HTTPBasicAuth(WP_USER, WP_APP_PASS)

def strip_html(html):
    return re.sub(r'<[^>]+>', '', html).strip()


# ============================================================
# FETCH POST DATE FROM WP REST API
# ============================================================
def get_post_date(wp_id):
    """Fetch ISO date from WP post."""
    url = f"{WP_URL}/wp-json/wp/v2/posts/{wp_id}"
    resp = requests.get(url, auth=auth, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("date", "2024-01-01T00:00:00")
    return "2024-01-01T00:00:00"


# ============================================================
# FETCH VIEW COUNT FROM YOUTUBE (Data API v3 — needs YT_API_KEY)
# ============================================================
def get_youtube_view_count(yt_id):
    """Fetch view count from YouTube Data API v3.
    Requires YT_API_KEY env var. Returns int or None.
    """
    api_key = os.environ.get("YT_API_KEY", "")
    if not api_key:
        return None
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?id={yt_id}&part=statistics&key={api_key}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            if items:
                return int(items[0]["statistics"].get("viewCount", 0))
    except Exception:
        pass
    return None


# ============================================================
# SET YOUTUBE THUMBNAIL AS FEATURED IMAGE
# ============================================================
def set_youtube_thumbnail(wp_id, yt_id, post_title):
    """Download YT maxres thumbnail and set as WP featured image."""
    # Try maxresdefault first, fallback to hqdefault
    for quality in ["maxresdefault", "hqdefault", "mqdefault"]:
        thumb_url = f"https://img.youtube.com/vi/{yt_id}/{quality}.jpg"
        resp = requests.get(thumb_url, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 5000:
            break
    else:
        print(f"    THUMB: nie udalo sie pobrac")
        return None

    # Upload to WP media library — ASCII-only filename for HTTP headers
    filename = f"prawy-tv-{yt_id}.jpg"

    # Check if thumbnail already uploaded (dedup)
    search_url = f"{WP_URL}/wp-json/wp/v2/media?search=prawy-tv-{yt_id}&per_page=1"
    existing = requests.get(search_url, auth=auth, timeout=10)
    if existing.status_code == 200 and existing.json():
        media_id = existing.json()[0]["id"]
        # Just ensure it's set as featured
        post_url = f"{WP_URL}/wp-json/wp/v2/posts/{wp_id}"
        requests.post(post_url, json={"featured_media": media_id}, auth=auth, timeout=15)
        print(f"    THUMB: reuse (media #{media_id})")
        return media_id

    media_url = f"{WP_URL}/wp-json/wp/v2/media"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "image/jpeg"
    }
    upload_resp = requests.post(
        media_url,
        headers=headers,
        data=resp.content,
        auth=auth,
        timeout=30
    )

    if upload_resp.status_code == 201:
        media_id = upload_resp.json()["id"]
        # Set as featured image
        post_url = f"{WP_URL}/wp-json/wp/v2/posts/{wp_id}"
        set_resp = requests.post(
            post_url,
            json={"featured_media": media_id},
            auth=auth,
            timeout=15
        )
        if set_resp.status_code == 200:
            print(f"    THUMB: OK (media #{media_id})")
            return media_id
    
    print(f"    THUMB: upload failed ({upload_resp.status_code})")
    return None


# ============================================================
# PLAYER JAVASCRIPT
# ============================================================
PLAYER_JS = """<script>
(function(){
  var iframe = document.querySelector('iframe[src*="youtube.com"]');
  if(!iframe) return;
  var src = iframe.src;
  if(src.indexOf('enablejsapi=1') === -1){
    iframe.src = src + (src.indexOf('?')>-1?'&':'?') + 'enablejsapi=1';
  }
  window.prawySeek = function(seconds){
    iframe.contentWindow.postMessage(JSON.stringify({
      event:'command', func:'seekTo', args:[seconds, true]
    }), '*');
    iframe.contentWindow.postMessage(JSON.stringify({
      event:'command', func:'playVideo', args:[]
    }), '*');
    iframe.scrollIntoView({behavior:'smooth', block:'center'});
  };
  document.querySelectorAll('.prawy-chapter').forEach(function(el){
    el.addEventListener('click', function(e){
      e.preventDefault();
      var t = parseInt(this.getAttribute('data-time'));
      window.prawySeek(t);
    });
  });
})();
</script>"""


# ============================================================
# SCHEMA JSON-LD — VideoObject + Clip + FAQPage
# ============================================================
def build_schema_jsonld(seo, yt_id, upload_date):
    chapters = seo.get("chapters", [])
    total_dur = seo.get("total_duration", 0)
    yt_url = seo.get("yt_url", "")
    
    dur_h = total_dur // 3600
    dur_m = (total_dur % 3600) // 60
    dur_s = total_dur % 60
    iso_dur = f"PT{dur_h}H{dur_m}M{dur_s}S" if dur_h else f"PT{dur_m}M{dur_s}S"
    
    clips = []
    for i, ch in enumerate(chapters):
        end_time = chapters[i+1]["time"] if i+1 < len(chapters) else total_dur
        clips.append({
            "@type": "Clip",
            "name": ch["label"],
            "startOffset": ch["time"],
            "endOffset": end_time,
            "url": f"{yt_url}&t={ch['time']}s"
        })
    
    video_schema = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": seo.get("seo_title", ""),
        "description": seo.get("video_description", ""),
        "thumbnailUrl": f"https://img.youtube.com/vi/{yt_id}/maxresdefault.jpg",
        "uploadDate": upload_date + "+00:00" if "T" in upload_date and "+" not in upload_date else upload_date,
        "contentUrl": yt_url,
        "embedUrl": f"https://www.youtube.com/embed/{yt_id}",
        "duration": iso_dur,
        "hasPart": clips
    }
    
    # Add interactionStatistic if view count available
    view_count = seo.get("view_count") or get_youtube_view_count(yt_id)
    if view_count:
        video_schema["interactionStatistic"] = {
            "@type": "InteractionCounter",
            "interactionType": "http://schema.org/WatchAction",
            "userInteractionCount": int(view_count)
        }
    
    # FAQPage
    faq_items = []
    for faq in seo.get("faq", []):
        faq_items.append({
            "@type": "Question",
            "name": faq["question"],
            "acceptedAnswer": {"@type": "Answer", "text": faq["answer"]}
        })
    
    schemas = [video_schema]
    if faq_items:
        schemas.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_items
        })
    
    # Quotation schema for each polished quote
    for q in seo.get("quotes", []):
        t = q.get("time", 0)
        schemas.append({
            "@context": "https://schema.org",
            "@type": "Quotation",
            "text": q["text"],
            "creator": {
                "@type": "Person",
                "name": q["speaker"]
            },
            "citation": f"{yt_url}&t={int(t)}s"
        })
    
    return schemas


# ============================================================
# BUILD POST CONTENT
# ============================================================
def build_post_content(seo, yt_id, upload_date):
    lead_html = seo["lead"]
    article_body = seo["article_body"]
    chapters = seo.get("chapters", [])
    quotes = seo.get("quotes", [])
    faq = seo.get("faq", [])
    yt_url = seo.get("yt_url", "")
    
    # Lead
    lead_block = f"""<!-- wp:paragraph -->
<p>{lead_html}</p>
<!-- /wp:paragraph -->

<!-- wp:more -->
<!--more-->
<!-- /wp:more -->"""

    # YouTube embed
    embed_json = json.dumps({"url": yt_url, "type": "video", "providerNameSlug": "youtube", "responsive": True, "className": "wp-embed-aspect-16-9 wp-has-aspect-ratio"})
    embed_block = f"""<!-- wp:embed {embed_json} -->
<figure class="wp-block-embed is-type-video is-provider-youtube wp-block-embed-youtube wp-embed-aspect-16-9 wp-has-aspect-ratio"><div class="wp-block-embed__wrapper">
{yt_url}
</div></figure>
<!-- /wp:embed -->"""

    # Clickable chapters — in-page seekTo
    ch_items = []
    for ch in chapters:
        t = ch["time"]
        m = int(t // 60); s = int(t % 60)
        ts = f"{m:02d}:{s:02d}"
        ch_items.append(
            f'<li><a href="#" class="prawy-chapter" data-time="{int(t)}">'
            f'<strong>{ts}</strong> \u2014 {ch["label"]}</a></li>'
        )
    chapters_block = f"""<!-- wp:heading -->
<h2 class="wp-block-heading">Rozdzia\u0142y nagrania</h2>
<!-- /wp:heading -->

<!-- wp:list -->
<ul class="prawy-chapters-list">
{chr(10).join(ch_items)}
</ul>
<!-- /wp:list -->""" if ch_items else ""

    # Article body
    article_block = f"""<!-- wp:html -->
{article_body}
<!-- /wp:html -->"""

    # Polished quotes with seekTo
    quotes_blocks = []
    for q in quotes:
        t = q.get("time", 0)
        m = int(t // 60); s = int(t % 60)
        ts = f"{m:02d}:{s:02d}"
        quotes_blocks.append(
            f'<!-- wp:quote -->\n'
            f'<blockquote class="wp-block-quote"><p>{q["text"]}</p>'
            f'<cite>\u2014 {q["speaker"]} '
            f'(<a href="#" class="prawy-chapter" data-time="{int(t)}">{ts}</a>)'
            f'</cite></blockquote>\n'
            f'<!-- /wp:quote -->'
        )
    quotes_section = ""
    if quotes_blocks:
        quotes_section = f"""<!-- wp:heading -->
<h2 class="wp-block-heading">Kluczowe cytaty</h2>
<!-- /wp:heading -->

{chr(10).join(quotes_blocks)}"""

    # FAQ (collapsible)
    faq_blocks = []
    for f in faq:
        faq_blocks.append(
            f'<details><summary><strong>{f["question"]}</strong></summary>'
            f'<p>{f["answer"]}</p></details>'
        )
    faq_section = ""
    if faq_blocks:
        faq_section = f"""<!-- wp:heading -->
<h2 class="wp-block-heading">Najcz\u0119\u015bciej zadawane pytania</h2>
<!-- /wp:heading -->

<!-- wp:html -->
{chr(10).join(faq_blocks)}
<!-- /wp:html -->"""

    # Schema JSON-LD
    schemas = build_schema_jsonld(seo, yt_id, upload_date)
    schema_block = ""
    for s in schemas:
        schema_json = json.dumps(s, ensure_ascii=False, indent=2)
        schema_block += f"""\n<!-- wp:html -->
<script type="application/ld+json">
{schema_json}
</script>
<!-- /wp:html -->"""

    # Player JS
    js_block = f"""<!-- wp:html -->
{PLAYER_JS}
<!-- /wp:html -->"""

    return (
        f"{lead_block}\n\n{embed_block}\n\n{chapters_block}\n\n"
        f"{article_block}\n\n{quotes_section}\n\n{faq_section}\n\n"
        f"{schema_block}\n\n{js_block}"
    )


# ============================================================
# UPDATE POST
# ============================================================
def update_post(wp_id, seo, yt_id):
    # Fetch real uploadDate from WP
    upload_date = get_post_date(wp_id)
    print(f"  uploadDate: {upload_date}")
    
    content = build_post_content(seo, yt_id, upload_date)
    excerpt = strip_html(seo["lead"])
    
    url = f"{WP_URL}/wp-json/wp/v2/posts/{wp_id}"
    data = {"content": content, "excerpt": excerpt}
    
    resp = requests.post(url, json=data, auth=auth, timeout=30)
    return resp.status_code, resp.json().get("link", "?")


if __name__ == '__main__':
    print("=" * 60)
    print("SEO v5 -- polished quotes + uploadDate + YT thumbnail")
    print("=" * 60)
    
    for v in VIDEOS:
        vid = v["youtube_id"]
        wp_id = v["wp_id"]
        seo_path = os.path.join(SEO_DIR, f"{vid}.json")
        
        if not os.path.exists(seo_path):
            print(f"\n[WP#{wp_id}] BRAK: {seo_path}")
            continue
        
        with open(seo_path, 'r', encoding='utf-8') as f:
            seo = json.load(f)
        
        print(f"\n[WP#{wp_id}] {seo['original_title']}")
        
        # Set YouTube thumbnail as featured image
        set_youtube_thumbnail(wp_id, vid, seo['original_title'])
        
        # Inject content
        status, link = update_post(wp_id, seo, vid)
        print(f"  REST API: {status} | {link}")
        print(f"  {'OK' if status == 200 else 'FAIL'}")
    
    print(f"\n{'='*60}")
    print("LINKI:")
    print("  1. https://prawy.pl/dr-krzysztof-kawecki-i-tadeusz-pluzanski-na-zywo/")
    print("  2. https://prawy.pl/wojciech-sumlinski-i-anna-klimczak-jedwabne-prawda-czy-falsz-wideo/")
    print("  3. https://prawy.pl/132064-dariusz-loranty-spowiedz-psa-na-zywo/")
    print(f"{'='*60}")
