"""AI Schema Generator — VideoObject, Clip (chapters), FAQPage via Gemini API.

TODO: Migrate from shadow-perihelion (test_full_seo_v4.py / generate_seo_v5.py).
User will provide these files in a separate dispatch once uploaded to repo.

Responsibilities:
  - Parse VTT transcript into chapters and FAQ candidates
  - Call Gemini API to generate SEO-optimized titles, descriptions, FAQ
  - Build complete JSON-LD schema:
    * VideoObject (name, description, duration, uploadDate, thumbnailUrl,
                   contentUrl, embedUrl, interactionStatistic)
    * Clip list with startOffset/endOffset/SeekToAction
    * FAQPage with Q&A pairs from transcript
  - Return schema dict ready for injector.py

Schema standards (Google 2026):
  - duration: ISO 8601 (PT#H#M#S)
  - uploadDate: ISO 8601 with timezone (e.g. 2026-01-15T10:00:00+01:00)
  - interactionStatistic: WatchAction + userInteractionCount (from YouTube)
  - SeekToAction: added for completeness (not rendered for PL content)
  - Quotation: NOT added (Google does not render; keep if existing)

Dependencies:
  pip install google-generativeai python-dotenv
"""

# TODO: implement after migration from shadow-perihelion
raise NotImplementedError(
    "generator.py — pending migration from shadow-perihelion. "
    "See DISPATCH-VSE-MIGRATE-GENERATOR for next steps."
)
