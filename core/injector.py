"""WordPress REST API Injector — write JSON-LD schema to post content.

TODO: Migrate from shadow-perihelion (inject_rest_v5.py).
User will provide this file in a separate dispatch once uploaded to repo.

Responsibilities:
  - Fetch current post content via WP REST API
  - Inject or update <script type='application/ld+json'> block
  - Atomic update: rollback on failure (preserve original on error)
  - Support dry-run mode (--dry-run flag)
  - Log injection result (post ID, schema types injected, response status)

Safety rules:
  - NEVER overwrite post content outside the JSON-LD script block
  - NEVER commit credentials to repo
  - Always verify WP REST API response (check 200/201, not just no exception)

Dependencies:
  pip install requests python-dotenv
"""

# TODO: implement after migration from shadow-perihelion
raise NotImplementedError(
    "injector.py — pending migration from shadow-perihelion. "
    "See DISPATCH-VSE-MIGRATE-INJECTOR for next steps."
)
