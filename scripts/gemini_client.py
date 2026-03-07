"""
Shared Gemini Client Helper
============================
Centralizes Gemini API client initialization, retry logic, JSON parsing,
and token tracking for all pipeline scripts.

VERSION: 1.0 — Phase B Gemini migration
"""

import asyncio
import json
import logging
import random
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
    max_output_tokens: int | None = None,
    temperature: float = 0.0,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    response_mime_type: str = None,
) -> dict:
    """
    Call Gemini API with retry logic and structured response parsing.

    INPUT:
        - prompt: The prompt text to send
        - model: Gemini model name (defaults to CONFIG['GEMINI_MODEL'])
        - max_output_tokens: Maximum output tokens (None = no limit, model finishes naturally)
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
            config_kwargs = dict(
                temperature=temperature,
            )
            if max_output_tokens is not None:
                config_kwargs["max_output_tokens"] = max_output_tokens
            if response_mime_type:
                config_kwargs["response_mime_type"] = response_mime_type
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )

            response_text = response.text
            tokens_in = response.usage_metadata.prompt_token_count
            tokens_out = response.usage_metadata.candidates_token_count

            # Attempt JSON parsing
            data = _extract_json(response_text)

            # If JSON parse failed, try truncation repair (model may hit internal output limits)
            if data is None and response_text and response_text.strip():
                if max_output_tokens is not None and tokens_out >= max_output_tokens:
                    logging.warning(
                        f"Response hit max_output_tokens ({tokens_out}/{max_output_tokens}) "
                        f"— attempting truncated JSON repair"
                    )
                else:
                    logging.warning(
                        f"JSON parse failed ({tokens_out} tokens out) "
                        f"— attempting truncated JSON repair"
                    )
                data = _repair_truncated_json(response_text)

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


async def call_gemini_async(
    prompt: str,
    *,
    model: str = None,
    max_output_tokens: int | None = None,
    temperature: float = 0.0,
    max_retries: int = 5,
    retry_delay: float = 2.0,
    response_mime_type: str = None,
) -> dict:
    """
    Async version of call_gemini(). Uses client.aio for non-blocking API calls.

    INPUT/OUTPUT: Same as call_gemini().
    """
    if model is None:
        model = CONFIG["GEMINI_MODEL"]

    client = get_client()

    for attempt in range(max_retries):
        try:
            config_kwargs = dict(
                temperature=temperature,
            )
            if max_output_tokens is not None:
                config_kwargs["max_output_tokens"] = max_output_tokens
            if response_mime_type:
                config_kwargs["response_mime_type"] = response_mime_type
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )

            response_text = response.text
            tokens_in = response.usage_metadata.prompt_token_count
            tokens_out = response.usage_metadata.candidates_token_count

            # Attempt JSON parsing
            data = _extract_json(response_text)

            # If JSON parse failed, try truncation repair
            if data is None and response_text and response_text.strip():
                if max_output_tokens is not None and tokens_out >= max_output_tokens:
                    logging.warning(
                        f"Response hit max_output_tokens ({tokens_out}/{max_output_tokens}) "
                        f"— attempting truncated JSON repair"
                    )
                else:
                    logging.warning(
                        f"JSON parse failed ({tokens_out} tokens out) "
                        f"— attempting truncated JSON repair"
                    )
                data = _repair_truncated_json(response_text)

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
            await asyncio.sleep(retry_delay * (attempt + 1))

        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = "429" in error_str or "resource_exhausted" in error_str or "rate" in error_str
            if is_rate_limit:
                jitter = random.uniform(0, retry_delay)
                wait = retry_delay * (2 ** attempt) + jitter
                logging.warning(f"Rate limited (attempt {attempt + 1}/{max_retries}), waiting {wait:.1f}s")
                await asyncio.sleep(wait)
            else:
                logging.error(f"Gemini API error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(retry_delay * (attempt + 1))


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


def _repair_truncated_json(text: str):
    """
    Attempt to repair JSON truncated by max_output_tokens.

    INPUT: Raw response text with potentially incomplete JSON
    ALGORITHM:
        1. Strip markdown fences
        2. Find the start of the JSON object/array
        3. Remove the last incomplete value (likely mid-string or mid-object)
        4. Close all open braces and brackets
    OUTPUT: Parsed dict/list or None
    """
    if not text:
        return None

    cleaned = re.sub(r"```json\s*|\s*```", "", text).strip()

    # Find start of JSON
    start = -1
    start_char = None
    for i, ch in enumerate(cleaned):
        if ch in ('{', '['):
            start = i
            start_char = ch
            break
    if start == -1:
        return None

    fragment = cleaned[start:]

    # Remove trailing incomplete entry: drop back to last complete comma-separated item
    # Strip trailing whitespace, partial strings, etc.
    # Try progressively trimming from the end to find a repairable point
    for trim_chars in range(0, min(500, len(fragment))):
        candidate = fragment if trim_chars == 0 else fragment[:-trim_chars]

        # Remove trailing comma if present
        candidate = candidate.rstrip().rstrip(',').rstrip()

        # Count open/close braces and brackets
        open_braces = candidate.count('{') - candidate.count('}')
        open_brackets = candidate.count('[') - candidate.count(']')

        if open_braces < 0 or open_brackets < 0:
            continue

        # Close all open structures
        repaired = candidate + ']' * open_brackets + '}' * open_braces

        try:
            result = json.loads(repaired)
            logging.info(
                f"Truncated JSON repair succeeded (trimmed {trim_chars} chars, "
                f"closed {open_braces} braces + {open_brackets} brackets)"
            )
            return result
        except json.JSONDecodeError:
            continue

    logging.warning("Truncated JSON repair failed — could not recover valid JSON")
    return None
