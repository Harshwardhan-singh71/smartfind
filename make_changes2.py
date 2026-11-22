import re

with open(r'c:\projects\smartfind_v3\ai.py', 'r') as f:
    content = f.read()

# Find _call_gemini_image function boundaries
start = content.find('def _call_gemini_image(prompt')
# Find the next function after _call_gemini_image
end = content.find('def ask_image(prompt', start)
if start == -1 or end == -1:
    print('Could not find _call_gemini_image function boundaries')
    exit(1)

old_call_gemini = content[start:end]

new_call_gemini = '''def _call_gemini_image(prompt, image_bytes, mime_type, json_mode=False, fast=False):
    """Internal: send prompt + image to Gemini. Returns reply text or None."""
    global _paused_until, last_error
    last_error = None
    if not is_available():
        last_error = "AI unavailable (no key, or paused after a quota error)"
        return None
    config = None
    if json_mode:
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0.2,
                http_options=types.HttpOptions(timeout=IMAGE_TIMEOUT_MS),
            )
        except Exception as error:
            last_error = f"{type(error).__name__}: {str(error)[:300]}"
            return None

    for attempt in (1, 2):
        try:
            from google.genai import types
            image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            reply = _get_client().models.generate_content(
                model=os.environ.get("GEMINI_MODEL", MODEL),
                contents=[prompt, image_part],
                config=config,
            )
            text = (reply.text or "").strip()
            if not text:
                last_error = "Gemini returned an empty answer"
                _consecutive_failures = 0
            else:
                _consecutive_failures = 0
            return text or None
        except Exception as error:
            last_error = f"{type(error).__name__}: {str(error)[:300]}"
            message = str(error).lower()
            if ("429" in message or "quota" in message or "exhausted" in message) and attempt == 1 and not fast:
                time.sleep(5)
                continue
            if "429" in message or "quota" in message or "exhausted" in message:
                _paused_until = time.time() + PAUSE_SECONDS
                _consecutive_failures = 0
                return None
            busy = ("503" in message or "504" in message or "unavailable" in message
                    or "deadline" in message or "timed out" in message or "timeout" in message)
            if busy:
                _consecutive_failures += 1
                if _consecutive_failures >= 2:
                    _cb_until = time.time() + BREAKER_PAUSE
                    _consecutive_failures = 0
                    return None
                if attempt == 1:
                    time.sleep(RETRY_WAIT)
                    continue
            else:
                _consecutive_failures = 0
            return None
    return None
'''

if old_call_gemini in content:
    content = content[:start] + new_call_gemini + content[end:]
    with open(r'c:\projects\smartfind_v3\ai.py', 'w') as f:
        f.write(content)
    print('Replaced _call_gemini_image successfully')
else:
    print('old_call_gemini not found in content')
    if 'def _call_gemini_image' in content:
        print('_call_gemini_image function exists in file')
    else:
        print('_call_gemini_image function NOT found')