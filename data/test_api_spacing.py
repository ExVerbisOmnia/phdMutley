#!/usr/bin/env python3
"""Test Gemini API with spaced-out requests to diagnose quota type."""
import sys, time
sys.path.insert(0, "scripts")
from gcp_secrets import get_gemini_api_key
from google import genai
from google.genai import types

key = get_gemini_api_key()
client = genai.Client(api_key=key)

def test_call(label, prompt, thinking=False):
    config = {"temperature": 0.0}
    if thinking:
        config["thinking_config"] = types.ThinkingConfig(thinking_budget=1024)
    try:
        r = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(**config),
        )
        tok = r.usage_metadata
        print(f"  {label}: OK (in={tok.prompt_token_count}, out={tok.candidates_token_count})")
        return True
    except Exception as e:
        print(f"  {label}: FAILED ({str(e)[:120]})")
        return False

print("=== Test sequence with 15s spacing ===")

# Test 1: small prompt, no thinking
test_call("small/no-think", "Say hi")
print("  waiting 15s...")
time.sleep(15)

# Test 2: medium prompt (~1K tokens), no thinking
test_call("1K-tok/no-think", "Explain: " + "legal text " * 200)
print("  waiting 15s...")
time.sleep(15)

# Test 3: larger prompt (~5K tokens), no thinking
test_call("5K-tok/no-think", "Summarize: " + "court ruling " * 1000)
print("  waiting 15s...")
time.sleep(15)

# Test 4: small prompt, WITH thinking
test_call("small/thinking", "Say hi", thinking=True)
print("  waiting 15s...")
time.sleep(15)

# Test 5: medium prompt, WITH thinking
test_call("1K-tok/thinking", "Explain: " + "legal text " * 200, thinking=True)

print("\n=== Done ===")
