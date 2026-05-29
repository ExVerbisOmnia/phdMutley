#!/usr/bin/env python3
"""Test Gemini API quota for different modes."""
import sys
sys.path.insert(0, "scripts")
from gcp_secrets import get_gemini_api_key
from google import genai
from google.genai import types

key = get_gemini_api_key()
client = genai.Client(api_key=key)

# Test 1: thinking_budget=0
print("Test 1: gemini-2.5-flash with thinking_budget=0...")
try:
    r = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Analyze: " + "x " * 5000,
        config=types.GenerateContentConfig(
            temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    tok = r.usage_metadata
    think_tok = getattr(tok, 'thoughts_token_count', 0) or 0
    print(f"  SUCCESS - in: {tok.prompt_token_count}, out: {tok.candidates_token_count}, thinking: {think_tok}")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {str(e)[:200]}")

# Test 2: large prompt, no thinking config at all
print("Test 2: gemini-2.5-flash large prompt, no thinking...")
try:
    r = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="List 5 citations from this legal text: " + "The court in Smith v. Jones (2020) held that " * 500,
        config=types.GenerateContentConfig(temperature=0.0),
    )
    tok = r.usage_metadata
    print(f"  SUCCESS - in: {tok.prompt_token_count}, out: {tok.candidates_token_count}")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {str(e)[:200]}")

# Test 3: thinking_budget=1 (minimal thinking)
print("Test 3: gemini-2.5-flash with thinking_budget=1...")
try:
    r = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Say hello",
        config=types.GenerateContentConfig(
            temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_budget=1),
        ),
    )
    print(f"  SUCCESS")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {str(e)[:200]}")

print("\nConclusion: thinking mode quota is exhausted" if "FAILED" in "Test 1" else "\nDone.")
