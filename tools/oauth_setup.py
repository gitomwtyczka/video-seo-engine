#!/usr/bin/env python3
"""OAuth Setup Utility — generate YouTube Data API v3 refresh_token.

CO: Interaktywny skrypt do generowania OAuth refresh_token dla YouTube API.

PO CO: Dodanie nowego kanału YouTube wymaga refresh_token OAuth 2.0.
       Ten skrypt prowadzi użytkownika przez proces autoryzacji:
       1. Otwiera URL autoryzacji w przeglądarce
       2. Użytkownik loguje się kontem Google i zezwala na dostęp
       3. Skrypt otrzymuje authorization code i wymienia na token
       4. Wyświetla refresh_token do wklejenia do channels/*.yaml

JAK: Uruchom z client_id i client_secret (z args lub env):
       python tools/oauth_setup.py --client-id=XXX --client-secret=YYY
     Lub ustaw zmienne środowiskowe:
       YT_CLIENT_ID=XXX YT_CLIENT_SECRET=YYY python tools/oauth_setup.py

     Skrypt używa localhost:8080 redirect URI (standardowy for "Desktop" OAuth app).

Wymagania:
  - OAuth 2.0 Client ID typu "Desktop" z Google Cloud Console
  - Scope: https://www.googleapis.com/auth/youtube

Utworzono: 2026-06-20 | vse-dev-21 | D6b.8
"""
import argparse
import http.server
import json
import os
import sys
import threading
import urllib.parse
import webbrowser
from typing import Optional

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install: pip install requests")
    sys.exit(1)


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "http://localhost:8080"
SCOPE = "https://www.googleapis.com/auth/youtube"


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="YouTube OAuth Setup — generate refresh_token for channels/*.yaml"
    )
    parser.add_argument(
        "--client-id",
        default=os.environ.get("YT_CLIENT_ID", ""),
        help="Google OAuth Client ID (or set YT_CLIENT_ID env var)",
    )
    parser.add_argument(
        "--client-secret",
        default=os.environ.get("YT_CLIENT_SECRET", ""),
        help="Google OAuth Client Secret (or set YT_CLIENT_SECRET env var)",
    )
    return parser.parse_args()


def _get_auth_code(client_id: str) -> str:
    """Open browser for Google OAuth consent and capture authorization code.

    Starts a minimal HTTP server on localhost:8080 to receive the redirect.

    Args:
        client_id: Google OAuth Client ID.

    Returns:
        Authorization code string.
    """
    auth_code: Optional[str] = None
    error: Optional[str] = None

    class OAuthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code, error
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

            if "code" in params:
                auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>\xe2\x9c\x85 Authorization successful!</h1>"
                    b"<p>You can close this tab and return to the terminal.</p></body></html>"
                )
            elif "error" in params:
                error = params["error"][0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    f"<html><body><h1>\u274c Error: {error}</h1></body></html>".encode()
                )
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress server logs

    # Build authorization URL
    auth_params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",  # Force refresh_token generation
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    print("\n\ud83d\udd11 Opening browser for Google OAuth consent...")
    print(f"\n   URL: {auth_url}\n")

    # Start local server
    server = http.server.HTTPServer(("localhost", 8080), OAuthHandler)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.start()

    # Open browser
    webbrowser.open(auth_url)

    print("\u23f3 Waiting for authorization callback on localhost:8080...")
    server_thread.join(timeout=120)
    server.server_close()

    if error:
        print(f"\n\u274c Authorization error: {error}")
        sys.exit(1)

    if not auth_code:
        print("\n\u274c Timeout: no authorization callback received within 120s")
        sys.exit(1)

    return auth_code


def _exchange_code(client_id: str, client_secret: str, auth_code: str) -> dict:
    """Exchange authorization code for access + refresh tokens.

    Args:
        client_id: Google OAuth Client ID.
        client_secret: Google OAuth Client Secret.
        auth_code: Authorization code from consent flow.

    Returns:
        Token response dict with 'access_token', 'refresh_token', etc.
    """
    resp = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )

    if resp.status_code != 200:
        print(f"\n\u274c Token exchange failed: HTTP {resp.status_code}")
        print(resp.text)
        sys.exit(1)

    return resp.json()


def main() -> None:
    """Main OAuth setup flow."""
    args = _parse_args()

    if not args.client_id or not args.client_secret:
        print("\u274c ERROR: --client-id and --client-secret required")
        print("  Set YT_CLIENT_ID and YT_CLIENT_SECRET env vars, or pass as args.")
        sys.exit(1)

    print("\n\u2550" * 60)
    print("  \ud83d\udcfa YouTube OAuth Setup \u2014 Video SEO Engine")
    print("\u2550" * 60)

    auth_code = _get_auth_code(args.client_id)
    print(f"\n\u2705 Authorization code received: {auth_code[:20]}...")

    tokens = _exchange_code(args.client_id, args.client_secret, auth_code)
    refresh_token = tokens.get("refresh_token", "")
    access_token = tokens.get("access_token", "")

    if not refresh_token:
        print("\n\u26a0\ufe0f  WARNING: No refresh_token received!")
        print("   This usually means the app was already authorized.")
        print("   Revoke access at https://myaccount.google.com/permissions")
        print("   then run this script again.")
        sys.exit(1)

    print("\n" + "\u2550" * 60)
    print("  \u2705 SUCCESS \u2014 OAuth tokens generated")
    print("\u2550" * 60)
    print(f"\n  Refresh Token: {refresh_token}")
    print(f"  Access Token:  {access_token[:30]}... (expires in {tokens.get('expires_in', '?')}s)")
    print("\n\u2550" * 60)
    print("  \ud83d\udcdd Add to your .env file:")
    print(f"     YT_REFRESH_TOKEN={refresh_token}")
    print("\n  Or add to channels/<channel_id>.yaml:")
    print(f"     yt_oauth:")
    print(f"       refresh_token: \"${{YT_REFRESH_TOKEN}}\"")
    print("\u2550" * 60 + "\n")


if __name__ == "__main__":
    main()
