# Raport diagnostyczny: 401 Unauthorized

**Zebrane: 2026-07-11**  
**Agent:** vse-worker

Poniżej wynik wykonania skryptu diagnostycznego z VPS na podstawie dyspozycji 401:

```text
=== 1. Backend logi ===
2026-07-11 10:00:36,726 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:37182 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:00:47,308 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:45802 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:00:57,874 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:37100 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:01:08,450 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:56900 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:01:19,034 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:36544 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:01:29,589 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:60488 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:01:40,163 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:60590 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:01:50,730 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:45100 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:02:01,304 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:39980 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:02:11,866 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:45654 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:02:22,436 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:35068 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:02:32,991 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:33800 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:02:43,542 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:50168 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:02:54,092 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:42048 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:03:04,652 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:36982 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:03:15,222 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:47070 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:03:25,833 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:46616 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:03:36,410 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:58614 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:03:46,962 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:37672 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:03:57,523 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:43368 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:04:08,082 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:48786 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:04:18,652 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:45502 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:04:29,239 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:46460 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:04:39,789 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:45176 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:04:50,354 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:49928 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:05:00,942 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:44548 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:05:11,524 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:35110 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:05:22,093 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:42162 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:05:32,644 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:58766 - "GET /v1/jobs/pending HTTP/1.0" 200 OK
2026-07-11 10:05:43,232 [INFO] api.routers.jobs: [jobs] /pending: 0 jobs returned for runner
INFO:     172.27.0.1:60588 - "GET /v1/jobs/pending HTTP/1.0" 200 OK

=== 2. Portale w bazie ===
 id | name | url | user_id 
----+------+-----+---------
(0 rows)

=== 3. Joby w bazie ===
ERROR:  relation "jobs" does not exist
LINE 1: SELECT id, user_id, created_at, status FROM jobs ORDER BY cr...
                                                    ^

=== 4. refreshAccessToken ===
(brak)

=== 5. NEXTAUTH env vars ===
NEXTAUTH_SECRET=9264f609a7ed2d330ac49b4d358fd7765a34e00f3268e7cc0b1bdd5e97b89381812881735d1e1c6f

=== 6. Auth refresh endpoint ===
2:Auth router: register, login, token refresh, Google OAuth.
19:    create_access_token, create_refresh_token,
50:    refresh_token: str
55:    refresh_token: str
91:    await db.refresh(user)
200:        refresh_token=create_refresh_token(str(user.id))
204:@router.post("/refresh", response_model=TokenResponse)
205:async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
206:    """Exchange a valid refresh token for a new JWT pair."""
209:        detail="Invalid refresh token"
212:        data = jwt.decode(payload.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
214:        if not user_id or data.get("type") != "refresh":
226:        refresh_token=create_refresh_token(str(user.id))
294:    await db.refresh(user)
298:        refresh_token=create_refresh_token(str(user.id))
365:    await db.refresh(user)
368:    refresh_token = create_refresh_token(str(user.id))
372:        f"{frontend_url}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"

=== 7. Tabele w bazie ===
             List of relations
 Schema |       Name       | Type  | Owner 
--------+------------------+-------+-------
 public | api_keys         | table | vse
 public | app_settings     | table | vse
 public | oauth_states     | table | vse
 public | plans            | table | vse
 public | transcript_jobs  | table | vse
 public | usage_logs       | table | vse
 public | users            | table | vse
 public | wp_portals       | table | vse
 public | youtube_channels | table | vse
(9 rows)
```
