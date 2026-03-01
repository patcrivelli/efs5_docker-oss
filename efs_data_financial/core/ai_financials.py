# efs_data/ai_financials.py
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# 🚨 Hardcoded API key (TEMP — do not use in production)
_GEMINI_API_KEY = "AIzaSyC0XC_LDLVUEP3S_fX7cKjaQEkIylYOC6s"


def _get_api_key() -> str:
    """Return the hardcoded Gemini API key (overrides env/settings)."""
    return _GEMINI_API_KEY


def is_enabled() -> bool:
    """Check if Gemini API is enabled (always true if key exists)."""
    return bool(_get_api_key())


def ai_normalize_statement(raw_json: dict, kind: str) -> dict:
    """
    Normalize raw financial JSON into canonical schema using Gemini.
    Falls back to raw_json if Gemini is disabled or parsing fails.
    """
    if not is_enabled():
        return raw_json

    try:
        import google.generativeai as genai  # pip install google-generativeai

        genai.configure(api_key=_get_api_key())
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
You are given a {kind} JSON export that may be irregular.
Return a canonical JSON with this exact schema:

{{
  "sections":[
    {{
      "title": "REVENUE",
      "lines":[{{"name":"Circulation Retail","value":113854}}, ...]
    }},
    ...
  ]
}}

Rules:
- Section titles MUST be uppercase (REVENUE, DIRECT COSTS, OVERHEADS, EBITDA, etc).
- Do NOT invent numbers or categories.
- Convert currency strings like "(37,880)" into negative integers: -37880.
- Exclude meta rows like "Year number", "Status", "Financial year".
- If no sections exist, put everything under "__UNGROUPED__".
- Output must be valid JSON only (no commentary).
"""

        resp = model.generate_content(
            [prompt, str(raw_json)],
            safety_settings={
                "HARASSMENT": "block_none",
                "HATE_SPEECH": "block_none",
                "SEXUAL": "block_none",
                "DANGEROUS": "block_none",
            },
        )

        text = (resp.text or "").strip()
        return json.loads(text)

    except Exception as e:
        logger.warning("Gemini normalization failed: %s", e)
        return raw_json
