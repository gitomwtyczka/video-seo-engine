#!/usr/bin/env python3
"""
Video prawy-YT wysylka — Batch Pipeline
Uruchamiaj lokalnie na Windows PC gdzie jest Local Runner i pliki video.

Uzycie:
  python batch_vse_pipeline.py --single Gz7WIgjQLuI
  python batch_vse_pipeline.py --batch
  python batch_vse_pipeline.py --list
"""
import argparse
import json
import time
import requests
import hashlib
from pathlib import Path
from datetime import datetime

# === KONFIGURACJA ===
VSE_URL = "https://vse.impresjapr.pl"
API_KEY = "vse_okhVWmFSNhCOeP9YG9HEVGLDOTlXIMiAffsrp7F8SrU"
PORTAL_ID = "2b047d7d-15a1-4d2f-8463-f89c2275bb73"
YT_CHANNEL_ID = "UCoH2G9By4OX3kcLsc8lHgDw"
LOCAL_VIDEO_DIR = r"C:\Users\tomas2\Videos\Prawy"
OUTPUT_DIR = r"C:\VSE\Shorts"
STATE_FILE = Path(__file__).parent / "batch_progress.json"

HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# === LISTA FILMÓW DO PRZETWORZENIA ===
FILMS = [
    {"youtube_id": "Gz7WIgjQLuI", "title": "Plużanski - Frakckowiak Muzeum emisja KIEDY"},
    {"youtube_id": "G8Bmml4Ys_4", "title": "Klimczak Sliwka Ukraina KIEDY"},
    {"youtube_id": "C2w6nnFB9vc", "title": "Klimczak Operator Mobbing I KIEDY"},
    {"youtube_id": "KCLzwiDPIdU", "title": "Klimczak Operator Mobbing II proces sadowy KIEDY"},
    {"youtube_id": "EQAB8t_gZ6M", "title": "Stacey Halwa Wychowanie emisja KIEDY"},
    {"youtube_id": "zXdP34T01R4", "title": "Stacey Halwa Nowacka laczyce ze Sliwka emisja KIEDY"},
]


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def find_local_file(youtube_id: str, title: str) -> str | None:
    """Szuka pliku MP4 w LOCAL_VIDEO_DIR po youtube_id lub fragmencie tytułu."""
    video_dir = Path(LOCAL_VIDEO_DIR)
    if not video_dir.exists():
        return None
    # Po youtube_id w nazwie
    for f in video_dir.glob(f"*{youtube_id}*"):
        if f.suffix.lower() in (".mp4", ".mov", ".mkv"):
            return str(f)
    # Po pierwszych słowach tytułu
    keywords = title.split()[:3]
    for f in video_dir.glob("*.mp4"):
        if all(kw.lower() in f.name.lower() for kw in keywords):
            return str(f)
    return None


def step_generate(youtube_id: str) -> dict:
    """KROK 1: Generuj SEO z YouTube URL."""
    url = f"https://www.youtube.com/watch?v={youtube_id}"
    print(f"  [1/4] Generowanie SEO dla {youtube_id}...")
    resp = requests.post(
        f"{VSE_URL}/v1/generate",
        headers=HEADERS,
        json={
            "video_url": url,
            "llm_provider": "claude",
            "lang": "pl",
            "publication_type": "full_analysis",
            "portal_id": PORTAL_ID,
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


def step_shorts_candidates(youtube_id: str) -> list:
    """KROK 2: Generuj propozycje shortów."""
    print(f"  [2/4] Short candidates dla {youtube_id}...")
    resp = requests.post(
        f"{VSE_URL}/v1/shorts/candidates",
        headers=HEADERS,
        json={
            "youtube_url": f"https://www.youtube.com/watch?v={youtube_id}",
            "youtube_id": youtube_id,
            "count_emotional": 5,
            "count_professional": 5,
            "provider": "claude",
            "portal_id": PORTAL_ID,
        },
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("candidates", [])


def step_render_shorts(youtube_id: str, candidates: list, local_path: str | None):
    """KROK 3: Zlec renderowanie top kandydatów."""
    top = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)[:10]
    print(f"  [3/4] Renderowanie {len(top)} shortów...")
    job_ids = []
    for c in top:
        payload = {
            "youtube_url": f"https://www.youtube.com/watch?v={youtube_id}",
            "youtube_id": youtube_id,
            "start_sec": c["start_sec"],
            "end_sec": c["end_sec"],
            "candidate_data": c,
            "render_format": "9:16",
            "subtitles": "none",
            "output_dir": OUTPUT_DIR,
            "portal_id": PORTAL_ID,
        }
        if local_path:
            payload["local_path"] = local_path
        resp = requests.post(f"{VSE_URL}/v1/shorts/render", headers=HEADERS, json=payload, timeout=30)
        if resp.ok:
            job_ids.append(resp.json().get("job_id"))
        time.sleep(1)
    return job_ids


def step_inject(youtube_id: str, schema_data: dict) -> dict:
    """KROK 4: Wstrzyknij artykuł do prawy.pl jako draft."""
    print(f"  [4/4] Inject do prawy.pl (draft)...")
    resp = requests.post(
        f"{VSE_URL}/v1/inject",
        headers=HEADERS,
        json={
            "video_url": f"https://www.youtube.com/watch?v={youtube_id}",
            "schema_data": schema_data,
            "portal_id": PORTAL_ID,
            "yt_channel_ids": [YT_CHANNEL_ID],
            "post_status": "draft",
            "post_format": "video",
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def process_film(film: dict, state: dict) -> bool:
    youtube_id = film["youtube_id"]
    title = film["title"]

    if state.get(youtube_id, {}).get("status") == "done":
        print(f"[SKIP] {title} — już przetworzony")
        return True

    print(f"\n=== FILM: {title} ({youtube_id}) ===")
    film_state = state.get(youtube_id, {})

    try:
        # KROK 1: Generate
        if not film_state.get("schema_data"):
            result = step_generate(youtube_id)
            film_state["schema_data"] = result.get("schema_data") or result
            state[youtube_id] = film_state
            save_state(state)
        else:
            print("  [1/4] SEO — z checkpointu")

        # KROK 2: Shorts candidates
        if not film_state.get("candidates"):
            candidates = step_shorts_candidates(youtube_id)
            film_state["candidates"] = candidates
            state[youtube_id] = film_state
            save_state(state)
        else:
            candidates = film_state["candidates"]
            print("  [2/4] Candidates — z checkpointu")

        # KROK 3: Render shorts
        if not film_state.get("render_jobs"):
            local_path = find_local_file(youtube_id, title)
            if local_path:
                print(f"  Znaleziono lokalny plik: {local_path}")
            job_ids = step_render_shorts(youtube_id, candidates, local_path)
            film_state["render_jobs"] = job_ids
            state[youtube_id] = film_state
            save_state(state)
        else:
            print("  [3/4] Render — z checkpointu")

        # KROK 4: Inject
        if not film_state.get("wp_post_id"):
            inject_result = step_inject(youtube_id, film_state["schema_data"])
            film_state["wp_post_id"] = inject_result.get("wp_post_id")
            film_state["wp_url"] = inject_result.get("post_url")
            film_state["status"] = "done"
            state[youtube_id] = film_state
            save_state(state)
        else:
            print("  [4/4] Inject — z checkpointu")

        print(f"  OK: prawy.pl draft -> {film_state.get('wp_url')}")
        return True

    except Exception as e:
        print(f"  BLAD: {e}")
        film_state["last_error"] = str(e)
        film_state["status"] = "error"
        state[youtube_id] = film_state
        save_state(state)
        return False


def main():
    parser = argparse.ArgumentParser(description="Video prawy-YT wysylka")
    parser.add_argument("--single", metavar="YOUTUBE_ID", help="Przetworz jeden film")
    parser.add_argument("--batch", action="store_true", help="Przetworz wszystkie filmy z listy")
    parser.add_argument("--list", action="store_true", help="Pokaz liste filmow i status")
    parser.add_argument("--reset", metavar="YOUTUBE_ID", help="Reset checkpointu dla filmu")
    args = parser.parse_args()

    state = load_state()

    if args.list:
        print(f"{'ID':15} {'Status':10} {'WP Post':40} {'Tytuł'}")
        for f in FILMS:
            s = state.get(f["youtube_id"], {})
            print(f"{f['youtube_id']:15} {s.get('status','pending'):10} {str(s.get('wp_url','')):40} {f['title']}")
        return

    if args.reset:
        state.pop(args.reset, None)
        save_state(state)
        print(f"Reset: {args.reset}")
        return

    if args.single:
        film = next((f for f in FILMS if f["youtube_id"] == args.single), None)
        if not film:
            # Pozwala przetworzyć film spoza listy
            film = {"youtube_id": args.single, "title": args.single}
        process_film(film, state)
        return

    if args.batch:
        ok = 0
        for i, film in enumerate(FILMS):
            success = process_film(film, state)
            if success:
                ok += 1
            if i < len(FILMS) - 1:
                print("  Przerwa 20s...")
                time.sleep(20)
        print(f"\nBatch done: {ok}/{len(FILMS)} OK")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
