import re
with open(r'c:\projects\smartfind_v3\ai.py', 'r') as f:
    content = f.read()

# Replace ask_text function
old_ask_text = '''def ask_text(prompt, json_mode=False, fast=False):
    \"\"\"Send a prompt, return the reply text, or None if anything goes wrong.
    fast=True: no retries; if Gemini is busy, pause AI for BUSY_PAUSE seconds so the next
    users skip it instantly instead of waiting.\"\"\"\n    global _paused_until, last_error\n    last_error = None\n    if not is_available():\n        last_error = \"AI unavailable (no key, or paused after a quota error)\"\n        return None\n    config = None\n    if json_mode:\n        try:\n            from google.genai import types\n            config = types.GenerateContentConfig(\n                response_mime_type=\"application/json\", temperature=0.2\n            )\n        except Exception as error:\n            last_error = f\"{type(error).__name__}: {str(error)[:300]}\"\n            return None\n\n    for attempt in (1, 2):\n        try:\n            reply = _get_client().models.generate_content(\n                model=os.environ.get(\"GEMINI_MODEL\", MODEL),\n                contents=redact(prompt),\n                config=config,\n            )\n            text = (reply.text or \"\").strip()\n            if not text:\n                last_error = \"Gemini returned an empty answer\"\n            return text or None\n        except Exception as error:   # slow, offline, bad key, quota... never crash the site\n            last_error = f\"{type(error).__name__}: {str(error)[:300]}\"\n            message = str(error).lower()\n            if (\"429\" in message or \"quota\" in message or \"exhausted\" in message) and attempt == 1 and not fast:\n                time.sleep(5)\n                continue\n            if \"429\" in message or \"quota\" in message or \"exhausted\" in message:\n                _paused_until = time.time() + PAUSE_SECONDS\n                return None\n            busy = \"503\" in message or \"504\" in message or \"unavailable\" in message or \"deadline\" in message or \"timed out\" in message or \"timeout\" in message\n            if busy and fast:\n                _paused_until = time.time() + BUSY_PAUSE\n                return None\n            if busy and attempt == 1:\n                time.sleep(RETRY_WAIT)\n                continue\n            return None\n    return None'''

new_ask_text = '''def ask_text(prompt, json_mode=False, fast=False):
    \"\"\"Send a prompt, return the reply text, or None if anything goes wrong.
    fast=True: no retries; if Gemini is busy, the circuit breaker may pause AI.\"\"\"\n    global _paused_until, last_error, _consecutive_failures\n    last_error = None\n    if not is_available():\n        last_error = \"AI unavailable (no key, or paused after a quota error)\"\n        return None\n    config = None\n    if json_mode:\n        try:\n            from google.genai import types\n            config = types.GenerateContentConfig(\n                response_mime_type=\"application/json\", temperature=0.2,\n                http_options=types.HttpOptions(timeout=TIMEOUT_MS),\n            )\n        except Exception as error:\n            last_error = f\"{type(error).__name__}: {str(error)[:300]}\"\n            return None\n\n    for attempt in (1, 2):\n        try:\n            reply = _get_client().models.generate_content(\n                model=os.environ.get(\"GEMINI_MODEL\", MODEL),\n                contents=redact(prompt),\n                config=config,\n            )\n            text = (reply.text or \"\").strip()\n            if not text:\n                last_error = \"Gemini returned an empty answer\"\n                _consecutive_failures = 0\n            else:\n                _consecutive_failures = 0\n            return text or None\n        except Exception as error:   # slow, offline, bad key, quota... never crash the site\n            last_error = f\"{type(error).__name__}: {str(error)[:300]}\"\n            message = str(error).lower()\n            if (\"429\" in message or \"quota\" in message or \"exhausted\" in message) and attempt == 1 and not fast:\n                time.sleep(5)\n                continue\n            if \"429\" in message or \"quota\" in message or \"exhausted\" in message:\n                _paused_until = time.time() + PAUSE_SECONDS\n                _consecutive_failures = 0\n                return None\n            busy = \"503\" in message or \"504\" in message or \"unavailable\" in message\n                or \"deadline\" in message or \"timed out\" in message or \"timeout\" in message\n            if busy:\n                _consecutive_failures += 1\n                if _consecutive_failures >= 2:\n                    _cb_until = time.time() + BREAKER_PAUSE\n                    _consecutive_failures = 0\n                    return None\n                if attempt == 1:\n                    time.sleep(RETRY_WAIT)\n                    continue\n            else:\n                _consecutive_failures = 0\n            return None\n    return None'''

if old_ask_text in content:
    content = content.replace(old_ask_text, new_ask_text)
    print('Replaced ask_text')
else:
    print('ask_text NOT found - checking what\\'s there')
    # Try to find ask_text
    if 'def ask_text' in content:
        print('Found ask_text function')
    else:
        print('ask_text function not found')

old = """def _get_client():
    global _client
    if _client is None:
        from google import genai
        from google.genai import types
        _client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
            http_options=types.HttpOptions(timeout=TIMEOUT_MS),
        )
    return _client"""

new = """def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client"""

if old in content:
    content = content.replace(old, new)
    with open(r'c:\projects\smartfind_v3\ai.py', 'w') as f:
        f.write(content)
    print('Replaced _get_client')
else:
    print('Not found')