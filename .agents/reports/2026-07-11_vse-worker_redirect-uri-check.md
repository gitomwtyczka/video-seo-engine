# Raport: Surowe dane REDIRECT_URI z VPS
**Data:** 2026-07-11
**Agent:** vse-worker

## Wynik komendy 1 (.env na VPS)
```
GOOGLE_CLIENT_ID=934133075831-d59kt5ofbih4250us4h53utakm7d2id4.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=[REDACTED]
GOOGLE_REDIRECT_URI=https://vse.impresjapr.pl/api/v1/auth/google/callback
YOUTUBE_API_KEY=[REDACTED]
```

## Wynik komendy 2 (youtube.py na VPS)
```
16:GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
17:GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
19:REDIRECT_URI = os.getenv("YOUTUBE_OAUTH_REDIRECT_URI", "https://vse.impresjapr.pl/v1/youtube/oauth/callback")
33:        f"&client_id={GOOGLE_CLIENT_ID}&redirect_uri={REDIRECT_URI}"
57:            "code": code, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
58:            "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code"
```