"""
Social Media Snippets Generator — endpoint VSE.

CO: Generuje posty social media na podstawie wygenerowanego SEO.
PO CO: Użytkownik po wygenerowaniu SEO może od razu dostać gotowe posty
       na X/Twitter, LinkedIn, Facebook, Instagram.
JAK: LLM dostaje focus_keyphrase + article_body + tytuł i generuje 4 posty.
"""
import logging
import os
import json
import re

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from core.generator import _call_llm, _sanitize_llm_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/socials", tags=["socials"])


SOCIAL_PROMPT = """
Jesteś specjalistą od social media. Na podstawie artykułu wygeneruj posty na 4 platformy.

TYTUŁ: {title}
FRAZA KLUCZOWA: {keyphrase}
ARTYKUŁ (fragment): {article_body_short}

ZASADY KAŻDEGO POSTU:
- Twitter/X: max 280 zn, mocny hook, 2 hashtagi
- LinkedIn: 800-1200 zn, profesjonalny, akapit + punkty + CTA
- Facebook: 400-600 zn, emotki, pytanie do angażowania
- Instagram: 150-200 zn caption + 5 hashtagów

Odpowiedź TYLKO JSON:
{{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "..."}}
"""


class SocialsRequest(BaseModel):
    title: str
    focus_keyphrase: str
    article_body: str = ""
    provider: str = "gemini"


@router.post("/generate")
def generate_social_posts(req: SocialsRequest):
    """Generuje posty social media na podstawie artykułu VSE."""
    api_key = os.getenv("GEMINI_API_KEY", "") if req.provider == "gemini" else os.getenv("ANTHROPIC_API_KEY", "")
    
    article_short = req.article_body[:2000] if req.article_body else ""
    # Usuń HTML tagi dla promptu
    article_short = re.sub(r"<[^>]+>", " ", article_short).strip()
    
    prompt = SOCIAL_PROMPT.format(
        title=req.title,
        keyphrase=req.focus_keyphrase,
        article_body_short=article_short,
    )
    
    raw = _call_llm(prompt, api_key, req.provider)
    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = _sanitize_llm_json(raw)
    
    posts = json.loads(raw)
    logger.info("[socials] generated for: %s", req.title[:60])
    return {"posts": posts}
