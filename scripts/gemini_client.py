"""
Shared Gemini Client Helper
============================
Centralizes Gemini API client initialization, retry logic, JSON parsing,
and token tracking for all pipeline scripts.

VERSION: 2.0 — Multi-key rotation with KeyPool
"""

import asyncio
import json
import logging
import random
import re
import threading
import time

from google import genai
from google.genai import types

from config import CONFIG
from gcp_secrets import get_gemini_api_keys


# ---------------------------------------------------------------------------
# Key Pool — multi-key rotation with cooldown and round-robin
# ---------------------------------------------------------------------------


class KeyPool:
    """
    Manages multiple Gemini API keys with round-robin rotation and cooldown.

    Two tiers: primary (round-robin first) and fallback (used when primaries
    are cooling down). Per-key tracking for cooldown, usage, and errors.
    Thread-safe (sync) and async-safe (async).

    ALGORITHM:
        1. Try primary keys in round-robin order, skip cooling/recently-used
        2. If no primary available, try fallback keys
        3. If ALL keys cooling, return soonest-available key + wait time
    """

    KEY_REQUEST_SPACING = 0.5   # min seconds between reuses of same key
    DEFAULT_COOLDOWN = 60       # seconds to sideline a key after 429

    def __init__(self, key_specs: list[dict]):
        """
        INPUT:
            - key_specs: list of {"name": str, "api_key": str, "tier": str}
        """
        self._keys: list[dict] = []
        self._primary_indices: list[int] = []
        self._fallback_indices: list[int] = []
        self._round_robin_idx = 0
        self._sync_lock = threading.Lock()
        self._async_lock = asyncio.Lock()

        for i, spec in enumerate(key_specs):
            client = genai.Client(api_key=spec["api_key"])
            entry = {
                "name": spec["name"],
                "client": client,
                "tier": spec["tier"],
                "cooldown_until": 0.0,
                "last_used": 0.0,
                "request_count": 0,
                "error_count": 0,
                "rotation_count": 0,
            }
            self._keys.append(entry)
            if spec["tier"] == "primary":
                self._primary_indices.append(i)
            else:
                self._fallback_indices.append(i)

        primary_count = len(self._primary_indices)
        fallback_count = len(self._fallback_indices)
        logging.info(
            f"KeyPool: {len(self._keys)} keys loaded "
            f"({primary_count} primary, {fallback_count} fallback)"
        )

    @property
    def size(self) -> int:
        return len(self._keys)

    # ---- Public acquire methods ----

    def acquire_sync(self) -> tuple[dict, float]:
        """Thread-safe key acquisition. Returns (entry, wait_seconds)."""
        with self._sync_lock:
            return self._select()

    async def acquire_async(self) -> tuple[dict, float]:
        """Async-safe key acquisition. Returns (entry, wait_seconds)."""
        async with self._async_lock:
            return self._select()

    # ---- Rate-limit marking ----

    def mark_rate_limited(self, entry: dict, cooldown: float | None = None):
        """Mark a key as rate-limited with a cooldown period."""
        if cooldown is None:
            cooldown = self.DEFAULT_COOLDOWN
        entry["cooldown_until"] = time.time() + cooldown
        entry["error_count"] += 1
        entry["rotation_count"] += 1

    # ---- Stats logging ----

    def log_stats(self):
        """Log per-key usage statistics."""
        logging.info("=" * 70)
        logging.info("KEY POOL STATISTICS")
        for entry in self._keys:
            logging.info(
                f"  {entry['name']:10s} | {entry['tier']:8s} | "
                f"calls: {entry['request_count']:5d} | "
                f"errors: {entry['error_count']:3d} | "
                f"rotations: {entry['rotation_count']:3d}"
            )
        logging.info("=" * 70)

    # ---- Internal selection logic ----

    def _select(self) -> tuple[dict, float]:
        """
        Select next available key. Must be called under lock.

        OUTPUT: (key_entry, wait_seconds)
            - wait_seconds == 0: key is ready to use immediately
            - wait_seconds > 0: caller must wait this long before using the key
        """
        now = time.time()

        # Try primary keys in round-robin order
        for _ in range(len(self._primary_indices)):
            idx = self._primary_indices[
                self._round_robin_idx % len(self._primary_indices)
            ]
            self._round_robin_idx += 1
            entry = self._keys[idx]
            if (
                entry["cooldown_until"] <= now
                and (now - entry["last_used"]) >= self.KEY_REQUEST_SPACING
            ):
                entry["last_used"] = now
                entry["request_count"] += 1
                return entry, 0.0

        # Try fallback keys
        for idx in self._fallback_indices:
            entry = self._keys[idx]
            if (
                entry["cooldown_until"] <= now
                and (now - entry["last_used"]) >= self.KEY_REQUEST_SPACING
            ):
                entry["last_used"] = now
                entry["request_count"] += 1
                return entry, 0.0

        # All keys busy — find soonest available
        soonest_time = float("inf")
        soonest_entry = self._keys[0]
        for entry in self._keys:
            available_at = max(
                entry["cooldown_until"],
                entry["last_used"] + self.KEY_REQUEST_SPACING,
            )
            if available_at < soonest_time:
                soonest_time = available_at
                soonest_entry = entry

        wait = max(0.0, soonest_time - now)
        return soonest_entry, wait


# ---------------------------------------------------------------------------
# Pool singleton
# ---------------------------------------------------------------------------

_pool: KeyPool | None = None


def get_pool() -> KeyPool:
    """Return the singleton KeyPool, creating it on first call."""
    global _pool
    if _pool is None:
        key_specs = get_gemini_api_keys()
        if not key_specs:
            raise RuntimeError(
                "No Gemini API keys found. Set GEMINI_KEY_* env vars or "
                "configure GCP Secret Manager."
            )
        _pool = KeyPool(key_specs)
    return _pool


def get_client():
    """Return a Gemini client (first key in pool). For backward compatibility."""
    pool = get_pool()
    return pool._keys[0]["client"]


# ---------------------------------------------------------------------------
# Rate-limit detection helpers
# ---------------------------------------------------------------------------


def _is_rate_limit(error: Exception) -> bool:
    """Check if an exception is a rate-limit (429) error."""
    error_str = str(error).lower()
    return (
        "429" in error_str
        or "resource_exhausted" in error_str
        or "rate limit" in error_str
    )


def _parse_cooldown(error: Exception) -> float:
    """Parse cooldown duration from API error message, or return default."""
    error_str = str(error).lower()
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_str)
    if match:
        return float(match.group(1)) + random.uniform(1, 5)
    return KeyPool.DEFAULT_COOLDOWN


# ---------------------------------------------------------------------------
# Sync API call
# ---------------------------------------------------------------------------


def call_gemini(
    prompt: str,
    *,
    model: str = None,
    max_output_tokens: int | None = None,
    temperature: float = 0.0,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    response_mime_type: str = None,
    response_schema=None,
    thinking_budget: int | None = None,
) -> dict:
    """
    Call Gemini API with key rotation and retry logic.

    On 429 rate-limit errors, rotates to the next available key immediately
    (no sleep). Only waits when ALL keys are cooling. Non-rate-limit errors
    use standard exponential backoff.

    INPUT:
        - prompt: The prompt text to send
        - model: Gemini model name (defaults to CONFIG['GEMINI_MODEL'])
        - max_output_tokens: Maximum output tokens (None = model finishes naturally)
        - temperature: Sampling temperature (0.0 for reproducibility)
        - max_retries: Retry attempts for non-rate-limit failures
        - retry_delay: Base delay between retries (seconds)
        - thinking_budget: If set, enables Gemini thinking mode with this token budget
    OUTPUT: dict with keys:
        - 'text': raw response text
        - 'data': parsed JSON (or None if not JSON)
        - 'tokens_in': prompt token count
        - 'tokens_out': candidate token count
        - 'tokens_thinking': thinking token count (0 if thinking not enabled)
        - 'model': model name used
    """
    if model is None:
        model = CONFIG["GEMINI_MODEL"]

    pool = get_pool()
    max_rotations = max_retries * pool.size
    rotation_count = 0
    retry_count = 0

    while retry_count < max_retries:
        entry, wait = pool.acquire_sync()
        if wait > 0:
            logging.debug(f"All keys busy, waiting {wait:.1f}s")
            time.sleep(wait)
            entry["last_used"] = time.time()
            entry["request_count"] += 1

        try:
            config_kwargs = dict(temperature=temperature)
            if max_output_tokens is not None:
                config_kwargs["max_output_tokens"] = max_output_tokens
            if thinking_budget is not None:
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=thinking_budget
                )
            if response_schema:
                config_kwargs["response_mime_type"] = "application/json"
                config_kwargs["response_schema"] = response_schema
            elif response_mime_type:
                config_kwargs["response_mime_type"] = response_mime_type

            response = entry["client"].models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )

            response_text = response.text
            tokens_in = response.usage_metadata.prompt_token_count
            tokens_out = response.usage_metadata.candidates_token_count
            tokens_thinking = (
                getattr(response.usage_metadata, "thoughts_token_count", 0) or 0
            )

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
                "tokens_thinking": tokens_thinking,
                "model": model,
            }

        except json.JSONDecodeError as e:
            retry_count += 1
            logging.error(
                f"JSON parse error (attempt {retry_count}/{max_retries}): {e}"
            )
            if retry_count >= max_retries:
                raise
            time.sleep(retry_delay * retry_count)

        except Exception as e:
            if _is_rate_limit(e):
                cooldown = _parse_cooldown(e)
                pool.mark_rate_limited(entry, cooldown)
                rotation_count += 1
                if rotation_count >= max_rotations:
                    raise RuntimeError(
                        f"Rate limit exhausted after {rotation_count} key rotations: {e}"
                    ) from e
                logging.warning(
                    f"Key {entry['name']} rate-limited, rotating "
                    f"({rotation_count}/{max_rotations})"
                )
                continue  # Retry immediately with next key
            else:
                retry_count += 1
                logging.error(
                    f"Gemini API error (attempt {retry_count}/{max_retries}): {e}"
                )
                if retry_count >= max_retries:
                    raise
                time.sleep(retry_delay * retry_count)


# ---------------------------------------------------------------------------
# Async API call
# ---------------------------------------------------------------------------


async def call_gemini_async(
    prompt: str,
    *,
    model: str = None,
    max_output_tokens: int | None = None,
    temperature: float = 0.0,
    max_retries: int = 5,
    retry_delay: float = 2.0,
    response_mime_type: str = None,
    response_schema=None,
    thinking_budget: int | None = None,
) -> dict:
    """
    Async version of call_gemini(). Uses key rotation and client.aio for
    non-blocking API calls.

    INPUT/OUTPUT: Same as call_gemini().
    """
    if model is None:
        model = CONFIG["GEMINI_MODEL"]

    pool = get_pool()
    max_rotations = max_retries * pool.size
    rotation_count = 0
    retry_count = 0

    while retry_count < max_retries:
        entry, wait = await pool.acquire_async()
        if wait > 0:
            logging.debug(f"All keys busy, waiting {wait:.1f}s")
            await asyncio.sleep(wait)
            entry["last_used"] = time.time()
            entry["request_count"] += 1

        try:
            config_kwargs = dict(temperature=temperature)
            if max_output_tokens is not None:
                config_kwargs["max_output_tokens"] = max_output_tokens
            if thinking_budget is not None:
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=thinking_budget
                )
            if response_schema:
                config_kwargs["response_mime_type"] = "application/json"
                config_kwargs["response_schema"] = response_schema
            elif response_mime_type:
                config_kwargs["response_mime_type"] = response_mime_type

            response = await entry["client"].aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )

            response_text = response.text
            tokens_in = response.usage_metadata.prompt_token_count
            tokens_out = response.usage_metadata.candidates_token_count
            tokens_thinking = (
                getattr(response.usage_metadata, "thoughts_token_count", 0) or 0
            )

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
                "tokens_thinking": tokens_thinking,
                "model": model,
            }

        except json.JSONDecodeError as e:
            retry_count += 1
            logging.error(
                f"JSON parse error (attempt {retry_count}/{max_retries}): {e}"
            )
            if retry_count >= max_retries:
                raise
            await asyncio.sleep(retry_delay * retry_count)

        except Exception as e:
            if _is_rate_limit(e):
                cooldown = _parse_cooldown(e)
                pool.mark_rate_limited(entry, cooldown)
                rotation_count += 1
                if rotation_count >= max_rotations:
                    raise RuntimeError(
                        f"Rate limit exhausted after {rotation_count} key rotations: {e}"
                    ) from e
                logging.warning(
                    f"Key {entry['name']} rate-limited, rotating "
                    f"({rotation_count}/{max_rotations})"
                )
                continue  # Retry immediately with next key
            else:
                retry_count += 1
                logging.error(
                    f"Gemini API error (attempt {retry_count}/{max_retries}): {e}"
                )
                if retry_count >= max_retries:
                    raise
                await asyncio.sleep(retry_delay * retry_count)


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------


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
