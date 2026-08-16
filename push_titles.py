import subprocess
import base64
import json
import sys

def push_file(file_path, repo_path, message):
    print(f"Fetching SHA for {repo_path}...")
    try:
        sha_cmd = ["gh", "api", f"repos/gitomwtyczka/video-seo-engine/contents/{repo_path}"]
        res = subprocess.run(sha_cmd, capture_output=True, text=True, check=True)
        sha = json.loads(res.stdout)["sha"]
    except Exception as e:
        print(f"Error getting sha: {e}")
        return

    with open(file_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "message": message,
        "content": content_b64,
        "sha": sha,
        "branch": "main"
    }
    
    with open("payload.json", "w") as f:
        json.dump(payload, f)

    print(f"Pushing {repo_path}...")
    push_cmd = ["gh", "api", "-X", "PUT", f"repos/gitomwtyczka/video-seo-engine/contents/{repo_path}", "--input", "payload.json"]
    try:
        push_res = subprocess.run(push_cmd, capture_output=True, text=True, check=True)
        print("Success:", json.loads(push_res.stdout).get("commit", {}).get("sha"))
    except subprocess.CalledProcessError as e:
        print("Push error:", e.stderr)

push_file("api/routers/inject.py", "api/routers/inject.py", "hotfix: przekazanie tytułu do YouTube w ścieżce inject [vse-dev]")
push_file("api/routers/youtube.py", "api/routers/youtube.py", "hotfix: poprawka tytułu (fallback) w ścieżce youtube publish [vse-dev]")
