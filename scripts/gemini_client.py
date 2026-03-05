"""
Shared Gemini Client Helper
============================
Centralizes Gemini API client initialization, retry logic, JSON parsing,
and token tracking for all pipeline scripts.

VERSION: 1.0 — Phase B Gemini migration
"""

import json
import logging
import re
import time

from google import genai
from google.genai import types

from config import CONFIG

# Singleton client — initialized once, reused across all calls
_client = None


def get_client():
    """Return the singleton Gemini client, creating it on first call."""
    global _client
    if _client is None:
        api_key = CONFIG["GEMINI_API_KEY"]
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not configured in Secret Manager")
        _client = genai.Client(api_key=api_key)
    return _client


def call_gemini(
    prompt: str,
    *,
    model: str = None,
    max_output_tokens: int = 4000,
    temperature: float = 0.0,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> dict:
    """
    Call Gemini API with retry logic and structured response parsing.

    INPUT:
        - prompt: The prompt text to send
        - model: Gemini model name (defaults to CONFIG['GEMINI_MODEL'])
        - max_output_tokens: Maximum output tokens
        - temperature: Sampling temperature (0.0 for reproducibility)
        - max_retries: Number of retry attempts for JSON parse errors
        - retry_delay: Base delay between retries (seconds)
    OUTPUT: dict with keys:
        - 'text': raw response text
        - 'data': parsed JSON (or None if not JSON)
        - 'tokens_in': prompt token count
        - 'tokens_out': candidate token count
        - 'model': model name used
    """
    if model is None:
        model = CONFIG["GEMINI_MODEL"]

    client = get_client()

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ),
            )

            response_text = response.text
            tokens_in = response.usage_metadata.prompt_token_count
            tokens_out = response.usage_metadata.candidates_token_count

            # Attempt JSON parsing
            data = _extract_json(response_text)

            return {
                "text": response_text,
                "data": data,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "model": model,
            }

        except json.JSONDecodeError as e:
            logging.error(f"JSON parse error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(retry_delay * (attempt + 1))

        except Exception as e:
            logging.error(f"Gemini API error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(retry_delay * (attempt + 1))


def _extract_json(text: str):
    """
    Extract JSON from response text, handling markdown code blocks.

    INPUT: Raw response text (may include ```json ... ``` wrappers)
    OUTPUT: Parsed dict/list or None
    """
    if not text:
        return None

    # Strip markdown code fences
    cleaned = re.sub(r"```json\s*|\s*```", "", text).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object or array in the text
        for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
            match = re.search(pattern, cleaned)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    continue
        return None
